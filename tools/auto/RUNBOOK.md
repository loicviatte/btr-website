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
Nothing to process → stop, say nothing. A folder without `captions.srt` is not ready yet (YouTube is still
making the captions): leave it, the Action retries.

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
- `atlasCards` (when there is an atlas pick): 6 slides like the existing countries in design/Atlas.dc.html:
  "Latin & Ballroom?" verdict, a big number fact, typical dances (2), a person or event, a year fact.
  Research with web search; every fact must be checkable (keep the sources for the commit message).
  Format: see `atlas_cards()` in `tools/auto/btr_pages.py`. If research isn't solid, leave `atlasCards` out:
  a "coming soon" card is shown instead.
- Part 2: `"addPartTo": "<existing slug>"`, `parts` = only the new part; give `chain`/`atlas` found in this part.

## 3. Apply
```
python3 tools/auto/btr_auto.py apply data/episodes/<slug>.json
```
This creates/updates: the episode page, Episodes list, Search index, previous guest's links, home page (hero,
previous episodes, chain teaser, World Atlas card), The Chain and the World Atlas.

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

## 6. Tell Loïc (in French, short)
What went online (guest, episode page link `https://www.breaktheroutinepodcast.com/episodes/<slug>`), the chain
question and the country picked, and anything uncertain (e.g. "pas trouvé la question de la Chain").

If something fails and can't be fixed safely: don't push, leave the folder without `done`, and tell Loïc what
blocked.
