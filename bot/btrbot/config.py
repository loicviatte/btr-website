"""Settings, read once from the environment (.env next to the project)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _req(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise SystemExit(f"Missing {name} in .env")
    return v


class Settings:
    def __init__(self) -> None:
        self.telegram_token = _req("TELEGRAM_BOT_TOKEN")
        self.data_dir = Path(os.environ.get("DATA_DIR", ROOT / "data"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # Only this chat may talk to the bot. If TELEGRAM_CHAT_ID is empty, the first chat that
        # sends /start becomes the owner (saved in data/chat_id).
        self.chat_file = self.data_dir / "chat_id"
        saved = self.chat_file.read_text().strip() if self.chat_file.exists() else ""
        self.chat_id = int(os.environ.get("TELEGRAM_CHAT_ID", "") or saved or 0)
        self.anthropic_key = _req("ANTHROPIC_API_KEY")
        self.model = os.environ.get("ANTHROPIC_MODEL", "claude-opus-5-5")
        self.channel_id = os.environ.get("YOUTUBE_CHANNEL_ID", "UCPTfscPkr0Div6di8S3IX9w")
        # Same Google app + refresh token as the website's GitHub Action (scope youtube.force-ssl)
        self.youtube_client = (os.environ.get("YT_CLIENT_ID", ""), os.environ.get("YT_CLIENT_SECRET", ""),
                               os.environ.get("YT_REFRESH_TOKEN", ""))
        self.youtube_token = Path(os.environ.get("YOUTUBE_TOKEN_FILE", ROOT / "secrets" / "youtube_token.json"))
        self.ytdlp_cookies = Path(os.environ.get("YTDLP_COOKIES", ROOT / "secrets" / "youtube_cookies.txt"))
        self.models_dir = Path(os.environ.get("MODELS_DIR", ROOT / "models"))
        # shared Drive folder where the DaVinci SRTs are dropped (link-shared, read without login)
        self.drive_srt_folder = os.environ.get("DRIVE_SRT_FOLDER", "1OF0ALQxvNZb2Qc5TqYURbx04BDe4Kk5-").strip()
        self.poll_minutes = int(os.environ.get("POLL_MINUTES", "15"))
        self.host_name = os.environ.get("HOST_NAME", "Marius Iepure")


ASSETS = Path(__file__).resolve().parent / "assets"
TEMPLATES = Path(__file__).resolve().parent / "templates"
