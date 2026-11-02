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
- Models (`llm.MODELS`, `usage.py`): chat Opus (Loïc 01.11: « un bot intelligent comme Claude »; was Haiku), creative Opus (axes, title, description), work Sonnet (chapters, frames),
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
  the reels himself on Instagram and TikTok. YouTube Shorts (`btrbot/shorts.py` planner, `bot.shorts_*`,
  `pipeline.short_upload`, `YouTube.upload_short/reschedule/statuses`): every filed reel is sent private with a
  publishAt, YouTube makes it public by itself; time = Loïc's choice (item["short_at"], tool shorts_schedule « short 2 le
  4.11 à 19h ») > ClickUp due date (18:00 London if no time) > already scheduled > next day without a Short; plan shown
  ClickUp is the trigger: statuses to generate → generated → approved (filed) → ready → scheduled → posted (`share.close_if_posted` after every platform mark, and the 10-min sweep in `bot.posts_refresh`: all planned platform fields Posted = status posted; carousels / stories validated with a date = scheduled; Atlas catch-ups the bot will post = scheduled); Loïc
  validates a cover (« ✅ Cover OK » on the cover, tool covers_ok) → task « ready » (`bot.covers_ok`); `bot.shorts_watch`
  (every poll + right after) schedules ready reels, then the task goes « scheduled » (YouTube only for now); a date changed
  in ClickUp moves a waiting Short; a new cover puts the task back to approved; re-filing never moves a task back from
  ready/scheduled/posted. ClickUp times are kept (date-only = 18:00 London, `shorts.due_at`). /shorts (tool shorts_plan)
  shows the plan; YouTube field Scheduled → Posted (`shorts_sync`), Short link in the task, the bot's own « Short · »
  task gets the publishing time as due date (Drive file renamed). A public Short is never touched again.
  Related video can't be set by the API (Loïc in Studio). Test: `tests/shorts_flow.py`.
  Instagram (`btrbot/instagram.py`, Graph API with Facebook Login v23.0, no third party): connected with /connect (Loïc
  pastes « app_id app_secret EAA-token » from the Graph API Explorer; `instagram.connect` keeps the never-expiring
  Page token + IG id, or, when the app can't get pages_show_list (BTR - Short), finds the Page / IG ids in the token's
  grants (debug_token) and keeps the long-lived user token (ig_kind user, 60 days, `ig_tick` warns 7 days before);
  message deleted, scrubbed from MEMORY). A feed reel (item["instagram"]) whose Short is scheduled
  is posted by the bot at the same time: `bot.ig_tick` every minute; ~45 min before = `pipeline.ig_prepare` (container,
  resumable upload of the local file, caption, collaborators = captions["collab"], cover_url = Drive direct link,
  retried without cover; ClickUp « Instagram placement » Grid = share_to_feed, else Reels tab only), at the time =
  `pipeline.ig_publish` (container already PUBLISHED = no double post); ClickUp Instagram field Scheduled → Posted,
  link in the task; 3 failures or >12 h late = Loïc posts it himself; not connected = one warning; container retried
  without cover, then without collaborators. Guest's @: `share.HANDLES` + data/handles.json (`load_handles`/`set_handle`,
  "" = no Instagram); unknown → `bot.ask_handle` (at « Ranger » with feed reels and at cover OK: Sonnet + web search
  `llm.guest_instagram`, buttons igh:ok / igh:none, or Loïc types the @ → `handle_reply`; tool guest_instagram);
  `share.apply_handle` puts « @handle on … » in the Instagram caption + collab [guest, mariusiepure], applied again at
  posting time. /igtest = dry run on the next IG reel (container only, kept if still fresh). Test: `tests/ig_flow.py`.
  TikTok (semi-auto until the API audit): `bot.tt_tick` every minute; at the Short's time it sends the video, the cover
  and the TikTok caption (<pre>, tap to copy) with « ✅ Posté sur TikTok » (ttok:vid:n → `tt_posted`); ClickUp TikTok
  field Scheduled → Posted. Test: `tests/tt_flow.py`.
  TikTok API (`btrbot/tiktok.py`, Content Posting API Direct Post, app « BTR Studio »): /connect → Loïc pastes « tiktok
  CLIENT_KEY CLIENT_SECRET », then the authorisation link → breaktheroutinepodcast.com/tiktok/callback (site page
  app/tiktok/callback, shows « tiktok CODE ») → pasted back (`on_secret`, message deleted); access token 24 h refreshed,
  refresh 365 days. /tiktok [n] = composer (`tt_compose` / `tt_card` / `on_tt_button`, TikTok UX rules: account, video,
  caption, audience picked by Loïc from creator_info (nothing pre-selected), comments / duet / stitch (🚫 when the account
  disables them), commercial content (your brand / branded content, never private), Music Usage / Branded Content
  declaration, « Confirmer pour l'heure prévue » or « Publier maintenant »); a confirmed reel is posted by `tt_publish`
  at the Short's time (FILE_UPLOAD, status polled; failure = back to the notification). Unaudited app = private posts:
  « /tiktok en » / « /tiktok fr » = TikTok screens (and /connect, TikTok part only) in English for the review demo (`T`).
  « 📥 Envoyer en brouillon » = Upload (video.upload, `tt_draft`, inbox draft). The composer is only sent with /tiktok until the audit; site pages /terms and /privacy (BTR Studio section) for it. Three steps: 1) ✅ Valider / 🗑 Jeter on each preview (nothing filed);
  2) once every ticked reel is decided, `maybe_dispatch` asks which ones also go on the Instagram feed (buttons rfeed,
  tick order = publishing order; also at boot and after /connect); 3) « Ranger » (rfile / tool reels_file) = `file_reels`:
  for each reel (feed ones first), cover (`pipeline.reel_cover`: sharp 4K guest stills kept at render time in
  `reels/rNN/cover/` (`reels.cover_search`: face sharpness, size, height), the best chosen by Sonnet against the approved
  cover `assets/cover_ref.jpg`; « de meilleurs screenshots » = tool reels_cover_search → `pipeline.reel_cover_search`
  downloads the moment again and samples it every 0.33 s; every search avoids stills already shown (cover/seen.json)
  and gives half mouth open / half mouth closed (Haiku on `render.mouth_sheet`); every cover is checked for the
  Instagram profile grid (`render.grid_check`: whole head (hair top = cy − HAIR 0.85, chin = cy + CHIN 0.5 face heights) + AIR 40 px
  inside the 3:4 crops (centre 240-1680 = Instagram, top 0-1440), hook inside the centre crop; `cover_box` frames close (Loïc 30.10: head = FILL 820 px of the 1920 cover, never closer
  than 28 % of a 4K frame, sharpened) with the hair top at 240 + AIR; the hook starts TEXT_GAP under the chin (template
  top, moved up only if it would leave the grid tile) and the dark / gold veils follow it;
  the picker skips photos that fail; a chosen photo without room gets the set generated above the head by LaMa,
  `pipeline._cover_air`; IG re-uploads if the cover changed after the container, `bot.cover_sig`) and sent with `render.grid_preview` (9:16 + both 3:4 crops); hook = consecutive words really said, template
  `templates/reel_cover.html` = the validated « They just DON'T CARE. » cover), then `pipeline.reel_share` (`share.py`):
  ClickUp place first, then Drive (scope drive.file, folder « BTR Reels / <guest> », files named
  MMDD_EPn_GUEST_FEED|SHORTS_TITLE.mp4 + _COVER.jpg, MMDD = due date of the ClickUp task else today, EP numbers in
  `share.EP_NUMBERS` + data/ep_numbers.json (new guest = next number); file ids kept so a re-file renames/moves the same
  file; bump `bot.REELS_FILES` to re-file validated reels at boot; viewable by link), then the ClickUp task
  (list « Content calendar »; the feed question lists the episode's free Instagram slots; feed → the next free « Reel k/N »
  slot, else a new « Reel · … » task; TikTok + Shorts only → a new « Short · … » task (Instagram field Not planned);
  changing the choice later (reel_validate instagram=…) gives the slot back / deletes the bot's own task; renamed, status approved,
  description block below « ———— BTR Studio ———— » with links + captions (plain paragraphs), cover attached). `bot.reels_context` tells the chat model which reels are filed (where, task, file) and when all are, so it never announces feed buttons that won't come.
  Captions (`pipeline.reel_captions`, bump `CAPTIONS_V`; filed reels get new ones via `bot.REELS_FILES` at boot) =
  the format approved on the first Oti reel, assembled by code from the model's pieces (hook / topic / quote /
  question, quotes checked as really said): “hook” / « @handle on topic: “quote” » / « question Tell us in the
  comments. » / « Part N of Break The Routine with Guest is out now on YouTube and Spotify. Link in bio. »; TikTok =
  full name + hashtags; Shorts = title « Guest: “hook” | Break The Routine » + description without link; no emoji;
  Instagram handles in `share.HANDLES` (collab invite guest + @mariusiepure). Both are connected from
  Telegram with /connect (Google address pasted back, ClickUp pk_ token pasted; secrets in data/secrets.json, never
  sent to the chat model). Tool reel_cover (other photo / other words / zoom 0.6-1.5 (below 1 = wider): face["zoom"] in `render.cover_box`, kept in item["cover_zoom"] for that photo; fast path « reel 5 photo 11 zoom 1.25 »). Tests: `tests/reel_offline.py` (render), `tests/reel_flow.py` (Telegram), `tests/reel_pages.py` (pages), `tests/reel_layout.py` (placement replayed on the real reels), `tests/reel_framing.py` (zoom), `tests/reel_cover.py` (cover), `tests/reel_share.py` (ClickUp slot, description), `tests/reel_names_timing.py` (word visibility, sentence seams, name fixes).
- Carousels & stories (Loïc 31.10; rules: claude/btr-carousels-workflow.md + btr-stories-workflow.md in the Claude
  project; templates = the validated Oti2-Moment / Oti2-Topics / Oti2-Stories canvas pages ported to `templates/posts.html`,
  same positions, texts shrink with window.fit): `btrbot/posts.py` (pure: ClickUp task names → kinds, shot needs,
  pages, captions, placement, zone previews, render) + `btrbot/postmaker.py` (Maker: plan from the episode's ClickUp
  tasks « Carousel · Key moment / Topics · Ep … », « Story · Poll / Rapid fire / The Chain / Link / Ask the next guest /
  Question / answer / Quote / Atlas quiz / Teaser share · … » in « to generate » (or the bot's own, MARK); the 3-episode
  CYCLE only when the episode has NO such task in any status (`Maker.episode_tasks`); a post asked by kind is linked to
  its task even if made by hand, and `Maker.file` links a validated post to its task if it wasn't; content = one Opus call (prompts.POSTS, every EXACT field checked with said_exactly, one fix retry,
  times pinned by posts.find_time); shots = 720p scan copy sampled every 2 s, classified guest / marius / both / wide /
  noface (cache posts_scan.json), eyes checked (Haiku), 4K grab; The Chain = previous guest's close-up from the end of
  their episode; render; file = Drive « BTR Posts / <guest> » (public links) + ClickUp block below MARK, status ready).
  State: data/episodes/<id>/posts.json. Bot (topic « stories »): /posts [lien] [kind…], auto after « chapters_ok »,
  tools posts_make / post_feedback / posts_validate / posts_status (validated: Drive folder + planned time) / posts_show
  (`bot.posts_show`: sent again as is, validated = images downloaded from Drive, no state / ClickUp change); previews (carousel album + IG caption; story = file
  + Instagram zones) with ✅ Valider / 📷 Autres photos (carousels: pick the slide, ↑/↓ for the Key moment's two photos → `bot.posts_photos`, only those photos change, `Maker.shots(redo=, want=)`; tool post_photos with slides / part / at / who) / ✍️ Autres textes / 🔀 Version b. Faces are measured again on the 4K photos (`Maker.refine`) and the person checked (`Maker.right_person`: never Marius for the guest); The Chain picks the guest's photo with the previous guest's face size (need fh, `posts.pick`); post_photos = ANOTHER photo (size smaller/bigger = a face 0.72x / 1.35x); post_zoom = SAME photo, factor <1 wider (`posts.place` lets the photo be smaller than its frame, `Maker.fill_gaps` + `imaging.fill_out` generate the set around with LaMa, cached in shot["ext"] per framing) or previous=true (st.data["history"]) or shift_x / shift_y (shot["shift"], fractions of the frame, « plus bas / à
  gauche », same photo, uncovered set generated the same way); pairs (The Chain, Q/A) take the SMALLER face's size (`posts.pair_zoom`); text feedback keeps the photos whose moment didn't move: side-by-side stories match face size and eye line (`posts.pair_place`, the photo may move up to 30 % past its frame
  edge, `place(free_y=)`, so the heads are level even when the 16:9 photo exactly fills the frame). `posts_tick` (60 s): at the
  task's time, carousels + Question/answer + Quote stories by the Instagram API (container 20 min before, Drive direct
  links), sticker stories / no API = files + ready-to-copy text sent to Loïc with « ✅ Posté » buttons; carousels
  (episode + World Atlas) on TikTok (Loïc 02.11: he adds the music and posts himself) = `bot.tt_photo_draft` 10 min
  before tt_at (ClickUp « HH:MM TikTok » line, else the Instagram time; TikTok field « Not planned » = none):
  `TikTok.photo_draft` (MEDIA_UPLOAD photo, Drive images in slide order pulled through the verified site,
  `tiktok.photo_url` → site route /api/tt-photo), caption to copy in Telegram, images only if it failed; it["tt"]["draft"],
  never a direct post nor a ClickUp change (Loïc taps « ✅ Posté sur TikTok »); >12 h
  late = never posted, Loïc told once; `posts_refresh` (10 min) follows ClickUp dates. World Atlas catch-ups
  (`atlas_tick`, images + captions from btr-media): approved / ready = posted by the API at their time, then Loïc gets
  the music to add in the app (Modifier → Ajouter de la musique works after posting, tested 01.11); episode carousels
  too when their task has a « Music: » line. Test: `tests/posts_flow.py [--render]`.
- Telegram group « BTR Studio » (`btrbot/topics.py`, Loïc 31.10): Loïc writes in a forum group where the bot is admin →
  `bot.register_group` keeps it (data/topics.json) and creates the topics 🎬 Reels & covers / 🖼️ Miniatures épisode /
  📚 Stories & carrousels (General = system). `ExtBot._do_post` is patched: every send* to Loïc's private chat goes to
  the group, in the topic of `topics.TOPIC` (context variable). `bot.set_origin` (handler group -1) sets it from the
  incoming message's topic (private chat = stays private: secrets, /connect); the reel / Shorts / IG / TikTok functions
  are wrapped « reels », the episode thumbnail / chapter ones « thumbs » (`topics.assign` at the end of bot.py — a new
  function that sends reel or thumbnail messages goes in that list). One chat memory per topic (`TopicMemory`,
  `MEMORY.everything()` to scrub secrets). In the group only Loïc drives the bot (`allowed`). Test: `tests/topics_flow.py`.
- « ✅ À valider » topic (`btrbot/dashboard.py`, Loïc 01.11): ONE message per episode (reels.json / posts.json touched in
  the last 21 days + the active episode), edited in place by `bot.dash_tick` (30 s, only when the text changes;
  reg.data["dash"][vid] = message id + signature). No buttons: tappable /commands like BotFather, per episode code
  (`dashboard.episode_code`: oti2, kiera…, reg.data["dash_codes"]): /oti2_reel3 (preview or cover sent again in Reels),
  /oti2_topics, /oti2_poll… (in Stories), /oti2_miniatures, /oti2_faire_poll (a ClickUp task « to generate » → made);
  `bot.on_dash_cmd` deletes the command message. Lines: miniatures (ep.stage), reels (⏳ preview / cover to validate,
  📅 Short planned, 🟢 published), carousels + stories = the episode's ClickUp tasks (`bot.ep_tasks`, cache CU_CACHE 5 min,
  release date cached in ep["release_at"] for « Ep Nov 3 » names) merged with the bot's items (an item whose kind has no task is hidden when the episode has tasks): ClickUp « posted » or
  bot posted = 🟢 locked (no command, edits refused), to generate ⬜. Topic created at boot for an existing group
  (`ensure_dash_topic`). Only the overviews stay: any other bot message routed there (`_routed_post`, DASH_KEEP
  marks the overview) and Loïc's own messages (`set_origin`) are deleted after DASH_TTL 40 s (`dash_forget`).
  Test: `tests/dash_flow.py`.
- « 🗓️ Instagram planning » topic (Loïc 01.11): Loïc changes the ClickUp calendar by chat; tools planning_list (CU_CACHE
  refreshed, « id · name · status · date »), planning_change (task_id, new_type and/or when: renamed with
  `posts.task_name`, Time line / description from `posts.task_desc`, status « to generate », the old kind's draft dropped,
  content made again via posts_make([kind]) when the task belongs to an episode the bot has (`bot.episode_of_task`);
  carousel ↔ story refused; posted = locked), planning_add (type, when, like_task_id or label: new task with Format /
  Instagram / placement / TikTok / YouTube fields), planning_remove (ClickUp trash, never posted). Dates « 4.11 19h »,
  « 11h » (`bot.plan_when`). « À valider » follows on its next tick. Topics added later are created at boot
  (`ensure_dash_topic` loops over topics.NAMES). Test: `tests/planning_flow.py`.
- Its overview (Loïc 01.11): ONE message on top, edited by dash_tick (`plan_overview_tick`, reg.data["planning_msg"]):
  every post still to go out THIS WEEK, Tuesday (episode day) → Monday (`plan_week`), ALL platforms (reels, carousels,
  stories, Shorts, YouTube Community, World Atlas…), grouped by day, 📸 / ▶️ per platform, late ones flagged
  (`dashboard.planning_overview`, `ig_kind`); the header names the episode in progress (`plan_current_ep`). Topic
  renamed « 🗓️ Posts planning ». Every other message there (Loïc's and the bot's) is noted (`plan_forget`,
  reg.data["plan_msgs"]) and the whole exchange is deleted PLAN_TTL (90 s) after its last message; kept while Loïc's
  request waits for its answer (≤ 15 min).
  Test: `tests/planning_overview.py`.
- Stress pass (01.11, `tests/planning_stress.py`): « À valider » deletions are kept in reg.data["del_queue"] and done by
  `del_tick` (10 s), so a restart no longer leaves messages behind; the planning sweep waits while the chat model is
  still working on a request from that topic (`PLAN_BUSY`, set in `ask_assistant`, max 30 min); an overview edit that
  fails for a passing reason (timeout) is retried next tick instead of posting a duplicate (`gone_msg`); late posts
  show the platforms still open (`plan_missing`, from the ClickUp Instagram / TikTok / YouTube fields) and a tappable
  `/fait_<task id>` (`plan_mark_done`: those fields → Posted, status posted; refused for a post not yet due); the
  overview is capped under Telegram's 4096 chars; `run()` passes keyword arguments.
- Validated content linked to its task AFTER the validation (01.11: « Posts planning » switched the Ask task to The
  Chain, whose content was already validated → task stayed « to generate »): `posts_file_linked` files it (Drive,
  description, images, « scheduled »); called by posts_make when there is nothing to make, and by the posts_refresh
  sweep for any validated item whose task still says « to generate » / « generated ».
- Questions about texts (Loïc 01.11): tools `transcript_search` (query → matching SRT passages with timecodes and
  context, or at=« 34:12 »; guest « Oti P2 » / link, else the episode of the posts / reels in progress; `srt.search`) and
  `post_texts` (the exact texts of a carousel / story: content + captions + sticker). topic_context_base tells the model
  a question gets an ANSWER citing the transcript, nothing redone unless asked. Test: `tests/transcript_tools.py`.
- Teaser (Loïc 01.11: « 4-5 moments clés montés ensemble, à la fin un écran episode out now »): `pipeline.teaser_moments`
  (Opus, prompts.TEASER_MOMENTS: 3-9 s lines, hook first, no spoiler; each start found with `srt.find_quote_start`, end
  with find_quote_end) → `pipeline.render_teaser`: each moment = a reel render (`render_reel` with n = TEASER_N + start
  second, work dir `teaser/mNNNNN` via `reel_work`, no cover search; a moment whose start/end/words didn't change is
  reused, seg.json), then concat (short audio fades) + end screen `templates/teaser_end.html` (`render.teaser_end`: last
  frame blurred, logo, PART n, name, EPISODE OUT NOW, platforms, link in bio; above Instagram's bottom UI) 3.5 s. State
  `teaser.json`. Bot (topic reels): /teaser [lien], tools teaser_make (feedback keeps the previous moments in the request)
  / teaser_show, buttons tz:ok / tz:redo. Not wired yet: Drive + ClickUp « Reel teaser » task + publishing. Test:
  `tests/teaser_flow.py`.
- Server logs without SSH: push anything to the branch `bot-logs` → workflow « Bot logs » (journal last 6 h with the bot token and secrets masked, posts.json summary). httpx INFO logs are off (they carry the token in the URL).
- `btrbot/agent.py` — this dev mode. `btrbot/check.py` — `/check` health check.

## Rules
- Only change files in this folder. Never print or edit secrets / `.env`.
- Never write to a YouTube video that is already public (see `Pipeline._guard`).
- Keep the episode flow working end to end; check with `/opt/btr-bot/.venv/bin/python -m py_compile btrbot/*.py`
  and, when useful, `tests/simulate.py` (offline mocks).
- User-facing text in French. Keep changes small and in the existing style.
