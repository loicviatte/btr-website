"""Validated reels → Google Drive (Loïc's own Drive, folder « BTR Reels / <episode> ») and the ClickUp content calendar.

Both are connected once from Telegram, without a computer (see bot.connect_cmd):
- Drive: the same Google app as YouTube (YT_CLIENT_ID / YT_CLIENT_SECRET), scope drive.file only (the bot sees nothing
  but the files it creates). Loïc opens the link, accepts, and pastes back the address of the page that does not load
  (http://127.0.0.1:8765/?code=…). The refresh token is kept in data/secrets.json (never in the repo).
- ClickUp: his personal API token (pk_…), pasted in the chat; the message is deleted right away.
"""
import json
import os
import re
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
REDIRECT = "http://127.0.0.1:8765/"           # the loopback address already used for the YouTube token
CLICKUP = "https://api.clickup.com/api/v2"
CONTENT_LIST = os.environ.get("CLICKUP_LIST", "1200920000009096")      # « Content calendar », space Break The Routine
F_EPISODE = "d32347e7-35fc-486b-964c-21a3539189fb"
F_FORMAT, CLIP = "7751e670-2be0-4518-bb2b-07272384f4f8", "a9b07faf-6af1-410b-9a8f-3b22cbd4e785"
F_PLACEMENT, REELS_TAB = "102a1750-0c36-4620-b95b-ac12fccde027", "3673c5e3-d04d-4836-a2ac-14de82d40c30"
F_IG, IG_NO, IG_TODO = ("00e62fea-52fd-4927-82b1-712e64a799e7", "6d3b3f7c-8782-4d9e-aa78-b8fca22f8615",
                        "2e187c73-0476-4683-a90e-3d0899df3076")
F_TT, TT_TODO = "a02e2e2c-eb04-47ba-bb85-0d9c9d77fbcd", "4d699c14-5ae2-4817-8f34-70f029e3c8d7"
F_YT, YT_TODO = "42cc05f2-218b-405a-ad1b-6069c5e2b04a", "93280cc0-4dd6-4654-b1cf-b3fa39cd1949"
WHERE_IG = ("Where: Instagram (Reels tab, not in grid) + TikTok + YouTube Shorts\n"
            "Cover: face and text inside the top 1080×1440.\nShorts: set “Related video” to the episode, no link in the description.")
WHERE_SHORT = ("Where: TikTok + YouTube Shorts only (not Instagram)\n"
               "Shorts: set “Related video” to the episode, no link in the description.")
MARK = "———— BTR Studio ————"                 # everything below is rewritten by the bot at each validation
FOLDER = "BTR Reels"
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


# ---------------------------------------------------------------- secrets
class Secrets:
    def __init__(self, data_dir: Path):
        self.path = Path(data_dir) / "secrets.json"

    def load(self) -> dict:
        try:
            return json.loads(self.path.read_text())
        except Exception:  # noqa: BLE001
            return {}

    def get(self, key: str, default=None):
        return self.load().get(key, default)

    def set(self, **kw) -> None:
        d = self.load()
        d.update(kw)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(d))
        os.chmod(tmp, 0o600)
        tmp.replace(self.path)


# ---------------------------------------------------------------- Google Drive
def drive_auth_url(client_id: str) -> str:
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id, "redirect_uri": REDIRECT, "response_type": "code", "access_type": "offline",
        "prompt": "consent", "scope": DRIVE_SCOPE})


def code_from(text: str) -> str | None:
    """The code in the address Loïc pastes back (http://127.0.0.1:8765/?code=…&scope=…), or None."""
    m = re.search(r"https?://(?:127\.0\.0\.1|localhost)\S*", text or "")
    if not m:
        return None
    q = urllib.parse.parse_qs(urllib.parse.urlparse(m.group(0)).query)
    return (q.get("code") or [None])[0]


def drive_connect(secrets: Secrets, client: tuple[str, str], code: str) -> None:
    r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
        "code": code, "client_id": client[0], "client_secret": client[1], "redirect_uri": REDIRECT,
        "grant_type": "authorization_code"})
    tok = r.json()
    if "refresh_token" not in tok:
        raise RuntimeError(tok.get("error_description") or tok.get("error") or "Google n'a pas renvoyé d'accès")
    if DRIVE_SCOPE not in tok.get("scope", ""):
        raise RuntimeError("l'accès à Drive n'a pas été coché sur la page Google : recommence et coche-le")
    secrets.set(drive_refresh=tok["refresh_token"])


class Drive:
    def __init__(self, secrets: Secrets, client: tuple[str, str]):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        refresh = secrets.get("drive_refresh")
        if not refresh:
            raise NotConnected("Drive")
        creds = Credentials(None, refresh_token=refresh, client_id=client[0], client_secret=client[1],
                            token_uri="https://oauth2.googleapis.com/token", scopes=[DRIVE_SCOPE])
        creds.refresh(Request())
        self.svc = build("drive", "v3", credentials=creds, cache_discovery=False)
        self.secrets = secrets

    def _find(self, name: str, parent: str | None, folder: bool) -> str | None:
        q = [f"name = '{name.replace(chr(39), chr(92) + chr(39))}'", "trashed = false"]
        q.append("mimeType = 'application/vnd.google-apps.folder'" if folder
                 else "mimeType != 'application/vnd.google-apps.folder'")
        if parent:
            q.append(f"'{parent}' in parents")
        r = self.svc.files().list(q=" and ".join(q), fields="files(id)", pageSize=5).execute()
        return (r.get("files") or [{}])[0].get("id")

    def folder(self, name: str, parent: str | None = None) -> str:
        fid = self._find(name, parent, True)
        if fid:
            return fid
        body = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
        if parent:
            body["parents"] = [parent]
        return self.svc.files().create(body=body, fields="id").execute()["id"]

    def upload(self, path: Path, folder_id: str, mime: str) -> dict:
        """Upload (or replace, same link) a file; anyone with the link can view it."""
        from googleapiclient.http import MediaFileUpload
        media = MediaFileUpload(str(path), mimetype=mime, resumable=True, chunksize=8 * 2 ** 20)
        fid = self._find(path.name, folder_id, False)
        if fid:
            f = self.svc.files().update(fileId=fid, media_body=media, fields="id,webViewLink").execute()
        else:
            f = self.svc.files().create(body={"name": path.name, "parents": [folder_id]}, media_body=media,
                                        fields="id,webViewLink").execute()
        self.svc.permissions().create(fileId=f["id"], body={"type": "anyone", "role": "reader"}).execute()
        return f

    def folder_link(self, fid: str) -> str:
        return f"https://drive.google.com/drive/folders/{fid}"


class NotConnected(RuntimeError):
    def __init__(self, what: str):
        super().__init__(f"{what} pas encore connecté")
        self.what = what


def drive_error(e: Exception) -> str:
    """A readable reason, with the activation link when the Drive API is off in the Google project."""
    s = str(e)
    m = re.search(r"https://console\.developers\.google\.com/apis/api/drive\.googleapis\.com/overview\?project=\d+", s)
    if m:
        return f"l'API Google Drive n'est pas activée dans le projet Google : active-la ici, puis revalide : {m.group(0)}"
    if "invalid_grant" in s:
        return "l'accès Drive a été retiré : refais /connect"
    return s[-300:]


# ---------------------------------------------------------------- ClickUp
class ClickUp:
    def __init__(self, token: str | None):
        if not token:
            raise NotConnected("ClickUp")
        self.h = {"Authorization": token, "Content-Type": "application/json"}

    def _req(self, method: str, path: str, **kw) -> dict:
        r = requests.request(method, CLICKUP + path, headers=self.h, timeout=60, **kw)
        if r.status_code == 401:
            raise RuntimeError("le token ClickUp n'est plus valable : refais /connect")
        if r.status_code >= 400:
            raise RuntimeError(f"ClickUp {r.status_code} : {r.text[:200]}")
        return r.json() if r.text else {}

    def me(self) -> dict:
        return self._req("GET", "/user").get("user", {})

    def tasks(self, list_id: str = CONTENT_LIST) -> list[dict]:
        out, page = [], 0
        while page < 10:
            r = self._req("GET", f"/list/{list_id}/task", params={"page": page, "include_closed": "true",
                                                                   "subtasks": "true"})
            out += r.get("tasks", [])
            if r.get("last_page", True) or not r.get("tasks"):
                break
            page += 1
        return out

    def task(self, tid: str) -> dict:
        return self._req("GET", f"/task/{tid}", params={"include_markdown_description": "true"})

    def update(self, tid: str, **fields) -> dict:
        try:
            return self._req("PUT", f"/task/{tid}", json=fields)
        except RuntimeError as e:
            if "markdown_content" not in fields or "ClickUp 4" not in str(e):
                raise
            fields["description"] = fields.pop("markdown_content")          # older API: plain text
            return self._req("PUT", f"/task/{tid}", json=fields)

    def set_field(self, tid: str, field: str, value) -> None:
        self._req("POST", f"/task/{tid}/field/{field}", json={"value": value})

    def create(self, list_id: str = CONTENT_LIST, **fields) -> dict:
        return self._req("POST", f"/list/{list_id}/task", json=fields)

    def delete(self, tid: str) -> None:
        self._req("DELETE", f"/task/{tid}")

    def attach(self, tid: str, path: Path) -> None:
        h = {"Authorization": self.h["Authorization"]}
        with open(path, "rb") as f:
            r = requests.post(f"{CLICKUP}/task/{tid}/attachment", headers=h, timeout=120,
                              files={"attachment": (path.name, f, "image/jpeg")})
        if r.status_code >= 400:
            raise RuntimeError(f"ClickUp pièce jointe {r.status_code}")


def _field(task: dict, fid: str):
    for f in task.get("custom_fields") or []:
        if f.get("id") == fid:
            return f.get("value")
    return None


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def slot_date(text: str, year: int) -> datetime | None:
    """« Ep Nov 3 » / « Episode of Nov 3 » → that day."""
    m = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})\b", (text or "").lower())
    if not m:
        return None
    try:
        return datetime(year, MONTHS[m.group(1)], int(m.group(2)), tzinfo=timezone.utc)
    except ValueError:
        return None


def is_reel_slot(t: dict) -> bool:
    name = (t.get("name") or "").lower()
    return name.startswith("reel ") and "teaser" not in name


def matches_episode(t: dict, label: str, guest: str, part: str | None, ep_date: datetime | None) -> bool:
    """The slot belongs to this episode: its Episode field / name says so (« Oti Mabuse P2 », « Oti P2 »), or it is a
    placeholder dated around the episode's release (« Ep Nov 3 », « Episode of Nov 3 », ±3 days)."""
    field, name = _norm(str(_field(t, F_EPISODE) or "")), _norm(t.get("name", ""))
    if _norm(label) and (_norm(label) in field or _norm(label) in name):
        return True
    first = _norm(guest).split(" ")[0] if guest else ""
    tag = f"p{part}" if part else ""
    if first and (first in field.split() or first in name.split()):
        if not tag or tag in field.split() or tag in name.split():
            return True
    if ep_date:
        for txt in (str(_field(t, F_EPISODE) or ""), t.get("name", "")):
            d = slot_date(txt, ep_date.year)
            if d and abs((d - ep_date).days) <= 3:
                return True
    return False


def free_slots(tasks: list[dict], label: str, guest: str, part: str | None, ep_date: datetime | None,
               taken: set[str]) -> list[dict]:
    """The episode's Instagram reel slots still free in the calendar, earliest first."""
    free = [t for t in tasks if is_reel_slot(t) and t["id"] not in taken
            and (t.get("status") or {}).get("status", "").lower() in ("to generate", "generated")
            and MARK not in (t.get("text_content") or t.get("description") or "")
            and matches_episode(t, label, guest, part, ep_date)]
    return sorted(free, key=lambda t: int(t.get("due_date") or 9e15))


def pick_slot(tasks: list[dict], label: str, guest: str, part: str | None, ep_date: datetime | None,
              taken: set[str]) -> dict | None:
    """The first free reel slot of this episode in the calendar (earliest due date)."""
    free = free_slots(tasks, label, guest, part, ep_date, taken)
    return free[0] if free else None


def slot_name(old: str, label: str, title: str) -> str:
    m = re.match(r"(Reel\s+\d+\s*/\s*\d+)", old or "")
    head = m.group(1) if m else "Reel"
    return f"{head} · {label} · {title}"[:200]


def description(old: str, links: dict, item: dict, title: str, video_url: str, today: str,
                instagram: bool = True) -> str:
    """The task's own lines (where / when / cover rules) kept, then the bot's block, rewritten at each validation:
    links, and the captions in code blocks (exact text, line breaks kept, copy button in ClickUp)."""
    keep = (old or "").split(MARK)[0].rstrip()
    caps = item.get("captions") or {}

    def fence(t):
        return "```\n" + (t or "—").replace("```", "") + "\n```"
    where = "Instagram + TikTok + Shorts" if instagram else "TikTok + Shorts seulement (pas Instagram)"
    lines = [MARK, "", f"**Reel validé le {today}** : « {title} » ({item.get('duration', '?')} s) · {where}", "",
             f"- Vidéo : {links.get('video', '—')}", f"- Cover : {links.get('cover', '—')}",
             f"- Dossier Drive : {links.get('folder', '—')}", f"- Épisode : {video_url}", ""]
    if instagram:
        lines += ["**Légende Instagram** (sans hashtags)", "", fence(caps.get("instagram")), ""]
    lines += ["**Légende TikTok / Shorts** (avec hashtags)", "", fence(caps.get("tiktok"))]
    return (keep + "\n\n" if keep else "") + "\n".join(lines)


def episode_label(guest: str, part: str | None) -> str:
    return f"{guest} P{part}" if part else guest


def episode_date(video: dict) -> datetime | None:
    """Release date of the episode on YouTube (scheduled publishAt, else publishedAt)."""
    for v in ((video.get("status") or {}).get("publishAt"), (video.get("snippet") or {}).get("publishedAt")):
        if v:
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                pass
    return None


def today_str() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%d.%m.%Y")
