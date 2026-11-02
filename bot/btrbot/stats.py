"""Audience figures for the website (About > Partners), read from the official APIs the bot is already connected to.

Every 2 h (bot.stats_tick):
  Instagram (Graph API, the Page token from /connect): followers + every reel's views (insights metric "views";
    needs the permission instagram_manage_insights, added to instagram.SCOPES on 02.11.2026: reconnect once).
  TikTok: a SEPARATE connection to the SANDBOX of the app (its own client key/secret), scopes user.info.basic,
    user.info.stats, video.list: the production app is under review with publishing scopes only. Connected from
    Telegram: « tiktokstats CLIENT_KEY CLIENT_SECRET », then the link, then « tiktokstats CODE ».
The result is written to data/stats/social.json in the GitHub repo (contents API, BOT_GITHUB_TOKEN); the site's
tools/auto/btr_stats.py prefers it over Metricool. A part that fails is left out; the site keeps its last figures.
"""
import base64
import json
import time
import urllib.parse
from datetime import datetime, timezone

import requests

from . import tiktok as _tt
from .instagram import Instagram
from .share import NotConnected, Secrets

REPO = "loicviatte/btr-website"
PATH = "data/stats/social.json"
TT_SCOPES = "user.info.basic,user.info.stats,video.list"


# ---------------------------------------------------------------- Instagram
def instagram(sec: Secrets) -> dict:
    I = Instagram(sec)
    me = I._get(I.uid, fields="followers_count,media_count,username")
    reels, after, err = [], None, None
    for _ in range(20):                                    # 20 pages × 50 = every post
        kw = {"fields": "id,media_product_type,permalink,timestamp", "limit": 50}
        if after:
            kw["after"] = after
        page = I._get(f"{I.uid}/media", **kw)
        for m in page.get("data", []):
            if m.get("media_product_type") != "REELS":
                continue
            views = None
            for metric in ("views", "plays"):
                try:
                    d = I._get(f"{m['id']}/insights", metric=metric).get("data") or []
                    views = int(((d[0].get("values") or [{}])[0]).get("value") or 0) if d else None
                    break
                except RuntimeError as e:                  # missing permission or metric not offered
                    err = str(e)[:200]
            if views is not None:
                reels.append([m.get("timestamp", "")[:10].replace("-", ""), m.get("permalink", ""), views])
        after = ((page.get("paging") or {}).get("cursors") or {}).get("after")
        if not (page.get("paging") or {}).get("next"):
            break
    out = {"followers": int(me.get("followers_count") or 0), "reels": reels}
    if not reels and err:
        out["error"] = err                                  # followers still usable
    return out


# ---------------------------------------------------------------- TikTok (sandbox app, stats only)
def tt_auth_url(client_key: str) -> str:
    return _tt.AUTH + "?" + urllib.parse.urlencode({"client_key": client_key, "response_type": "code",
                                                    "scope": TT_SCOPES, "redirect_uri": _tt.REDIRECT, "state": "stats"})


def _tt_store(sec: Secrets, tok: dict) -> None:
    now = int(time.time())
    sec.set(tts_access=tok["access_token"], tts_access_exp=now + int(tok.get("expires_in") or 86400) - 300,
            tts_refresh=tok.get("refresh_token") or sec.get("tts_refresh"),
            tts_refresh_exp=now + int(tok.get("refresh_expires_in") or 365 * 86400))


def tt_connect(sec: Secrets, code: str) -> dict:
    key, secret = sec.get("tts_client_key"), sec.get("tts_client_secret")
    if not key or not secret:
        raise RuntimeError("colle d'abord « tiktokstats CLIENT_KEY CLIENT_SECRET » (sandbox)")
    tok = _tt._check(requests.post(f"{_tt.API}/oauth/token/", timeout=30, data={
        "client_key": key, "client_secret": secret, "code": urllib.parse.unquote(code),
        "grant_type": "authorization_code", "redirect_uri": _tt.REDIRECT}))
    _tt_store(sec, tok)
    return tiktok_user(sec)


def _tt_token(sec: Secrets) -> str:
    s = sec.load()
    if not s.get("tts_refresh"):
        raise NotConnected("TikTok stats")
    if s.get("tts_access") and int(s.get("tts_access_exp") or 0) > time.time():
        return s["tts_access"]
    tok = _tt._check(requests.post(f"{_tt.API}/oauth/token/", timeout=30, data={
        "client_key": s.get("tts_client_key"), "client_secret": s.get("tts_client_secret"),
        "grant_type": "refresh_token", "refresh_token": s.get("tts_refresh")}))
    _tt_store(sec, tok)
    return tok["access_token"]


def tiktok_user(sec: Secrets) -> dict:
    h = {"Authorization": f"Bearer {_tt_token(sec)}"}
    d = _tt._check(requests.get(f"{_tt.API}/user/info/", headers=h, timeout=30, params={
        "fields": "display_name,follower_count,likes_count,video_count"}))
    return (d.get("data") or {}).get("user") or {}


def tiktok(sec: Secrets) -> dict:
    u = tiktok_user(sec)
    h = {"Authorization": f"Bearer {_tt_token(sec)}", "Content-Type": "application/json; charset=UTF-8"}
    vids, cursor = [], None
    for _ in range(30):                                    # 20 per page
        body = {"max_count": 20}
        if cursor:
            body["cursor"] = cursor
        d = _tt._check(requests.post(f"{_tt.API}/video/list/", headers=h, timeout=30, json=body,
                                     params={"fields": "id,create_time,view_count"})).get("data") or {}
        for v in d.get("videos") or []:
            day = datetime.fromtimestamp(int(v.get("create_time") or 0), timezone.utc).strftime("%Y%m%d")
            vids.append([day, str(v.get("id")), int(v.get("view_count") or 0)])
        if not d.get("has_more"):
            break
        cursor = d.get("cursor")
    return {"followers": int(u.get("follower_count") or 0), "likes": int(u.get("likes_count") or 0),
            "videos": vids}


# ---------------------------------------------------------------- collect + push
def collect(sec: Secrets) -> dict:
    out = {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
           "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")}
    for name, fn in (("instagram", instagram), ("tiktok", tiktok)):
        try:
            out[name] = fn(sec)
        except NotConnected:
            pass
        except Exception as e:  # noqa: BLE001
            out[name + "_error"] = str(e)[:300]
    return out


def push(token: str, data: dict) -> bool:
    """Write data/stats/social.json on main (no site deploy: Vercel ignores data/stats)."""
    if not token:
        raise RuntimeError("BOT_GITHUB_TOKEN manquant")
    h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    url = f"https://api.github.com/repos/{REPO}/contents/{PATH}"
    r = requests.get(url, headers=h, params={"ref": "main"}, timeout=30)
    sha = r.json().get("sha") if r.status_code == 200 else None
    body = {"message": "Audience figures (bot: Instagram + TikTok APIs)", "branch": "main",
            "content": base64.b64encode((json.dumps(data, ensure_ascii=False, indent=1) + "\n").encode()).decode()}
    if sha:
        body["sha"] = sha
    r = requests.put(url, headers=h, json=body, timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"GitHub {r.status_code}: {r.text[:200]}")
    return True
