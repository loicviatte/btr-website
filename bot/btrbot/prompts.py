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
  accent) with longer flowing blocks; vary how many punch words each block has.
- Never put the last 1-2 words of a sentence on the same block as the start of the next sentence: finish the sentence
  on its block, start the next sentence on a new block (only a block that holds both sentences whole may mix them).
- 4 lines per block at most (a hard limit). When a phrase is too long for 4 lines, end the block where its clause ends and
  continue the phrase on the next block; 1-2 lines is fine for an accent.
Notation for each token:
- lower-case = small linking word; UPPER-CASE = punch word shown huge (one or two per block, the words that carry the meaning)
- prefix * = gold (key words, about one per block), / = italic (punchlines), ~ = letters that tighten (use 1 or 2 times in the whole reel)
- a prefix applies to ONE word only. Put “ ” around words the speaker quotes or paraphrases from someone else.
Rules: use ONLY the spoken words, in the same order, same spelling (you may fix the capitalisation and punctuation). You may skip
fillers and stutters ("um", "you know", repeated words) but never add, change or reorder words. Never put a long small-word
phrase on the same line as a punch word: split it. Always put "align": "c" (the program places the blocks on screen).
Return ONLY JSON: {{"blocks": [{{"align": "c", "lines": ["where are my *FRIENDS", "FAMILY", "HUSBAND?"]}}]}}"""

REEL_CAPTIONS = """Write the pieces of the social captions for this reel of Break The Routine, a DanceSport podcast hosted by Marius
Iepure. Guest: {guest_name}. Episode: "{video_title}".
What is said in the reel:
<reel>
{text}
</reel>
The captions follow a fixed format approved by Loïc (the program assembles it), e.g. for Oti Mabuse:
“They just don't care.”

@otimabuse on Latin and Ballroom competitive dance versus the TV shows: “When you are on these shows, people care.”

Do you agree? Tell us in the comments.

Part 2 of Break The Routine with Oti Mabuse is out now on YouTube and Spotify. Link in bio.
Give:
- "hook": the most striking short sentence of the reel, EXACT consecutive words the guest says (3 to 12 words, keep
  their punctuation), e.g. "They just don't care."
- "topic": what the moment is about, a few plain words that follow "<guest> on …", e.g. "Latin and Ballroom
  competitive dance versus the TV shows" (no quotes, no full stop, no emoji).
- "quote": a second line said in the reel that backs the hook up, EXACT consecutive words (5 to 20 words), different
  from the hook; "" if none fits.
- "question": one short question to the audience that makes dancers comment, e.g. "Do you agree?" or "Have you ever
  felt this on the floor?" (no emoji).
- "tags": 1 to 3 extra hashtags specific to this moment (e.g. "#StrictlyComeDancing"), CamelCase.
- "cover": the words printed on the reel cover: 2 to 5 CONSECUTIVE words the guest really says, split in up to 3
  parts: "small" = the lead-in words (may be empty), "big" = the punch word(s) shown huge, "gold" = the last punch
  word(s) in gold italic (may be empty). Example: {{"small": "They just", "big": "DON'T", "gold": "CARE."}}. big and
  gold: 1 or 2 short words each, in UPPER CASE.
Never invent facts or words: quotes are only what is said above. No emoji anywhere. English.
Return ONLY JSON: {{"hook": "...", "topic": "...", "quote": "...", "question": "...", "tags": ["#..."],
"cover": {{"small": "...", "big": "...", "gold": "..."}}}}"""

REEL_COVER_PICK = """The first image is a reel cover Loïc approved: the style to match. The second image shows numbered candidates for
the cover of another reel, each framed as the cover would be (the bottom part is darkened: the hook text goes there).
Pick the best ones, like the approved cover: the guest's face sharp (no motion blur), both eyes open and visible (also
behind glasses), a lively, engaged expression (a smile, a strong emotion, mid-thought), looking at the host or slightly
to the side, MOUTH CLOSED or a closed-mouth smile (never caught mid-word with the mouth open — Loïc rejects those), no hand or microphone in front of the face, head and
shoulders well placed in the upper part of the frame.
Return ONLY JSON: {{"best": [numbers, best first, up to 3]}}"""

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
- "together": when Loïc wants words kept on the same block (« laisse good time ensemble », « le time est séparé de
  good »), the exact words as they are on screen, e.g. ["good time"]. They will be forced onto one block.
- "reply": one short French sentence for Loïc saying exactly what you will change (or asking ONE question if you
  really cannot tell what he means).
Return ONLY JSON: {{"fixes": [{{"from": "...", "to": "..."}}], "relayout": false, "layout_note": "", "together": [],
"reply": "..."}}"""


REEL_NAMES = """You check the spelling of the proper nouns in the subtitles of a short clip from Break The Routine, a DanceSport
podcast hosted by Marius Iepure. Guest: {guest}. Episode: "{title}".
What the speech recognition wrote for the clip:
<clip>
{text}
</clip>
Context written by the producers (episode title, YouTube description, chapters), names are spelled right there:
<context>
{context}
</context>
Find every proper noun in the clip: people (dancers, partners, judges, celebrities, family members), TV shows,
competitions, dance studios, places, brands. Check each spelling, first against the context, then with web search
whenever you are not certain (search the name with the guest, e.g. "Oti Mabuse sister", "Strictly 2019 Kelvin
Fletcher partner"). Also catch names the recognizer wrote as ordinary words or split oddly ("Muti" for Motsi, "danny
mack" for Danny Mac, "black pool" for Blackpool).
Rules: only change a word into the correct spelling of the SAME spoken name (it sounds the same); never touch ordinary
words; never add or remove words; if you cannot confirm a spelling, leave it as it is.
Return ONLY JSON, after your searches: {{"fixes": [{{"from": "words exactly as in the clip", "to": "correct spelling",
"source": "context" or a URL}}]}}"""


SMILES = """These are numbered close-ups of the same person's face, taken from a podcast video, for an Instagram photo.
"smile" = the numbers where the person smiles or laughs naturally (warm, genuine expression), eyes open (not a blink,
not mid-word with a twisted mouth). "best" = up to 5 numbers, the most flattering and lively expressions, best first.{want}
Return ONLY JSON: {{"smile": [numbers], "best": [numbers]}}"""

MOUTH_OPEN = """These are numbered close-ups of the same person's face, taken from a video.
List ONLY the numbers where the mouth is OPEN: lips apart, talking, teeth or inside of the mouth visible (a wide smile
showing teeth counts as open). A closed mouth or lips together (even smiling) is not open.
Return ONLY JSON: {{"open": [numbers]}}"""


GUEST_INSTAGRAM = """Find the Instagram account of {guest}, the guest of this episode of Break The Routine, a DanceSport
podcast (Latin & Ballroom; hosted by Marius Iepure). Episode title and description:
{context}

Search the web. Only give an account you are confident is this exact person (the dancer / coach / judge, not a namesake):
verified badge, link from their own website, competition profile, or the episode itself. Never guess a handle from the name.
Answer with JSON only: {{"handle": "username without @, or empty if not found", "sure": true/false,
"evidence": "one short line in French: where you found it"}}"""

POSTS = """Write the content of this episode's Instagram carousels and stories (rules validated by Loïc on the Oti Mabuse
Part 2 episode). Episode: "{title}". Guest: {guest}.{part_line}
YouTube chapters (index: start time title):
{chapters}
Already used in the teaser and the reels of this episode (do NOT reuse these moments for the key moment):
{avoid}
{feedback}
Hard rules:
- Every field marked EXACT = consecutive words really said in the transcript above (you may cut at the start or the end
  of a sentence, never add, change, reorder or fix a word). Guest's words unless said otherwise.
- English. No emoji, no hashtags. Facts only from the transcript. Never a line said by Marius when the guest's is asked.
- Times "mm:ss" (or "h:mm:ss") read from the nearest [mm:ss] marker before the words.
Return ONLY JSON with:
"guest_title": the guest's short title for a label, e.g. "Two-time Strictly champion" (max 30 chars, true to the episode),
"pronoun": "she" | "he" | "they",
{blocks}
"""

POSTS_BLOCKS = {
    "moment": """"moment": {{"sentences": [8 objects {{"text": EXACT, one sentence (or part) said by the guest, 4 to 16 words,
   "gold": [1 to 3 words of that text that carry the emotion, copied exactly], "t": "mm:ss"}}] — 8 sentences following
   each other in ONE strong moment of the episode (emotion, confession, a stand taken), in order, ~1 to 3 minutes long,
   not one of the moments already used; "hook": EXACT, the most striking of these 8 texts; "context": what the moment is
   about, words that follow "<guest> on …" (no quotes, no full stop), "quote": EXACT, a second line of the moment that
   backs the hook up ("" if none), "question": one short question to the audience, e.g. "Have you ever felt this?",
   "tags": 1 to 3 extra CamelCase hashtags for TikTok}}""",
    "topics": """"topics": {{"items": [6 objects in episode order {{"chapter": index of the chapter (list above) where this
   subject is discussed, "title": short catchy title (max 45 chars, no quote marks), "context": 1 or 2 factual sentences
   (max 170 chars) that set the quote up, "quote": EXACT guest's words on this subject (5 to 16 words), "t": "mm:ss" of the
   quote}}], "hook": one line for the cover, max 70 chars, ending with "Swipe through." (e.g. "Strictly, two wins, and why
   she walked away. Swipe through."), "summary": one sentence for the caption naming the subjects, with "{{guest}}" where
   the guest's name goes (e.g. "From Kelvin to Bill Bailey to walking away, {{guest}} told us everything."), "tags": 1 to 3
   CamelCase hashtags}} — no quote used in the key moment""",
    "poll": """"poll": {{"line": 1 or 2 short lines that set the question up (max 34 chars each, separated by \\n), e.g.
   "Two Strictly wins.\\nThen she walked away.", "question": the poll question (max 34 chars), "options": [2 answers, max
   18 chars each], "footer": e.g. "Her answer is in Part 2, link in bio.", "tap": the end of « Tap the link … » for the
   version without poll, e.g. "to hear why.", "t": "mm:ss" when this subject is discussed, "b": true if the subject is
   too long, too loaded or too serious for a poll}}""",
    "rapid": """"rapid": {{"question": EXACT, one rapid fire question as MARIUS asks it (max 10 words), "answer": EXACT, the guest's
   answer (max 12 words), "options": [the true answer in max 22 chars, 2 believable decoys], "count": how many rapid fire
   questions are asked (0 if unknown), "footer": e.g. "Her 20 answers are in Part 2, link in bio.", "t": "mm:ss" of the
   question, "b": true if the answer can't make a fair quiz}}""",
    "chain": """"chain": {{"prev_guest": full name of the previous guest who left the question for this guest (from the
   episode), "question": EXACT, that question as it is read in the episode (MARIUS or the card; max 18 words), "answer":
   the guest's real answer in max 22 chars for the quiz, "options": [the true answer, 2 believable decoys], "footer": a
   teasing line true to the answer, e.g. "Her answer involves chickens. Part 2, link in bio.", "t": "mm:ss" when the
   question is read, "b": true if the answer is too long or too serious for a quiz}} — if the episode has no question
   from a previous guest, give "chain": null""",
    "link": """"link": {{"headline": "We asked <her/him> …" what makes people tap, e.g. "We asked her why she walked away
   from Strictly after two wins." (max 80 chars), "tap": end of « Tap the link … », e.g. "to hear what she told us.",
   "t": "mm:ss" of that subject}}""",
    "ask": """"ask": {{"t": "mm:ss" when Marius reads or holds the question card for the next guest (end of the
   episode), or null}}""",
    "qa": """"qa": {{"question": EXACT, a short question as MARIUS asks it (max 12 words), "answer": EXACT, the guest's answer
   (max 16 words, a fun or striking one), "t_q": "mm:ss", "t_a": "mm:ss"}}""",
    "quote": """"quote": {{"quote": EXACT, the guest's strongest short line (3 to 9 words), "label": "<GUEST NAME> ON
   <SUBJECT>" in capitals (max 36 chars), "t": "mm:ss"}} — not the key moment's hook""",
    "atlas": """"atlas": {{"country": the country the guest lands on in the World Atlas segment, "options": [that country,
   2 decoys], "t": "mm:ss" when the atlas is opened, "b": false}} — null if there is no World Atlas segment""",
    "teaser": "",
}

POSTS_FIX = """These fields are not exact words of the transcript (or were rejected). Give the same JSON again with
these fields replaced by words really said (cut, never add), everything else unchanged:
{errors}"""


TEASER_MOMENTS = """Episode: "{video_title}" with {guest_name}.{part_line}

The transcript (with [mm:ss] markers) is above.

Build the TEASER of this episode: {n} very short moments cut together (about 30 s in all), then an end screen
« Episode out now ». It is the trailer that makes DanceSport people click on the full episode.
Each moment:
- ONE complete sentence or phrase said by {guest_name} (or a short exchange with Marius), 3 to 9 seconds long.
- Punchy on its own: a strong opinion, a confession, a surprising fact, an emotional line, a laugh. Never a warm-up.
- Makes people curious WITHOUT giving the answer away (tease the story, don't tell its ending).
- Different topics: together they show the range of the episode.
Order them like a trailer: the strongest hook first, rising tension, the most intriguing line last (just before « out now »).
For each, the EXACT first words and EXACT last words as they appear in the transcript (3 to 8 words each), so the cut
can be found in the audio. The moment ends where the sentence ends, never mid-thought.
{feedback}Return ONLY JSON:
{{"moments": [
  {{"start": "mm:ss", "end": "mm:ss", "first_words": "exact first words", "last_words": "exact last words",
    "line": "the whole sentence, verbatim", "why": "1 short French line: why it teases"}}
]}}"""


COMMUNITY = """Episode: "{video_title}" with {guest_name}.{part_line} The transcript (with [mm:ss] markers) is above.
Write ONE YouTube Community post for the Break The Routine channel (DanceSport podcast hosted by Marius Iepure), in English.
Rules: no link and no URL anywhere, no hashtags, at most one emoji, no em dash. A quote must be the guest's exact words
(cut, never add or change words) and goes in “ ”. Never spoil the answer of a story; make people curious.
{what}
{feedback}Return ONLY JSON: {{"text": "...", "question": "..." or null, "options": ["..."] or null, "correct": null or the
0-based index of the right option (quiz), "quote": "the exact quote used, or null"}}"""

COMMUNITY_WHAT = {
    "tomorrow": "Kind: « New episode tomorrow », posted the day before the episode comes out. 1 to 3 short sentences "
                "(max 300 characters): who the guest is for dancers, one teasing line or short exact quote, then that "
                "the episode is out tomorrow on the channel. No question/options.",
    "poll": "Kind: poll about this week's episode. A question DanceSport people want to vote on (a stance or debate from "
            "the episode, or a quiz on what the guest answered), max 100 characters; 2 to 4 short options (max 60 "
            "characters each); for a quiz, set correct. text = 1 short sentence introducing it (max 150 characters).",
}
