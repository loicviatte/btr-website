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
- Conversation: `btrbot/assistant.py` — Haiku with ~22 tools (`assistant.TOOLS`), handlers in `bot.tool_handlers`. Every free-text
  message / screenshot goes to `bot.ask_assistant`; heavy jobs start in the background with `bot.bg` (one at a time, LOCK).
  `assistant.Memory` keeps the chat (Loïc + everything the bot posted). Add a capability = a tool + a handler, not a regex.
  Exact « titre: / citation: / part: / description: » stay instant fast paths. `tests/stress.py` = 30 real-model scenarios
  (workflow « Bot stress test », runs after a deploy whose commit message contains [stress]).
- Models (`llm.MODELS`, `usage.py`): chat Haiku, creative Opus (axes, title, description), work Sonnet (chapters, frames),
  vision_cheap Haiku (eyes). Every call is logged with its cost in `data/usage.jsonl` (/couts). Claude Code: Opus, fresh session.
- PART badge: `templates/_part.html` (top right, white PART + gold number), on all 3 formats via `pipeline.part_number(ep)`; on any existing YouTube thumbnail via `Pipeline.badge_thumbnail` + `/badge` (preview, then Loïc's go; allowed on public videos, thumbnail only).
- Reels (workflow: claude/btr-reels-workflow.md in the Claude project): `btrbot/reels.py` (section download in 4K,
  word timings with Parakeet via sherpa-onnx in `models/`, silence cuts, shot-by-shot framing from the source edit:
  guest / Marius close-up 9:16 alternating wide/tight at jump cuts, wide shot of both → split screen guest top /
  Marius bottom, frame-exact render, −14 LUFS, no music; the tight zoom never cuts the head: `reels.single_box`, bump
  `reels.FRAMING` when the picture changes so kept edits are made again), `btrbot/subs.py` (v3 subtitles as ASS: Regular/Heavy,
  gold, italic, tighten; words only from the transcription, never added), state in `data/episodes/<id>/reels.json`
  (`state.Reels`, one shared object per process). Telegram: `/reels [lien]`, list of 10 moments with tick buttons,
  previews with ✅/🗑, tools reels_propose / reels_select / reel_adjust / reel_subtitles / reels_resend / reel_validate /
  reel_drop. Subtitle pages: 4 lines max (`subs.cap_lines`), never an expression cut between pages (`keep_phrases`),
  no sentence tail on the next sentence's page (`sentence_seams`, and `cap_lines` never cuts there: `_seam_ok`), Loïc's
  « keep X together » forced last (`keep_together`, item["together"] from the feedback tool; layout notes accumulate in
  item["sub_note"]), dropping keeps the files (« ↩️ Annuler » / tool reel_undrop), flash pages merged (`merge_flashes`), every word
  readable ≥ MIN_SEEN 0.5 s (`timeline` delays the next page, `appear`, checked by `visibility` → preview warning);
  proper nouns checked once per edit by `pipeline.reel_names` (Sonnet + server web search, context = title, YouTube
  description, chapters; a fix must sound like the heard word; cached in edit.json["names"], shown in the preview),
  placement (`vary` + `place`: mostly centred, 2 pages off-centre every 8 (l / r / lower / stair), a page never starts below the last word of the previous one nor in the bottom third). A restart resumes interrupted reels; when the reel rules
  change, bump `bot.REELS_RULES` so Loïc gets one « Renvoyer les reels » button after the deploy. Loïc publishes
  the reels himself: the bot never posts them. Three steps: 1) ✅ Valider / 🗑 Jeter on each preview (nothing filed);
  2) once every ticked reel is decided, `maybe_dispatch` asks which ones also go on the Instagram feed (buttons rfeed,
  tick order = publishing order; also at boot and after /connect); 3) « Ranger » (rfile / tool reels_file) = `file_reels`:
  for each reel (feed ones first), cover (`pipeline.reel_cover`: sharp 4K guest stills kept at render time in
  `reels/rNN/cover/` (`reels.cover_search`: face sharpness, size, height), the best chosen by Sonnet against the approved
  cover `assets/cover_ref.jpg`; « de meilleurs screenshots » = tool reels_cover_search → `pipeline.reel_cover_search`
  downloads the moment again and samples it every 0.33 s, hook = consecutive words really said, template
  `templates/reel_cover.html` = the validated « They just DON'T CARE. » cover), then `pipeline.reel_share` (`share.py`):
  ClickUp place first, then Drive (scope drive.file, folder « BTR Reels / <guest> », files named
  MMDD_EPn_GUEST_FEED|SHORTS_TITLE.mp4 + _COVER.jpg, MMDD = due date of the ClickUp task else today, EP numbers in
  `share.EP_NUMBERS` + data/ep_numbers.json (new guest = next number); file ids kept so a re-file renames/moves the same
  file; bump `bot.REELS_FILES` to re-file validated reels at boot; viewable by link), then the ClickUp task
  (list « Content calendar »; the feed question lists the episode's free Instagram slots; feed → the next free « Reel k/N »
  slot, else a new « Reel · … » task; TikTok + Shorts only → a new « Short · … » task (Instagram field Not planned);
  changing the choice later (reel_validate instagram=…) gives the slot back / deletes the bot's own task; renamed, status approved,
  description block below « ———— BTR Studio ———— » with links + captions, cover attached). Both are connected from
  Telegram with /connect (Google address pasted back, ClickUp pk_ token pasted; secrets in data/secrets.json, never
  sent to the chat model). Tool reel_cover (other photo / other words). Tests: `tests/reel_offline.py` (render), `tests/reel_flow.py` (Telegram), `tests/reel_pages.py` (pages), `tests/reel_layout.py` (placement replayed on the real reels), `tests/reel_framing.py` (zoom), `tests/reel_cover.py` (cover), `tests/reel_share.py` (ClickUp slot, description), `tests/reel_names_timing.py` (word visibility, sentence seams, name fixes).
- `btrbot/agent.py` — this dev mode. `btrbot/check.py` — `/check` health check.

## Rules
- Only change files in this folder. Never print or edit secrets / `.env`.
- Never write to a YouTube video that is already public (see `Pipeline._guard`).
- Keep the episode flow working end to end; check with `/opt/btr-bot/.venv/bin/python -m py_compile btrbot/*.py`
  and, when useful, `tests/simulate.py` (offline mocks).
- User-facing text in French. Keep changes small and in the existing style.
