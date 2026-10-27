"""Health check, run on the server after install:  python -m btrbot.check"""
import tempfile
from pathlib import Path

from .config import Settings


def step(name, fn):
    try:
        out = fn()
        print(f"✅ {name}: {out}")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"❌ {name}: {e}")
        return False


def main():
    cfg = Settings()
    from .youtube import YouTube
    yt = YouTube(cfg.youtube_token, cfg.channel_id, cfg.youtube_client)
    step("YouTube API", lambda: f"{len(yt.recent(10))} recent uploads, unlisted ready: {len(yt.unlisted_ready())}")
    refs: list = []
    step("Reference episodes", lambda: (refs.extend(yt.public_references(3)), [r["title"] for r in refs] or "none")[1])
    if refs:
        step("Captions download", lambda: (lambda t: f"{t[1]} track, {len(t[0] or '')} chars")(yt.caption_srt(refs[0]["id"])))

        def frame():
            from . import frames
            url = frames.full_res_url(refs[0]["id"], cfg.ytdlp_cookies)
            out = Path(tempfile.mkdtemp()) / "f.jpg"
            frames.grab(url, 600, out)
            return f"4K frame OK ({out.stat().st_size // 1024} KB)"
        if not step("Video download from this server (yt-dlp)", frame):
            print("   → add/refresh secrets/youtube_cookies.txt (see README), or use a residential proxy.")

    if cfg.drive_srt_folder:
        from . import drive
        step("Drive SRT folder", lambda: (lambda f: f"{len(f)} SRT: " + ", ".join(n for _, n in f[:5]))(drive.list_srt(cfg.drive_srt_folder)))

    import shutil
    import subprocess
    step("Claude Code (mode dev)", lambda: (subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.strip()
                                            if shutil.which("claude") else (_ for _ in ()).throw(RuntimeError("pas installé")))
         + (" · GitHub OK" if cfg.github_token else " · secret BOT_GITHUB_TOKEN manquant"))

    import anthropic
    step("Anthropic", lambda: anthropic.Anthropic(api_key=cfg.anthropic_key).messages.create(
        model=cfg.model, max_tokens=20, messages=[{"role": "user", "content": "Say OK"}]).content[0].text)

    import asyncio
    from telegram import Bot
    step("Telegram", lambda: asyncio.run(Bot(cfg.telegram_token).get_me()).username)

    step("Face models + Marius reference", lambda: (lambda f: "ready")(__import__("btrbot.faces", fromlist=["Faces"]).Faces(cfg.models_dir)))
    step("LaMa model", lambda: f"{(cfg.models_dir / 'big-lama.pt').stat().st_size // 2**20} MB")


if __name__ == "__main__":
    main()
