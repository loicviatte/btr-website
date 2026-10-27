# BTR bot — notes for Claude (dev mode)

You are running headless on the bot's own server, from a git clone of `loicviatte/btr-website`, inside `bot/`.
Loïc talks to you through Telegram (French, short, solutions). Your edits are deployed only when he presses
"Déployer": the bot commits `bot/` and pushes to `main`; the GitHub Action `.github/workflows/bot-deploy.yml`
rsyncs `bot/` to `/opt/btr-bot`, writes `.env` from repo secrets, reinstalls if `install.sh`/`requirements.txt`
changed, restarts the systemd service `btr-bot`, and rolls back automatically if the new version crashes at start.

## Map
- `btrbot/bot.py` — Telegram handlers, jobs (YouTube poll every 15 min, Drive SRT folder), buttons, dev mode routing.
- `btrbot/pipeline.py` — episode steps: transcript → 3 axes (title/quote) → frames → thumbnails → publish → chapters.
- `btrbot/prompts.py`, `btrbot/llm.py` — Claude prompts and API wrapper (model `claude-opus-5-5`).
- `btrbot/youtube.py` — YouTube Data API (same Google app as the website; scope youtube.force-ssl).
- `btrbot/frames.py`, `faces.py`, `imaging.py`, `render.py`, `templates/*.html` — frame scan (yt-dlp + cookies),
  face recognition (Marius vs guest), cut-outs (rembg) and LaMa top extension, Playwright rendering of the
  3 validated thumbnail templates (YouTube 1920×1080, Instagram 1080×1920, square 1080×1080). Brand rules:
  PP Monument Extended, quote 72/120/72 px (top left-aligned, key word big, bottom right-aligned), name 69 px
  #FCDF9A hard-light, gold haze behind the cut-out people.
- `btrbot/state.py` — per-episode JSON state in `data/episodes/<id>/` (live data: `/opt/btr-bot/data`).
- `btrbot/drive.py` — shared Drive folder of DaVinci SRTs; `btrbot/srt.py` — SRT parsing (DaVinci 01:00:00 offset).
- `btrbot/agent.py` — this dev mode. `btrbot/check.py` — `/check` health check.

## Rules
- Only change files in this folder. Never print or edit secrets / `.env`.
- Never write to a YouTube video that is already public (see `Pipeline._guard`).
- Keep the episode flow working end to end; check with `/opt/btr-bot/.venv/bin/python -m py_compile btrbot/*.py`
  and, when useful, `tests/simulate.py` (offline mocks).
- User-facing text in French. Keep changes small and in the existing style.
