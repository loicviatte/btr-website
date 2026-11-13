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
TT_SCHEDULED, TT_POSTED = "b1b05eb7-20a6-4a78-8602-98e1ba8262b0", "cc9d50cc-9317-48b1-a044-af3d4bc8326a"
F_YT, YT_TODO = "42cc05f2-218b-405a-ad1b-6069c5e2b04a", "93280cc0-4dd6-4654-b1cf-b3fa39cd1949"
IG_SCHEDULED, IG_POSTED = "eb8ad4fc-67be-4503-acca-7c14e6ad370d", "3594b624-2ee1-4d1b-83ff-bc4c8d5d9509"
GRID = "b64d9e9c-6809-4527-9511-736f4d21ca4e"           # Instagram placement « Grid » (orderindex 0)
STORY_PLACE = "f1f6f3ca-f4db-4e3f-9918-4d2015dc4908"    # Instagram placement « Story »
FMT_STORY, FMT_CAROUSEL = "6af1e79f-f33e-40bc-8a2c-6ab1f8f96649", "768a686c-3286-45d1-980a-06869af04629"
TT_NO, YT_NO = "affcf24b-8be9-454c-ad20-98c92ceddc41", "783dfbd6-cd19-4e22-9479-0befa6b0f759"
YT_SCHEDULED, YT_POSTED = "a95e6c4c-35e7-4a87-8705-fcd3dc7592e0", "530bf62a-705a-4647-b596-364aff465ebf"
WHERE_IG = ("Where: Instagram (Reels tab, not in grid) + TikTok + YouTube Shorts\n"
            "Cover: whole head + hook inside Instagram's 3:4 grid tile (centre).\nShorts: set “Related video” to the episode, no link in the description.")
WHERE_SHORT = ("Where: TikTok + YouTube Shorts only (not Instagram)\n"
               "Shorts: set “Related video” to the episode, no link in the description.")
# Content calendar statuses: to generate → generated → approved (filed) → ready (Loïc validated the cover: the bot
# schedules) → scheduled → posted
LATER = ("ready", "scheduled", "posted")
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
    """The code in the address Loïc pastes back (http://127.0.0.1:8765/?code=…&scope=…), with or without « http:// »
    (Safari and Telegram drop it when copying), or None."""
    t = text or ""
    if "127.0.0.1" not in t and "localhost" not in t:
        return None
    m = re.search(r"[?&]code=([^&\s]+)", t)
    return urllib.parse.unquote(m.group(1)) if m else None


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

    def put(self, path: Path, folder_id: str, name: str, mime: str, fid: str | None = None, same: bool = False) -> dict:
        """Upload under `name` in `folder_id`; an existing file (its id kept from before) is replaced in place, renamed
        and moved, so its link never changes. Anyone with the link can view it."""
        from googleapiclient.http import MediaFileUpload
        media = MediaFileUpload(str(path), mimetype=mime, resumable=True, chunksize=8 * 2 ** 20)
        f = None
        if fid:
            try:
                cur = self.svc.files().get(fileId=fid, fields="id,parents,trashed").execute()
                if not cur.get("trashed"):
                    olds = ",".join(p for p in cur.get("parents", []) if p != folder_id)
                    kw = {"addParents": folder_id, "removeParents": olds} if olds else {}
                    if same:                               # content unchanged: name / folder only (seconds, not minutes)
                        f = self.svc.files().update(fileId=fid, body={"name": name}, fields="id,webViewLink",
                                                    **kw).execute()
                        return f
                    f = self.svc.files().update(fileId=fid, body={"name": name}, media_body=media,
                                                fields="id,webViewLink", **kw).execute()
            except Exception:  # noqa: BLE001
                f = None                                   # deleted by hand: upload again
        if f is None:
            fid = self._find(name, folder_id, False)
            if fid:
                f = self.svc.files().update(fileId=fid, media_body=media, fields="id,webViewLink").execute()
            else:
                f = self.svc.files().create(body={"name": name, "parents": [folder_id]}, media_body=media,
                                            fields="id,webViewLink").execute()
        self.svc.permissions().create(fileId=f["id"], body={"type": "anyone", "role": "reader"}).execute()
        return f

    def drop_empty_folders(self, root: str, keep: str) -> None:
        """Folders the bot made in « BTR Reels » that are now empty (the old one-per-episode layout) go to the bin."""
        r = self.svc.files().list(q=f"'{root}' in parents and mimeType = 'application/vnd.google-apps.folder' "
                                    "and trashed = false", fields="files(id)", pageSize=100).execute()
        for f in r.get("files", []):
            if f["id"] == keep:
                continue
            inside = self.svc.files().list(q=f"'{f['id']}' in parents and trashed = false", fields="files(id)",
                                           pageSize=1).execute().get("files")
            if not inside:
                self.svc.files().update(fileId=f["id"], body={"trashed": True}).execute()

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

    def download(self, fid: str) -> bytes:
        return self.svc.files().get_media(fileId=fid).execute()

    def folder_link(self, fid: str) -> str:
        return f"https://drive.google.com/drive/folders/{fid}"


def restore_before(secrets: "Secrets", client: tuple[str, str], fid: str, since: str, local: Path) -> str:
    """The Drive file's last revision from before `since` (ISO UTC) becomes the current one again, and the local copy
    gets the same content. Returns "restored" or "unchanged" (nothing was uploaded after `since`)."""
    import io

    from googleapiclient.http import MediaIoBaseDownload
    d = Drive(secrets, client)
    revs = d.svc.revisions().list(fileId=fid, fields="revisions(id,modifiedTime)", pageSize=200).execute()
    revs = sorted(revs.get("revisions", []), key=lambda r: r["modifiedTime"])
    older = [r for r in revs if r["modifiedTime"] < since]
    newer = [r for r in revs if r["modifiedTime"] >= since]
    if not older:
        return "unchanged"
    req = d.svc.revisions().get_media(fileId=fid, revisionId=older[-1]["id"])
    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, req, chunksize=16 * 2 ** 20)
    done = False
    while not done:
        _, done = dl.next_chunk()
    data = buf.getvalue()
    if len(data) < 10000:
        raise RuntimeError("ancienne version vide")
    tmp = local.with_suffix(".restore.mp4")
    tmp.write_bytes(data)
    tmp.replace(local)                                  # the server copy = the validated version
    if not newer:
        return "unchanged"
    from googleapiclient.http import MediaFileUpload
    d.svc.files().update(fileId=fid, media_body=MediaFileUpload(str(local), mimetype="video/mp4", resumable=True,
                                                                chunksize=8 * 2 ** 20)).execute()
    return "restored"


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
ON_CHANGE: list = []      # callbacks when the bot changes the calendar (Loïc 03.11: « Posts planning » follows at once)


def _changed() -> None:
    for f in ON_CHANGE:
        try:
            f()
        except Exception:  # noqa: BLE001
            pass


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
            r = self._req("PUT", f"/task/{tid}", json=fields)
        except RuntimeError as e:
            if "markdown_content" not in fields or "ClickUp 4" not in str(e):
                raise
            fields["description"] = fields.pop("markdown_content")          # older API: plain text
            r = self._req("PUT", f"/task/{tid}", json=fields)
        if set(fields) - {"markdown_content", "description"}:              # status / name / date: calendar changed
            _changed()
        return r

    def set_field(self, tid: str, field: str, value) -> None:
        self._req("POST", f"/task/{tid}/field/{field}", json={"value": value})
        _changed()

    def create(self, list_id: str = CONTENT_LIST, **fields) -> dict:
        r = self._req("POST", f"/list/{list_id}/task", json=fields)
        _changed()
        return r

    def delete(self, tid: str) -> None:
        _changed()
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


def option_name(task: dict, fid: str) -> str:
    """The chosen option's name of a dropdown field (the API gives its id or its orderindex)."""
    for f in task.get("custom_fields") or []:
        if f.get("id") != fid:
            continue
        v = f.get("value")
        if isinstance(v, dict):
            return str(v.get("name") or "")
        for o in (f.get("type_config") or {}).get("options") or []:
            if v is not None and (o.get("id") == v or str(o.get("orderindex")) == str(v)):
                return str(o.get("name") or "")
    return ""


def all_posted(task: dict) -> bool:
    """Every platform planned for this post (Instagram / TikTok / YouTube not « Not planned ») is « Posted »."""
    names = [option_name(task, f).lower() for f in (F_IG, F_TT, F_YT)]
    planned = [n for n in names if n and n != "not planned"]
    return bool(planned) and all(n == "posted" for n in planned)


def close_if_posted(cu: "ClickUp", tid: str) -> bool:
    """Status « posted » once everything planned is out (Loïc 01.11: the Saturday reels stayed « scheduled »)."""
    t = cu.task(tid)
    if (t.get("status") or {}).get("status", "").lower() != "posted" and all_posted(t):
        cu.update(tid, status="posted")
        return True
    return False


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
            if d and abs((d.date() - ep_date.date()).days) <= 3:     # calendar days (timedelta.days floors)
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
                instagram: bool = True, base: str = "") -> str:
    """The task's own lines (where / when / cover rules) kept, then the bot's block, rewritten at each validation:
    links, and the captions in code blocks (exact text, line breaks kept, copy button in ClickUp)."""
    keep = (old or "").split(MARK)[0].rstrip()
    caps = item.get("captions") or {}
    where = "Instagram + TikTok + Shorts" if instagram else "TikTok + Shorts seulement (pas Instagram)"
    lines = [MARK, "", f"**Reel validé le {today}** : « {title} » ({item.get('duration', '?')} s) · {where}", "",
             f"- Vidéo : {links.get('video', '—')}", f"- Cover : {links.get('cover', '—')}",
             f"- Dossier Drive : {links.get('folder', '—')}", f"- Épisode : {video_url}"]
    if links.get("instagram"):
        lines.append(f"- Instagram : {links['instagram']}")
    if links.get("short"):
        at = (item.get("yt_short") or {}).get("at")
        lines.append(f"- YouTube Short : {links['short']}" + (f" (programmé par le bot, en ligne le {_when(at)})" if at else ""))
    if base:
        lines.append(f"- Fichier : {base}.mp4")
    lines.append("")
    if instagram:
        collab = " et ".join("@" + h for h in caps.get("collab") or [])
        lines += ["---", "", "**📸 Instagram** (sans hashtags)" + (f" · collaboration : inviter {collab}" if collab else ""),
                  "", caps.get("instagram") or "—", ""]
    lines += ["---", "", "**🎵 TikTok** (avec hashtags)", "", caps.get("tiktok") or "—", ""]
    if caps.get("short_title"):
        lines += ["---", "", "**▶️ YouTube Shorts** (vidéo associée : l'épisode ; pas de lien dans la description)", "",
                  f"Titre : {caps['short_title']}", "", caps.get("short_desc") or ""]
    return (keep + "\n\n" if keep else "") + "\n".join(lines)



def _when(at: str) -> str:
    from . import shorts
    dt = shorts.parse(at)
    return shorts.label(dt) + " (Londres)" if dt else at

# BTR episode numbers (order of the guests' first episode on the channel); new guests get the next one automatically
EP_NUMBERS = {"kiera brunton": 1, "michael shelton": 2, "jaime dieguez": 3, "nicole cutler": 4, "james wilson": 5,
              "anthony rutherford": 6, "phemelo mabuse": 7, "ian waite": 8, "oskar odiakosa": 9, "peter nash": 10,
              "peter maxwell": 11, "leila stewart": 12, "oti mabuse": 13}


# Instagram accounts (for the @ in the Instagram caption and the collaboration invite); others get their full name
HANDLES = {"oti mabuse": "otimabuse", "marius iepure": "mariusiepure"}


def guest_handle(guest: str) -> str | None:
    """The guest's Instagram @ (without @); "" = Loïc said there is none; None = unknown (the bot asks)."""
    return HANDLES.get(_norm(guest))


def load_handles(data_dir: Path) -> None:
    """Handles Loïc confirmed for new guests (data/handles.json, "" = no Instagram), on top of HANDLES."""
    try:
        HANDLES.update(json.loads((Path(data_dir) / "handles.json").read_text()))
    except Exception:  # noqa: BLE001
        pass


def set_handle(data_dir: Path, guest: str, handle: str) -> None:
    path = Path(data_dir) / "handles.json"
    try:
        d = json.loads(path.read_text())
    except Exception:  # noqa: BLE001
        d = {}
    d[_norm(guest)] = handle.lstrip("@").strip()
    path.write_text(json.dumps(d, ensure_ascii=False, indent=1))
    HANDLES[_norm(guest)] = d[_norm(guest)]


# Extra Instagram collaborators on top of the guest's @ and Marius (Loïc 03.11: Hannah's association
# @dpa_dance_promotersassociation on EP14): per guest in data/collabs.json, per episode in ep["ig_collabs"].
IG_MAX_COLLAB = 3          # Graph API: up to 3 collaborators per post (instagram.container / carousel cut the rest)
COLLABS: dict[str, list[str]] = {}


def load_collabs(data_dir: Path) -> None:
    try:
        COLLABS.update(json.loads((Path(data_dir) / "collabs.json").read_text()))
    except Exception:  # noqa: BLE001
        pass


def set_collabs(data_dir: Path, guest: str, handles: list[str]) -> None:
    path = Path(data_dir) / "collabs.json"
    try:
        d = json.loads(path.read_text())
    except Exception:  # noqa: BLE001
        d = {}
    d[_norm(guest)] = clean_handles(handles)
    if not d[_norm(guest)]:
        d.pop(_norm(guest))
    path.write_text(json.dumps(d, ensure_ascii=False, indent=1))
    COLLABS.clear()
    COLLABS.update(d)


def clean_handles(handles) -> list[str]:
    out = [str(h).strip().lstrip("@").strip().rstrip("/").split("/")[-1].split("?")[0] for h in handles or []]
    return list(dict.fromkeys(h for h in out if re.fullmatch(r"[A-Za-z0-9._]{2,30}", h)))


def extra_collabs(guest: str, ep=None) -> list[str]:
    """The extra collaborators of this guest + this episode (guest's own @ and Marius left out)."""
    own = {(HANDLES.get(_norm(guest)) or "").lower(), "mariusiepure"}
    out = list(COLLABS.get(_norm(guest)) or []) + list((ep.get("ig_collabs") if ep is not None else None) or [])
    return [h for h in clean_handles(out) if h.lower() not in own]


def collab_list(handle: str | None, extra=()) -> list[str]:
    """Invites in priority order: guest, Marius, then the extras (Instagram keeps the first IG_MAX_COLLAB)."""
    return list(dict.fromkeys(h for h in (handle, "mariusiepure", *extra) if h))


def apply_handle(caps: dict, guest: str, handle: str | None, extra=()) -> dict:
    """Instagram caption « Guest on … » → « @handle & @extra on … » and the collab invites (guest + Marius + extras).
    Idempotent; an extra taken out of the list leaves the caption too."""
    caps = dict(caps or {})
    ig = caps.get("instagram") or ""
    if handle and guest:
        ig = re.sub(r"(^|\n)" + re.escape(guest) + r"(?= on )", lambda m: m.group(1) + "@" + handle, ig, count=1)
    who = "@" + handle if handle else guest
    if ig and who:
        tail = "".join(" & @" + x for x in extra)
        ig = re.sub(r"(^|\n)(" + re.escape(who) + r")(?: & @[A-Za-z0-9._]+)*(?= on )",
                    lambda m: m.group(1) + m.group(2) + tail, ig, count=1)
    if ig:
        caps["instagram"] = ig
    caps["collab"] = collab_list(handle, extra)
    return caps


def guest_key(guest: str) -> str:
    return _norm(guest)


def _slug(s: str, n: int = 40) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").upper()[:n].strip("-")


def post_date(task: dict | None) -> datetime:
    """The day the reel is planned (the ClickUp task's due date, London time), else today."""
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("Europe/London")
    due = (task or {}).get("due_date")
    if due:
        try:
            return datetime.fromtimestamp(int(due) / 1000, tz)
        except (TypeError, ValueError):
            pass
    return datetime.now(tz)


def file_base(day: datetime, ep_no: int | None, guest: str, instagram: bool, title: str) -> str:
    """MMDD_EP13_OTI-MABUSE_FEED_ALONE-ON-STRICTLY (FEED = on Instagram too, SHORTS = TikTok + Shorts only)."""
    return "_".join([day.strftime("%m%d"), f"EP{ep_no}" if ep_no else "EP", _slug(guest, 30) or "GUEST",
                     "FEED" if instagram else "SHORTS", _slug(title, 50) or "REEL"])


def file_id(link: str) -> str | None:
    m = re.search(r"/d/([A-Za-z0-9_-]{20,})", link or "")
    return m.group(1) if m else None


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


def release_final(video: dict) -> bool:
    """The release date can't move any more: the video is public or has its publishAt. An unlisted video's publishedAt
    is only its upload date (Lene 13.11: uploaded Nov 5 → matched the « Ep Nov 3 » tasks)."""
    st = video.get("status") or {}
    return st.get("privacyStatus") == "public" or bool(st.get("publishAt"))


def refresh_release(ep, video_of) -> datetime | None:
    """ep["release_at"], read again from YouTube until it is final (`release_final`)."""
    cur = None
    if ep.get("release_at"):
        try:
            cur = datetime.fromisoformat(ep["release_at"])
        except ValueError:
            cur = None
    if cur is not None and ep.get("release_final"):
        return cur
    try:
        video = video_of(ep.video_id)
    except Exception:  # noqa: BLE001
        return cur
    d = episode_date(video)
    if d is not None:
        ep["release_at"], ep["release_final"] = d.isoformat(), release_final(video)
        ep.save()
    return d or cur


def today_str() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%d.%m.%Y")
