"""TikTok Content Posting API (Direct Post), official, no third party.

Connected once from Telegram (/connect): Loïc pastes « tiktok CLIENT_KEY CLIENT_SECRET » (app BTR Studio on
developers.tiktok.com), opens the authorisation link, TikTok sends him to breaktheroutinepodcast.com/tiktok/callback
which shows « tiktok CODE »; he pastes it back. Tokens: access 24 h (refreshed by the bot), refresh 365 days, kept in
data/secrets.json. Until TikTok audits the app, everything it posts is private (SELF_ONLY): the bot then keeps the
notification mode for real posts (bot.tt_tick).

Before each post Loïc confirms in Telegram (bot.tt_compose, TikTok's UX rules): account, caption, audience picked by
him from creator_info (nothing pre-selected), comments / duet / stitch, commercial content disclosure.
"""
import time
import urllib.parse
from pathlib import Path

import requests

from .share import NotConnected, Secrets

API = "https://open.tiktokapis.com/v2"
AUTH = "https://www.tiktok.com/v2/auth/authorize/"
REDIRECT = "https://www.breaktheroutinepodcast.com/tiktok/callback"
SCOPES = "user.info.basic,video.publish,video.upload"
PRIVACY_FR = {"PUBLIC_TO_EVERYONE": "Tout le monde", "MUTUAL_FOLLOW_FRIENDS": "Amis",
              "FOLLOWER_OF_CREATOR": "Abonnés", "SELF_ONLY": "Moi uniquement"}


def _check(r: requests.Response) -> dict:
    try:
        d = r.json()
    except ValueError:
        d = {}
    err = d.get("error") or {}
    if r.status_code >= 400 or (err and err.get("code") not in (None, "", "ok")):
        msg = err.get("message") or d.get("error_description") or r.text[:300]
        raise RuntimeError(f"TikTok {r.status_code} : {err.get('code') or d.get('error') or ''} {msg}".strip())
    return d


def auth_url(client_key: str) -> str:
    return AUTH + "?" + urllib.parse.urlencode({"client_key": client_key, "response_type": "code", "scope": SCOPES,
                                                 "redirect_uri": REDIRECT, "state": "btr"})


def _store(secrets: Secrets, tok: dict) -> None:
    now = int(time.time())
    secrets.set(tt_access=tok["access_token"], tt_access_exp=now + int(tok.get("expires_in") or 86400) - 300,
                tt_refresh=tok.get("refresh_token") or secrets.get("tt_refresh"),
                tt_refresh_exp=now + int(tok.get("refresh_expires_in") or 365 * 86400),
                tt_open_id=tok.get("open_id") or secrets.get("tt_open_id"))


def connect(secrets: Secrets, code: str) -> dict:
    """Authorisation code → tokens; returns the account's display name / avatar."""
    key, secret = secrets.get("tt_client_key"), secrets.get("tt_client_secret")
    if not key or not secret:
        raise RuntimeError("colle d'abord « tiktok CLIENT_KEY CLIENT_SECRET »")
    tok = _check(requests.post(f"{API}/oauth/token/", timeout=30, data={
        "client_key": key, "client_secret": secret, "code": urllib.parse.unquote(code),
        "grant_type": "authorization_code", "redirect_uri": REDIRECT}))
    _store(secrets, tok)
    return TikTok(secrets).user()


class TikTok:
    def __init__(self, secrets: Secrets):
        self.sec = secrets
        if not secrets.get("tt_refresh"):
            raise NotConnected("TikTok")

    def token(self) -> str:
        s = self.sec.load()
        if s.get("tt_access") and int(s.get("tt_access_exp") or 0) > time.time():
            return s["tt_access"]
        tok = _check(requests.post(f"{API}/oauth/token/", timeout=30, data={
            "client_key": s.get("tt_client_key"), "client_secret": s.get("tt_client_secret"),
            "grant_type": "refresh_token", "refresh_token": s.get("tt_refresh")}))
        _store(self.sec, tok)
        return tok["access_token"]

    def _h(self) -> dict:
        return {"Authorization": f"Bearer {self.token()}", "Content-Type": "application/json; charset=UTF-8"}

    def user(self) -> dict:
        d = _check(requests.get(f"{API}/user/info/", headers=self._h(), timeout=30,
                                params={"fields": "open_id,display_name,avatar_url"}))
        return (d.get("data") or {}).get("user") or {}

    def creator_info(self) -> dict:
        """creator_nickname / creator_username / creator_avatar_url, privacy_level_options, comment_disabled,
        duet_disabled, stitch_disabled, max_video_post_duration_sec — shown to Loïc before each post."""
        return _check(requests.post(f"{API}/post/publish/creator_info/query/", headers=self._h(), timeout=30,
                                    json={})).get("data") or {}

    def _upload(self, url: str, video: Path, size: int, chunk: int, count: int) -> None:
        with open(video, "rb") as f:
            for i in range(count):
                start = i * chunk
                end = size - 1 if i == count - 1 else start + chunk - 1
                f.seek(start)
                data = f.read(end - start + 1)
                r = requests.put(url, data=data, timeout=600, headers={
                    "Content-Type": "video/mp4", "Content-Length": str(len(data)),
                    "Content-Range": f"bytes {start}-{end}/{size}"})
                if r.status_code >= 400:
                    raise RuntimeError(f"TikTok upload {r.status_code} : {r.text[:200]}")

    @staticmethod
    def _chunks(size: int) -> tuple[int, int]:
        return (size, 1) if size <= 64_000_000 else (10_000_000, size // 10_000_000)

    def draft(self, video: Path) -> str:
        """Upload (video.upload): the video lands in the account's TikTok inbox as a draft, to finish in the app."""
        size = video.stat().st_size
        chunk, count = self._chunks(size)
        d = _check(requests.post(f"{API}/post/publish/inbox/video/init/", headers=self._h(), timeout=60, json={
            "source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk,
                            "total_chunk_count": count}}))["data"]
        self._upload(d["upload_url"], video, size, chunk, count)
        return d["publish_id"]

    def post(self, video: Path, title: str, settings: dict, cover_ms: int = 0) -> str:
        """Direct Post of a local file with Loïc's settings (privacy_level, disable_comment / duet / stitch,
        brand_content_toggle, brand_organic_toggle). Returns the publish_id."""
        size = video.stat().st_size
        chunk, count = self._chunks(size)
        body = {"post_info": {"title": title[:2200], "privacy_level": settings["privacy_level"],
                              "disable_comment": bool(settings.get("disable_comment")),
                              "disable_duet": bool(settings.get("disable_duet")),
                              "disable_stitch": bool(settings.get("disable_stitch")),
                              "video_cover_timestamp_ms": int(cover_ms),
                              "brand_content_toggle": bool(settings.get("brand_content_toggle")),
                              "brand_organic_toggle": bool(settings.get("brand_organic_toggle"))},
                "source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk,
                                "total_chunk_count": count}}
        d = _check(requests.post(f"{API}/post/publish/video/init/", headers=self._h(), timeout=60, json=body))["data"]
        self._upload(d["upload_url"], video, size, chunk, count)
        return d["publish_id"]

    def status(self, publish_id: str) -> dict:
        """status: PROCESSING_UPLOAD / PROCESSING_DOWNLOAD / SEND_TO_USER_INBOX / PUBLISH_COMPLETE / FAILED."""
        return _check(requests.post(f"{API}/post/publish/status/fetch/", headers=self._h(), timeout=30,
                                    json={"publish_id": publish_id})).get("data") or {}
