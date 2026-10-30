"""YouTube Data API v3: find unlisted uploads, read captions, update title/description/thumbnail, schedule Shorts."""
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]


class YouTube:
    def __init__(self, token_file: Path, channel_id: str, client: tuple[str, str, str] | None = None):
        """client = (client_id, client_secret, refresh_token): the same Google app as the website
        (YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN). Otherwise a token file from btrbot.auth."""
        self.token_file = token_file
        self.channel_id = channel_id
        self.client = client
        self._svc = None
        self._uploads = None

    @property
    def svc(self):
        if self._svc is None:
            if self.client and all(self.client):
                cid, secret, refresh = self.client
                creds = Credentials(None, refresh_token=refresh, client_id=cid, client_secret=secret,
                                    token_uri="https://oauth2.googleapis.com/token", scopes=SCOPES)
                creds.refresh(Request())
            else:
                creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)
                if not creds.valid:
                    creds.refresh(Request())
                    self.token_file.write_text(creds.to_json())
            # the client refreshes the access token by itself from here on
            self._svc = build("youtube", "v3", credentials=creds, cache_discovery=False)
        return self._svc

    # ---- listing -------------------------------------------------------
    def uploads_playlist(self) -> str:
        if not self._uploads:
            r = self.svc.channels().list(part="contentDetails", id=self.channel_id).execute()
            self._uploads = r["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        return self._uploads

    def recent(self, n: int = 25) -> list[dict]:
        r = self.svc.playlistItems().list(part="contentDetails", playlistId=self.uploads_playlist(), maxResults=min(n, 50)).execute()
        ids = [i["contentDetails"]["videoId"] for i in r.get("items", [])]
        if not ids:
            return []
        v = self.svc.videos().list(part="snippet,status,contentDetails", id=",".join(ids), maxResults=50).execute()
        return v.get("items", [])

    def unlisted_ready(self) -> list[dict]:
        return [
            v for v in self.recent()
            if v["status"].get("privacyStatus") == "unlisted" and v["status"].get("uploadStatus") == "processed"
        ]

    def public_references(self, n: int = 8) -> list[dict]:
        """Recent public long-form episodes (title + description), used as style references."""
        out = []
        for v in self.recent(50):
            if v["status"].get("privacyStatus") != "public":
                continue
            dur = v["contentDetails"].get("duration", "")
            if "H" not in dur and not _minutes_over(dur, 15):  # skip Shorts and clips
                continue
            out.append({"id": v["id"], "title": v["snippet"]["title"], "description": v["snippet"].get("description", "")})
            if len(out) >= n:
                break
        return out

    def video(self, vid: str) -> dict:
        r = self.svc.videos().list(part="snippet,status,contentDetails", id=vid).execute()
        return r["items"][0]

    # ---- captions --------------------------------------------------------
    def caption_srt(self, vid: str) -> tuple[str | None, str | None]:
        """Returns (srt_text, kind) with kind 'standard' (uploaded) or 'asr' (auto). None if not ready."""
        r = self.svc.captions().list(part="snippet", videoId=vid).execute()
        tracks = r.get("items", [])
        if not tracks:
            return None, None

        def rank(t):
            s = t["snippet"]
            return (s.get("trackKind") != "standard", not s.get("language", "").startswith("en"), s.get("status") != "serving")

        for t in sorted(tracks, key=rank):
            if t["snippet"].get("status") not in (None, "serving"):
                continue
            data = self.svc.captions().download(id=t["id"], tfmt="srt").execute()
            text = data.decode("utf-8", "replace") if isinstance(data, bytes) else str(data)
            if text.strip():
                return text, t["snippet"].get("trackKind", "").lower()
        return None, None

    # ---- writing ----------------------------------------------------------
    def update_metadata(self, vid: str, title: str | None = None, description: str | None = None) -> None:
        v = self.svc.videos().list(part="snippet", id=vid).execute()["items"][0]
        sn = v["snippet"]
        body = {"id": vid, "snippet": {
            "title": (title or sn["title"])[:100],
            "description": (description if description is not None else sn.get("description", ""))[:5000],
            "categoryId": sn["categoryId"],
        }}
        for keep in ("tags", "defaultLanguage", "defaultAudioLanguage"):
            if keep in sn:
                body["snippet"][keep] = sn[keep]
        self.svc.videos().update(part="snippet", body=body).execute()

    def set_thumbnail(self, vid: str, jpg: Path) -> None:
        self.svc.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(jpg), mimetype="image/jpeg")).execute()

    # ---- Shorts (validated reels, scheduled: private until publishAt) ---------------------------------
    def upload_short(self, path: Path, title: str, description: str, publish_at: str, category: str = "22",
                     tags: list[str] | None = None) -> dict:
        """New private video that YouTube makes public by itself at publish_at (RFC 3339, UTC). Vertical and under
        3 min = a Short. Resumable upload in 8 MB chunks."""
        body = {"snippet": {"title": title[:100], "description": description[:5000], "categoryId": category or "22",
                            "tags": tags or [], "defaultLanguage": "en", "defaultAudioLanguage": "en"},
                "status": {"privacyStatus": "private", "publishAt": publish_at, "selfDeclaredMadeForKids": False,
                           "containsSyntheticMedia": False}}
        media = MediaFileUpload(str(path), mimetype="video/mp4", chunksize=8 << 20, resumable=True)
        req = self.svc.videos().insert(part="snippet,status", body=body, media_body=media)
        resp = None
        while resp is None:
            _, resp = req.next_chunk(num_retries=3)
        return resp

    def reschedule(self, vid: str, publish_at: str) -> None:
        """New publishAt for a Short that is still waiting (private + scheduled). Never touches a public video."""
        st = self.video(vid)["status"]
        if st.get("privacyStatus") != "private" or not st.get("publishAt"):
            raise RuntimeError("ce Short est déjà publié (ou n'est plus programmé) : je n'y touche pas")
        body = {"id": vid, "status": {"privacyStatus": "private", "publishAt": publish_at}}
        for keep in ("embeddable", "license", "publicStatsViewable", "selfDeclaredMadeForKids", "containsSyntheticMedia"):
            if keep in st:
                body["status"][keep] = st[keep]
        self.svc.videos().update(part="status", body=body).execute()

    def statuses(self, ids: list[str]) -> dict[str, dict]:
        """id → status (privacyStatus, uploadStatus, publishAt…); missing ids = deleted videos."""
        out = {}
        for i in range(0, len(ids), 50):
            r = self.svc.videos().list(part="status", id=",".join(ids[i:i + 50])).execute()
            out.update({v["id"]: v["status"] for v in r.get("items", [])})
        return out


def _minutes_over(iso: str, minutes: int) -> bool:
    import re
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return False
    h, mi, _ = (int(x or 0) for x in m.groups())
    return h * 60 + mi >= minutes
