"""Instagram reels through Meta's official Graph API (Instagram API with Facebook Login, no third party).

Connected once from Telegram (/connect): Loïc pastes his Meta app id, app secret and a user token from the Graph API
Explorer; the bot turns it into the BTR Facebook Page's token (never expires) and keeps it in data/secrets.json with
the Instagram account id. Instagram has no scheduling in the API: the bot uploads the reel about 45 min before its time
(container), then publishes it at the time itself (bot.ig_tick, every minute).
"""
import json
import time
from pathlib import Path

import requests

from .share import NotConnected, Secrets

GRAPH = "https://graph.facebook.com/v23.0"
SCOPES = "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement,business_management"


def _check(r: requests.Response) -> dict:
    try:
        d = r.json()
    except ValueError:
        d = {}
    if r.status_code >= 400 or "error" in d:
        e = d.get("error") or {}
        msg = e.get("error_user_msg") or e.get("message") or r.text[:300]
        raise RuntimeError(f"Instagram {r.status_code} : {msg}")
    return d


def connect(secrets: Secrets, app_id: str, app_secret: str, user_token: str) -> str:
    """Short user token → long-lived → the token of the Page linked to the Instagram account (no expiry).
    Returns the Instagram @username. Nothing but the page token and ids is kept."""
    long = _check(requests.get(f"{GRAPH}/oauth/access_token", timeout=30, params={
        "grant_type": "fb_exchange_token", "client_id": app_id, "client_secret": app_secret,
        "fb_exchange_token": user_token}))["access_token"]
    pages = _check(requests.get(f"{GRAPH}/me/accounts", timeout=30, params={
        "access_token": long, "fields": "id,name,access_token,instagram_business_account{id,username}",
        "limit": 100})).get("data", [])
    pages = [p for p in pages if p.get("instagram_business_account")]
    if not pages:
        raise RuntimeError("aucune page Facebook reliée à un compte Instagram pro dans ce que tu as autorisé : "
                           "recommence et coche la page BTR et le compte Instagram")
    pick = next((p for p in pages if "routine" in (p["instagram_business_account"].get("username") or "").lower()
                 or "routine" in p.get("name", "").lower()), pages[0])
    ig = pick["instagram_business_account"]
    secrets.set(ig_token=pick["access_token"], ig_user=ig["id"], ig_username=ig.get("username", ""),
                ig_page=pick["id"])
    return ig.get("username", "")


class Instagram:
    def __init__(self, secrets: Secrets):
        s = secrets.load()
        self.token, self.uid = s.get("ig_token"), s.get("ig_user")
        if not self.token or not self.uid:
            raise NotConnected("Instagram")

    def _get(self, path: str, **params) -> dict:
        return _check(requests.get(f"{GRAPH}/{path}", params={"access_token": self.token, **params}, timeout=60))

    def _post(self, path: str, **data) -> dict:
        return _check(requests.post(f"{GRAPH}/{path}", data={"access_token": self.token, **data}, timeout=60))

    def container(self, video: Path, caption: str, collaborators: list[str], cover_url: str | None,
                  share_to_feed: bool) -> str:
        """Reel container with the local file uploaded to Meta (resumable upload). Returns the container id."""
        data = {"media_type": "REELS", "upload_type": "resumable", "caption": caption[:2200],
                "share_to_feed": "true" if share_to_feed else "false"}
        if collaborators:
            data["collaborators"] = json.dumps(collaborators[:3])
        if cover_url:
            data["cover_url"] = cover_url
        c = self._post(f"{self.uid}/media", **data)
        cid = c["id"]
        uri = c.get("uri") or f"https://rupload.facebook.com/ig-api-upload/v23.0/{cid}"
        size = video.stat().st_size
        with open(video, "rb") as f:
            r = requests.post(uri, data=f, timeout=600, headers={
                "Authorization": f"OAuth {self.token}", "offset": "0", "file_size": str(size)})
        _check(r)
        return cid

    def status(self, cid: str) -> dict:
        return self._get(cid, fields="status_code,status")

    def wait(self, cid: str, limit: float = 600) -> dict:
        """Until Meta has processed the video: FINISHED, or raises on ERROR / EXPIRED / timeout."""
        end = time.time() + limit
        delay = 5
        while True:
            st = self.status(cid)
            code = st.get("status_code")
            if code in ("FINISHED", "PUBLISHED"):
                return st
            if code in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"Instagram a refusé la vidéo ({code}) : {st.get('status', '')}")
            if time.time() > end:
                raise RuntimeError("Instagram traite encore la vidéo après 10 min")
            time.sleep(delay)
            delay = min(delay * 2, 30)

    def publish(self, cid: str) -> dict:
        mid = self._post(f"{self.uid}/media_publish", creation_id=cid)["id"]
        try:
            link = self._get(mid, fields="permalink").get("permalink", "")
        except Exception:  # noqa: BLE001
            link = ""
        return {"id": mid, "permalink": link}
