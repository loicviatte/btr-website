# New episode → website (runbook for the scheduled Claude task)

The GitHub Action `.github/workflows/new-episodes.yml` checks YouTube every 2 hours. For each **public** upload
**longer than 15 minutes** that is not on the site yet, it saves `data/incoming/<videoId>/` with `meta.json`,
`thumb.jpg` and `captions.srt`. This runbook turns those folders into pages and puts them online.
Loïc chose **direct publishing**: no review step, so check carefully before pushing.

## 0. Is there anything to do?
```
cd btr-website && git pull
ls data/incoming/*/captions.srt   # a folder WITH captions.srt and WITHOUT a "done" file = to process
```
A folder without `captions.srt` is not ready yet (no SRT in Drive and YouTube is still making the captions): leave it,
the Action retries. `meta.json` → `captionsSource`: `drive` = Loïc's DaVinci SRT from the shared Drive folder
BREAKTHEROUTINE/SRT (best quality, names spelled right; `srtDriveId`/`srtName` say which file), `youtube` = YouTube's.

Also, on every run, fill Atlas cards that still say "coming soon" once the Instagram carousel research exists:
```
git clone -q https://github.com/loicviatte/btr-media.git ../btr-media   # public repo, read only
python3 tools/auto/btr_auto.py atlas-sync ../btr-media
```
If it filled something: compile, build, smoke test (any existing slug), commit "Atlas: <country> cards", push.
Also, once a day (when `data/stats/metricool.json` has an older `date` than today), refresh the About > Partners
figures. Metricool (brandId `7665642`, `getAnalyticsDataByMetrics`, `to` = now):
- (YouTube: `data/stats/youtube.json`; the average counts only full episodes out for 7+ days.)
- `IGEV01`, `TKEV07`, `YTEV01` from 7 days ago → the latest non-null value of each = Instagram followers, TikTok
  followers, YouTube subscribers;
- `IGRE01`, `IGRE06`, `IGRE23` from `2024-01-01` → one row per reel `[date, url, views]`;
- `TKPO01`, `TKPO03`, `TKPO07` from `2024-01-01` → one row per TikTok video (often empty: fine).
- `IGRE06`, `IGRE05` from `2024-01-01` → `[reel url, cover image url]` rows: save them as `reelCovers`; the GitHub
  Action uses them to fill reels without a cover on the episode pages (`tools/auto/reel_covers.py`).
Write them to `data/stats/metricool.json` as `{"date": "<YYYY-MM-DD>", "instagramFollowers": n, "tiktokFollowers": n,
"youtubeSubscribers": n, "reels": [rows], "tiktokVideos": [rows], "reelCovers": [rows]}` (rows exactly as returned), then
`python3 tools/auto/btr_auto.py stats`. YouTube views come from `data/stats/youtube.json` (the Action), Spotify from
`data/stats/base.json` (by hand). If it prints "About updated": compile, build, smoke test, commit
"About: figures <date>", push. Always commit `data/stats/metricool.json` (no deploy for it alone).
Metricool failing is not a reason to stop: the figures stay as they are.

Nothing to process, nothing synced and no figures changed → stop, say nothing.

Process folders in publishing order (oldest `publishedAt` first), one at a time, steps 1 to 6 each.

## 1. Read the episode
- `meta.json`: title, description, publishedAt, durationSec.
- `python3 tools/auto/btr_auto.py srt data/incoming/<vid>/captions.srt > /tmp/t.json` → transcript passages.
- `python3 tools/auto/btr_auto.py chapters data/incoming/<vid>/meta.json` → chapters from the description
  (empty list if the description has none).
- Read the whole transcript. Who is the guest? Is this a **new guest** or **another part** of an existing guest
  (title says "Part 2", or the guest is the one on the latest page and the conversation continues)?

## 2. Write the spec: `data/episodes/<slug>.json`
Format: see the docstring at the top of `tools/auto/btr_auto.py`. Rules:
- `slug`: guest name in lowercase with hyphens, accents removed (`oti-mabuse`). `initials`: 2 letters.
- `pronoun`: she / he / they, from how Marius talks about them.
- `bio`: one sentence, facts said in the episode only (career, titles, where from). Same tone as existing bios.
- `about`: two paragraphs. 1) "In this episode, Marius Iepure sits down with <Name>, <who they are>, for …".
  2) "They talk about …" listing the real topics in order. No hype, no invented facts.
- `teaser`: one sentence for the home page, "<Name> on …".
- `parts[0]`: `vid`, `title` (YouTube title, cleaned of " | Break The Routine" etc.), `date` ("4 Nov 2026" from
  publishedAt), `secs` (durationSec), `thumb` (`python3 tools/auto/btr_auto.py thumb data/incoming/<vid>/thumb.jpg`),
  `chapters` (from the description; if none, write 12–25 chapters from the transcript: English, 3–8 words,
  SEO-friendly, no hyphens, no first-person host voice, first one at 0 = "Intro"), `transcript` (the passages from step 1).
- `chain.answers`: the question the previous guest left (find where Marius reads it out; `sec` = the moment the
  question is read; `from`/`fromSlug` = previous guest). The previous guest's question is on their page / in
  design/Chain.dc.html `qs`. Null if it is not in this part.
- `chain.leaves`: the question this guest records for the next guest (text + `sec`). Null if not in this part.
- `atlas`: the country the guest lands on when opening the World Atlas (`country`, `slug`, `sec` = the draw).
  Null if there is no draw. If the map uses another name (e.g. "Dem. Rep. Congo"), add `mapName`.
- `playlist`: the guest's song for the Break The Routine playlist (Marius asks "what's your favorite song to dance to
  right now… we'll add it to our playlist"): `{"title", "artist", "sec", "part"}`, `sec` = when Marius asks. Check the
  exact title and artist on the web (auto captions mangle names: "Mekka" was "Manteca", "Gamella" was Kamo Mphela) and
  write them as Spotify shows them. If the guest names no clear song, leave `playlist` out and say so to Loïc.
  `apply` puts it in the episode sidebar and in the home page list; Loïc adds it to the Spotify playlist himself.
- `atlasCards`: leave it out. The site shows a "coming soon" card for the new country; the Instagram carousel task
  (step 6) does the researched, fact-checked slides, and `atlas-sync` copies them to the site.
- Part 2: `"addPartTo": "<existing slug>"`, `parts` = only the new part; give `chain`/`atlas` found in this part.

## 3. Apply
```
python3 tools/auto/btr_auto.py apply data/episodes/<slug>.json
```
This creates/updates: the episode page, Episodes list, Search index, previous guest's links, home page (hero,
previous episodes, chain teaser, World Atlas card), The Chain and the World Atlas.

Then `python3 tools/auto/btr_auto.py atlas-sync ../btr-media` (in case the carousel already exists).

## 4. Check
```
npm ci   # first time in a fresh checkout
npm run compile && npm run build && node tools/auto/smoke.js <slug> "<Name>"
```
Fix anything the smoke test reports. Then look at the new episode page, the home page, /chain and /atlas
(Playwright screenshots, desktop and phone). Typical things to fix by hand in design/*.dc.html: a missing
chain answer timestamp, a guest crop (`imgPos`), wording.

## 5. Publish
```
touch data/incoming/<vid>/done
git add -A && git commit -m "New episode: <Name> — <title>" && git push
```
Pushing to `main` deploys the site (Vercel). Footer credit, the Ask page (never linked) and fonts are untouched.

## 6. Hand the country to the Instagram carousel task
Only when the episode has a World Atlas draw (and it is a new country for this guest):
1. If `meta.json` says `captionsSource: drive`, the SRT is already in that Drive folder: use `srtDriveId`, don't upload.
   Otherwise upload the captions to the Drive folder the carousel task watches (Google Drive connector, `create_file`):
   title `<YYYY-MM-DD> <Guest> - <episode title>.srt`, `parentId` `1OF0ALQxvNZb2Qc5TqYURbx04BDe4Kk5-`
   (BREAKTHEROUTINE/SRT), `textContent` = the captions.srt text, `contentMimeType` `text/plain`,
   `disableConversionToGoogleType` true. Keep the returned file id.
2. Only if Loïc has the carousel task switched on (`list_triggers`: "BTR World Atlas auto-carousel" `enabled: true`; he pauses it
   when he prefers to run it himself): start it now (`fire_trigger`, trigger `trig_0151tdHEtCDERz4pbqP4nJDi`, "BTR World Atlas auto-carousel")
   with text: `Signal du site BTR : nouvel épisode « <title> », guest <Name>, publié le <date>. Pays tiré (vu par
   le site) : <country>, à <m:ss> dans la vidéo <url>. SRT dans Google Drive BREAKTHEROUTINE/SRT, file id <id>.`
   It researches and verifies the 8 slides, adds them to the BTR Designs canvas, sends Loïc the images and captions
   (no scheduling: Loïc publishes himself). Its verified research then fills the site's Atlas cards through atlas-sync
   on a later run of this task.
If the task is paused, don't start it: tell Loïc the SRT is in Drive, ready for him to launch the carousel.
If uploading or firing fails, say so in the message to Loïc.

## 7. Tell Loïc (in French, short)
What went online (guest, episode page link `https://www.breaktheroutinepodcast.com/episodes/<slug>`), the chain
question, the country picked, the playlist song to add on Spotify, and anything uncertain (e.g. "pas trouvé la question de la Chain").

If something fails and can't be fixed safely: don't push, leave the folder without `done`, and tell Loïc what
blocked.
