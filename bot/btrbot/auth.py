"""Run ONCE on a computer with a browser (your Mac):

    python -m btrbot.auth path/to/client_secret.json

Pick the "Break The Routine Podcast" channel when Google asks. It writes
secrets/youtube_token.json, which you then copy to the server.
"""
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from .youtube import SCOPES

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
    creds = flow.run_local_server(port=0, prompt="select_account consent", access_type="offline")
    out = ROOT / "secrets" / "youtube_token.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(creds.to_json())
    from googleapiclient.discovery import build
    me = build("youtube", "v3", credentials=creds).channels().list(part="snippet", mine=True).execute()
    names = [c["snippet"]["title"] for c in me.get("items", [])]
    print(f"Token saved to {out}. Authorised channel(s): {names}")
    if not any("Break The Routine" in n for n in names):
        print("WARNING: this is not the Break The Routine channel. Run again and pick the right account.")


if __name__ == "__main__":
    main()
