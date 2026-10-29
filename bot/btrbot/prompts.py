"""Prompts for Claude. Public copy is in English; the chat with Loïc is in French."""

SYSTEM = """You are the packaging editor of "Break The Routine" (BTR), a DanceSport (competitive Latin & Ballroom) video podcast hosted by Marius Iepure. Guests are judges, champions, coaches and federation figures.
You help Loïc (producer, French-speaking) pick the hook of each new episode: the guest quote that goes on the thumbnail and the YouTube title.
Rules for thumbnail quotes:
- A REAL sentence the guest says in the transcript, verbatim or trimmed (never invent or paraphrase words they did not say). Never a line said by Marius.
- 3 to 7 words, punchy, curiosity-driven, a bit provocative ("clickbait" but honest to the episode). It must make a dancer need to know the story.
- Split in three parts: "top" (small words), "key" (ONE punch word or two short words, shown huge, max 12 characters, usually UPPERCASE), "bottom" (small words). top+key+bottom read as the quote.
YouTube titles follow the channel's existing pattern (see the reference titles) and stay under 100 characters.
Write public copy in English. Talk to Loïc in French, short and direct."""

AXES = """New unlisted episode: "{video_title}".
Guest (best guess, confirm from the transcript): {guest_hint}

Reference: the channel's previous episode titles (copy their pattern and tone):
{ref_titles}

Previous thumbnail quotes that worked: "I'd had enough", "Who PROTECTS the dancers?", "My family DIDN'T SPEAK to me", "They're gonna BAN judges", "People were BREAKING the rules".

The transcript (with [mm:ss] markers) is above.

Find the 3 strongest, clearly different angles (axes) for this episode. Return ONLY JSON:
{{"guest_name": "First Last",
  "axes": [
    {{"angle": "1 short French line: what the angle is about",
      "quote": "the exact words from the transcript",
      "top": "...", "key": "...", "bottom": "...",
      "timestamp": "mm:ss where the guest says it",
      "title": "YouTube title proposal",
      "why": "1 short French line: why it will click"}}
  ]}}"""

REFINE = """Current episode: "{video_title}" with {guest_name}.
Axes proposed so far (JSON): {axes}

The transcript (with [mm:ss] markers) is above.

Conversation so far about this episode (oldest first):
{history}

Loïc now writes: "{message}"

Answer him in French. If he asks for changes or new options, propose them (always verbatim guest quotes). If he clearly picks or validates one, set "final".
Return ONLY JSON:
{{"reply": "your French message to Loïc",
  "axes": [optional new/updated list of axes, same shape as before, or null],
  "final": {{"quote": "...", "top": "...", "key": "...", "bottom": "...", "timestamp": "mm:ss", "title": "...", "guest_name": "First Last"}} or null}}"""

PICK_FRAMES = """These are numbered candidate frames of {who} from the episode. The thumbnail quote is: "{quote}".
Pick the {n} best frames for a YouTube/Instagram thumbnail: eyes open, face sharp and well lit, a strong readable expression that fits the quote's emotion, mouth not caught mid-word in an ugly way, head not cut, not blurred by motion. Prefer variety (different expressions).
Return ONLY JSON: {{"best": [numbers in order of preference], "note": "1 short French line"}}"""

EYES_OPEN = """These are numbered close-ups of the upper half of a face (eyes area), taken from a video, for a thumbnail.
List ONLY the numbers where BOTH eyes are fully open: both irises and pupils clearly visible, no squinting, no laughing-squint, no blink, no heavy lids, not winking, not looking far to the side with the eye half hidden. When in doubt, leave the number out.
Return ONLY JSON: {{"open": [numbers]}}"""

DESCRIPTION = """Write the YouTube description for the new episode, keeping EXACTLY the structure of the channel's existing descriptions below: same sections in the same order, same fixed blocks (links, credits, sponsors, socials, hashtags) copied verbatim, same tone and length. Only replace the episode-specific parts (hook/summary about the guest and topics).
Where the previous descriptions have chapters/timestamps, put the single line {{CHAPTERS}} instead (it will be filled later). If they have none, put {{CHAPTERS}} just before the links block.
Never invent facts: use only what the transcript says.

Episode title: {title}
Guest: {guest_name}

Previous descriptions:
{refs}

Transcript excerpt:
<transcript>
{transcript}
</transcript>

Return ONLY the description text."""

CHAPTERS = """Create YouTube chapters for this episode from the timed transcript.
Rules: first chapter at 00:00; 6 to 15 chapters; at least 1 minute apart; titles in English, 3 to 8 words, SEO oriented (names, topics, competitions), no hyphens or dashes, never in the host's first person. Flag the recurring segments explicitly when they appear: the World Atlas game, the rapid-fire questions, the question passed from one guest to the next.
Use the timestamps of the transcript (they match the video). Return ONLY JSON: {{"chapters": [["00:00", "Title"], ["mm:ss", "Title"]]}}

<transcript>
{transcript}
</transcript>"""

RETIME = """These YouTube chapters have APPROXIMATE start times (they can be off by up to a minute or more). Using the transcript markers
below (exact times from the SRT), set each chapter's start to the exact time where its topic really begins (the first sentence of that
topic). Keep the titles and the order unchanged. Return ONLY JSON: {{"chapters": [["00:00", "Title"], ["mm:ss", "Title"]]}}

Current chapters:
{chapters}

<transcript>
{transcript}
</transcript>"""

TRANSCRIPT = """Transcript of the episode, with [mm:ss] markers:
<transcript>
{transcript}
</transcript>"""



# ---------------------------------------------------------------- reels (claude/btr-reels-workflow.md)
REEL_CANDIDATES = """Episode: "{video_title}" with {guest_name}.
The thumbnail/teaser of this episode already uses this moment (avoid it): {avoid}

The transcript (with [mm:ss] markers) is above.

Find the {n} best moments for vertical reels (Instagram Reels, TikTok, YouTube Shorts) aimed at the DanceSport community.
Each moment:
- 20 to 60 seconds, self-contained (a viewer who never saw the episode understands it), mostly the guest speaking.
- Opens with a punchy sentence in the first 5 seconds (the hook): no warm-up, start right on it.
- Has a turn or a clear stance that makes dancers react (debate, confession, surprising fact, strong opinion, funny story).
- Ends on a strong last sentence (a punchline or a stance), not mid-thought.
- No two moments overlap; cover different topics.
For each, give the EXACT first words and the EXACT last words as they appear in the transcript (5 to 8 words each), so the cut can be found in the audio.
Return ONLY JSON:
{{"candidates": [
  {{"start": "mm:ss", "end": "mm:ss",
    "first_words": "exact first 5-8 words", "last_words": "exact last 5-8 words",
    "hook": "the opening sentence, verbatim",
    "title": "3-6 word English label",
    "why": "1 short French line: why it will work"}}
]}}"""

REEL_BLOCKS = """Lay out animated subtitles for a vertical reel of a DanceSport podcast, in the "Diary of a CEO" stacked style.
Here are the words actually spoken in the reel, in order (index:word):
{words}

Group them into blocks (pages) of short lines (1 to 3 words per line) that follow the speech.
- NEVER split a phrase or an expression across two blocks: a block ends where the speaker's thought or clause ends, never
  between words that belong together ("why not", "give me", "a lot of", "I don't know", "come on", verb + its object,
  article/preposition + its noun). If in doubt, keep the words together in the same block.
- Vary the rhythm so it never feels monotonous: mix very short punch blocks (1-2 lines, a single huge word on its own for an
  accent) with longer flowing blocks; vary the alignment and how many punch words each block has.
- About 3-4 lines per block is a guide, not a rule: go to 5-7 lines when a phrase needs it to stay whole, or 1 line for an accent.
Notation for each token:
- lower-case = small linking word; UPPER-CASE = punch word shown huge (one or two per block, the words that carry the meaning)
- prefix * = gold (key words, about one per block), / = italic (punchlines), ~ = letters that tighten (use 1 or 2 times in the whole reel)
- a prefix applies to ONE word only. Put “ ” around words the speaker quotes or paraphrases from someone else.
Rules: use ONLY the spoken words, in the same order, same spelling (you may fix the capitalisation and punctuation). You may skip
fillers and stutters ("um", "you know", repeated words) but never add, change or reorder words. Never put a long small-word
phrase on the same line as a punch word: split it. Vary the alignment from one block to the next: "c" centred, "l" left, "stair".
Return ONLY JSON: {{"blocks": [{{"align": "c", "lines": ["where are my *FRIENDS", "FAMILY", "HUSBAND?"]}}]}}"""

REEL_CAPTIONS = """Write the social captions for this reel of Break The Routine, a DanceSport podcast hosted by Marius Iepure (@mariusiepure).
Guest: {guest_name}. Episode: "{video_title}".
What is said in the reel:
<reel>
{text}
</reel>
Rules: English; first line = a hook that makes a dancer stop scrolling (never invent facts or quotes: only what is said above);
then 1 or 2 short lines of context; then a call to action to watch the full episode (YouTube / Spotify, link in bio).
Instagram: NO hashtags, max 60 words. TikTok / YouTube Shorts: same text plus 5 to 8 relevant hashtags at the end
(#dancesport #ballroom #latindance …).
Return ONLY JSON: {{"instagram": "...", "tiktok": "..."}}"""

REEL_ARBITRATE = """Two transcriptions of the same podcast audio disagree in a few places: an automatic speech model ("audio")
and the producer's subtitle file ("srt"). Either one can be wrong. For each disagreement, pick the version that is most
likely what was really said, using the context, the speaker's name, and your knowledge of DanceSport and TV dance
shows (names of judges, dancers, competitions, dances). You can ONLY choose between the two versions, never write another.
Podcast: Break The Routine (DanceSport), host Marius Iepure. Guest: {guest_name}. Episode: "{title}".
{items}
Return ONLY JSON: {{"picks": [{{"id": 0, "pick": "audio" | "srt", "sure": true | false}}]}}"""

REEL_SUB_FEEDBACK = """You fix the burned-in subtitles of a vertical reel. The producer (Loïc, writing in French, casually) gives feedback.
Words spoken in the reel, in order (as transcribed): {words}
Subtitles currently on screen, block by block (lines separated by " / "):
{blocks}
Loïc's feedback: "{feedback}"

Decide what to change:
- "fixes": words that are wrong on screen and what they should be (a misheard word, a misspelled name). "from" = the words
  exactly as they are now, "to" = the correct words. Only words Loïc points at. "to" must be words Loïc wrote himself
  (e.g. "c'est Motsi" → "Motsi"). If he only says a passage is wrong without saying what is really said, do NOT guess:
  no fix, and ask him in "reply" for the exact words. Never change words he did not question; never rephrase.
- "relayout": true if the problem is the layout (cut in the wrong place, a word missing on screen, bad emphasis) rather than
  a word; then "layout_note" = a short English instruction for whoever redoes the layout.
- "reply": one short French sentence for Loïc saying exactly what you will change (or asking ONE question if you
  really cannot tell what he means).
Return ONLY JSON: {{"fixes": [{{"from": "...", "to": "..."}}], "relayout": false, "layout_note": "", "reply": "..."}}"""
