#!/usr/bin/env python3
"""Break The Routine — add a new episode (or a new part of an episode) to the site.

The site's source of truth is design/*.dc.html. This script edits those files from an episode spec
(data/episodes/<slug>.json, written by the scheduled Claude task from the YouTube data that the GitHub
Action downloads into data/incoming/<videoId>/). Then `npm run compile && npm run build`.

Commands
  srt <captions.srt>                      print transcript passages [[sec, text], ...] as JSON
  chapters <meta.json>                    print chapters parsed from the YouTube description as JSON
  thumb <thumb.jpg>                       copy a thumbnail into public/assets, print its asset id
  apply <spec.json>                       create/update the episode page, Episodes list, Search index,
                                          previous episode's links. Prints what is left to do by hand.
  country "<Country name>"                print the World Atlas map entry for a country (needs node deps)
  atlas-sync <btr-media dir>              fill "coming soon" Atlas cards from the Instagram carousel research
                                          (btr-media/pipeline/content/<slug>.json, matched by guest name)

Extra spec keys: "teaser" (one sentence under the home page hero), "atlasCards" (carousel slides, see btr_pages.atlas_cards),
"atlas.mapName" (the map's own country name when it differs, e.g. "Dem. Rep. Congo").

Spec (data/episodes/<slug>.json)
{
  "slug": "flavia-cacace", "name": "Flavia Cacace", "initials": "FC", "pronoun": "she",
  "bio": "One sentence on who the guest is.",
  "about": ["In this episode, Marius Iepure sits down with ...", "They talk about ..."],
  "imgPos": "50% 30%",                       # object-position of the guest crop in the sidebar (optional)
  "parts": [{"vid": "abc123", "title": "Episode title", "date": "4 Nov 2026", "secs": 3720, "thumb": "<asset id>",
             "chapters": [{"sec": 0, "label": "Intro"}, ...],
             "transcript": [[0, "text"], [12, "text"], ...]}],
  "chain": {"answers": {"from": "Oti Mabuse", "fromSlug": "oti-mabuse", "question": "…", "part": 0, "sec": 1234},
            "leaves":  {"question": "…", "part": 0, "sec": 4567}},     # either may be null
  "atlas": {"country": "Peru", "slug": "peru", "part": 0, "sec": 2345}, # or null
  "polaroid": "<asset id>"                  # optional
}
For a part 2, put only the new part in "parts" and add "addPartTo": "<existing slug>"; the existing page keeps
its part 1 (transcript, chapters, reels…) and gets the new part appended. chain/atlas/about may then be given to
replace the existing ones (omit to keep them).
Optional "playlist": {"title", "artist", "sec", "part"}: the guest's song (see tools/auto/btr_playlist.py).
"""
import hashlib, html, json, os, re, shutil, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DESIGN = os.path.join(ROOT, 'design')
ASSETS = os.path.join(ROOT, 'public', 'assets')
MONO = "font-family: 'PP Monument Extended', 'Arial Black', sans-serif;"
SPOTIFY = 'https://open.spotify.com/show/033MKpAWIDCQzSHvlWeTF1'
APPLE = 'https://podcasts.apple.com/us/podcast/break-the-routine/id6789345225'
TEMPLATE = 'Episode-peter-maxwell.dc.html'   # a complete page: chain answer + question left + atlas + polaroid

def esc(s):
    return html.escape(str(s), quote=True)

def read(name):
    with open(os.path.join(DESIGN, name), encoding='utf-8') as f:
        return f.read()

def write(name, s):
    with open(os.path.join(DESIGN, name), 'w', encoding='utf-8') as f:
        f.write(s)

def yt(vid, sec=0):
    return 'https://www.youtube.com/watch?v=' + vid + (f'&amp;t={int(sec)}s' if sec else '')

def yt_js(vid, sec=0):
    return 'https://www.youtube.com/watch?v=' + vid + (f'&t={int(sec)}s' if sec else '')

def fmt(s):
    s = int(s); h, m, x = s // 3600, s % 3600 // 60, s % 60
    return f'{h}:{m:02d}:{x:02d}' if h else f'{m:02d}:{x:02d}'

def human_len(secs):            # "1 h 26" / "58 min"
    m = round(secs / 60)
    return f'{m // 60} h {m % 60:02d}' if m >= 60 else f'{m} min'

def list_len(secs):             # Episodes list: "1:26:00" / "58:00"
    m = round(secs / 60)
    return f'{m // 60}:{m % 60:02d}:00' if m >= 60 else f'{m}:00'

def first(name):
    return name.split(' ')[0]

def poss(name):
    return first(name) + '’s'

def subj(p):
    return {'she': 'She', 'he': 'He'}.get(p, 'They')

def obj_poss(p):
    return {'she': 'Her', 'he': 'His'}.get(p, 'Their')

def page_of(slug):
    return f'Episode-{slug}.dc.html'

# ---------------------------------------------------------------- transcript / chapters / thumbnails

def srt_passages(path, max_secs=28, max_chars=420):
    """SRT cues -> passages that end on a sentence, like the hand-made transcripts: [[sec, text], ...]."""
    raw = open(path, encoding='utf-8-sig').read().replace('\r', '')
    cues = []
    for block in re.split(r'\n\s*\n', raw.strip()):
        lines = [l for l in block.split('\n') if l.strip()]
        ti = next((i for i, l in enumerate(lines) if '-->' in l), None)
        if ti is None: continue
        m = re.match(r'(\d+):(\d+):(\d+)[,.](\d+)', lines[ti].strip())
        if not m: continue
        sec = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
        text = ' '.join(lines[ti + 1:])
        text = re.sub(r'<[^>]+>', '', text).replace('&gt;&gt;', '').replace('>>', '').strip()
        if text: cues.append((sec, text))
    # YouTube auto captions repeat the previous line as the first line of the next cue: drop overlaps
    out, last = [], ''
    for sec, text in cues:
        if last and text.startswith(last):
            text = text[len(last):].strip()
        if text: out.append((sec, text)); last = text
    passages, cur, start = [], [], None
    for sec, text in out:
        if start is None: start = sec
        cur.append(text)
        joined = ' '.join(cur)
        if (re.search(r'[.?!]["”’)]?$', text) and (sec - start >= 6 or len(joined) > 160)) or sec - start >= max_secs or len(joined) > max_chars:
            passages.append([start, re.sub(r'\s+', ' ', joined).strip()]); cur, start = [], None
    if cur: passages.append([start, re.sub(r'\s+', ' ', ' '.join(cur)).strip()])
    return passages

def description_chapters(desc):
    ch = []
    for line in (desc or '').split('\n'):
        m = re.match(r'^\s*\(?((?:\d{1,2}:)?\d{1,2}:\d{2})\)?\s*[-–—:|]?\s*(.+?)\s*$', line)
        if not m: continue
        parts = [int(x) for x in m.group(1).split(':')]
        sec = parts[0] * 3600 + parts[1] * 60 + parts[2] if len(parts) == 3 else parts[0] * 60 + parts[1]
        ch.append({'sec': sec, 'label': m.group(2)})
    return ch if len(ch) >= 3 and ch[0]['sec'] == 0 else []

def add_thumb(path):
    data = open(path, 'rb').read()
    aid = hashlib.md5(data).hexdigest()
    ext = os.path.splitext(path)[1].lower().lstrip('.') or 'jpg'
    os.makedirs(ASSETS, exist_ok=True)
    shutil.copyfile(path, os.path.join(ASSETS, f'{aid}.{ext}'))
    return aid

# ---------------------------------------------------------------- reading existing data

def episodes_rows():
    s = read('Episodes.dc.html')
    m = re.search(r'const list = \[\n(.*?)\n    \];', s, re.S)
    rows = []
    for line in m.group(1).split('\n'):
        vals = re.findall(r"'((?:[^'\\]|\\.)*)'", line)
        if len(vals) == 7: rows.append(vals)
    return rows

def guest_order():
    """Pages in release order (oldest first), from the Episodes list (newest first)."""
    seen, order = set(), []
    for r in reversed(episodes_rows()):
        if r[6] not in seen: seen.add(r[6]); order.append(r[6])
    return order

def js_array(s, name):
    m = re.search(r'\n    const ' + name + r' = (\[.*?\]);\n', s, re.S)
    return json.loads(m.group(1)) if m else None

def set_js_array(s, name, value):
    new = '\n    const ' + name + ' = ' + json.dumps(value, ensure_ascii=False) + ';\n'
    s2, n = re.subn(r'\n    const ' + name + r' = \[.*?\];\n', lambda m: new, s, count=1, flags=re.S)
    assert n == 1, name
    return s2

def row_for(page, vid=None):
    for r in episodes_rows():
        if r[6] == page and (vid is None or r[4] == vid): return r
    return None

# ---------------------------------------------------------------- page pieces

def player_block(tpl, part, label, name):
    m = re.search(r'<div data-player=""[^>]*>.*?\n    </div>', tpl, re.S)
    b = m.group(0)
    b = re.sub(r'(<img src=")[^"]*(" alt=")[^"]*(")', lambda x: x.group(1) + '/_blob/' + part['thumb'] + x.group(2) + esc(name + ' and Marius Iepure on the Break The Routine set') + x.group(3), b, count=1)
    b = re.sub(r'(<a href=")[^"]*(" class="ep-hero-btn")', lambda x: x.group(1) + yt(part['vid']) + x.group(2), b, count=1)
    b = re.sub(r'(</svg>\s*)[^<]*?(\s*</a>)', lambda x: x.group(1) + label + x.group(2), b, count=1)
    return m.span(), b

def header_col(spec):
    parts = spec['parts']
    meta_style = f"margin: 0; {MONO} font-size: 11px; font-weight: 800; letter-spacing: 0.08em; color: #c9b8a6;"
    chip = f"display: inline-flex; align-items: center; min-height: 36px; padding: 0 14px; {MONO} font-size: 11px; font-weight: 800; letter-spacing: 0.06em; text-decoration: none; "
    out = []
    if len(parts) == 1:
        p = parts[0]
        out.append(f'<p style="{meta_style}">{esc(p["date"].upper())} · {esc(human_len(p["secs"]).upper())}</p>')
    else:
        items = []
        for i, p in enumerate(parts):
            lab = f'PART {i + 1} · {p["date"].upper()} · {human_len(p["secs"]).upper()}'
            if i == 0: items.append(f'<span style="{chip}background: #fecb7a; color: #000000;">{esc(lab)}</span>')
            else: items.append(f'<a href="{yt(p["vid"])}" style="{chip}border: 1px solid rgba(254,203,122,0.55); color: #ffffff;">{esc(lab)}</a>')
        out.append('<nav aria-label="Parts" style="display: flex; flex-wrap: wrap; gap: 8px;">' + ''.join(items) + '</nav>')
    title = parts[-1]['title'] if len(parts) > 1 else parts[0]['title']
    out.append(f'<h1 style="margin: 0; {MONO} font-size: clamp(26px, 3.2vw, 46px); font-weight: 800; line-height: 1.08; text-wrap: balance;">{esc(title)}</h1>')
    out.append(f'<p style="margin: 0; {MONO} font-size: 18px; font-weight: 800; color: #fcdf9a;">with {esc(spec["name"].upper())}</p>')
    return '\n        '.join(out)

def buttons(spec):
    b = f"display: inline-flex; align-items: center; min-height: 48px; padding: 0 20px; {{}} text-decoration: none; {MONO} font-size: 12px; font-weight: 800; letter-spacing: 0.04em;"
    gold = b.format('background: #fecb7a; color: #000000;')
    line = b.format('border: 1px solid rgba(254,203,122,0.55); color: #ffffff;')
    vids = spec['parts']
    yts = [f'<a href="{yt(p["vid"])}" style="{gold}">{"YOUTUBE" if len(vids) == 1 else "PART " + str(i + 1) + " ON YOUTUBE"}</a>' for i, p in enumerate(vids)]
    return '\n        '.join(yts + [f'<a href="{SPOTIFY}" style="{line}">SPOTIFY</a>', f'<a href="{APPLE}" style="{line}">APPLE PODCASTS</a>'])

def about_html(paras):
    out = []
    for i, p in enumerate(paras):
        color = '#e8ddd1' if i == 0 else '#c9b8a6'
        out.append(f'<p style="margin: 0; max-width: 680px; color: {color};">{esc(p)}</p>')
    return '\n          '.join(out)

def chain_html(spec, next_guest=None):
    name, pr = spec['name'], spec.get('pronoun', 'they')
    vids = [p['vid'] for p in spec['parts']]
    link = 'align-self: flex-start; padding: 4px 0; font-size: 14px;'
    blocks = []
    a = (spec.get('chain') or {}).get('answers')
    if a:
        part = a.get('part', 0)
        ptxt = f'Part {part + 1} at ' if len(vids) > 1 else 'at '
        blocks.append(f'''<div style="display: flex; flex-direction: column; gap: 4px;">
            <p style="margin: 0; font-size: 13px; color: #c9b8a6;">{subj(pr)} answers {esc(a["from"])}</p>
            <p style="margin: 0; font-weight: 600;">“{esc(a["question"])}”</p>
            <a href="{yt(vids[part], a["sec"])}" style="{link}">{obj_poss(pr)} answer {ptxt}{fmt(a["sec"])}</a>
          </div>''')
    l = (spec.get('chain') or {}).get('leaves')
    sep = 'padding-top: 16px; border-top: 1px dashed rgba(254,203,122,0.35);'
    if l:
        part = l.get('part', 0)
        if next_guest:
            extra = f'''
            <a href="{{{{lp}}}}{page_of(next_guest["slug"])}" style="{link}">{esc(poss(next_guest["name"]))} episode</a>'''
            if next_guest.get('ans'):
                extra += f'''
            <a href="{yt(next_guest["vid"], next_guest["ans"])}" style="{link}">{esc(poss(next_guest["name"]))} answer at {fmt(next_guest["ans"])}</a>'''
            head = f'{subj(pr)} leaves a question for {esc(next_guest["name"])}'
        else:
            extra = f'''
            <a href="{yt(vids[part], l["sec"])}" style="{link}">{obj_poss(pr)} question at {fmt(l["sec"])}</a>''' if l.get('sec') else ''
            head = f'{obj_poss(pr)} question for the next guest'
        blocks.append(f'''<div style="display: flex; flex-direction: column; gap: 4px;{" " + sep if blocks else ""}">
            <p style="margin: 0; font-size: 13px; color: #c9b8a6;">{head}</p>
            <p style="margin: 0; font-weight: 600;">“{esc(l["question"])}”</p>{extra}
          </div>''')
    at = spec.get('atlas')
    if at:
        part = at.get('part', 0)
        blocks.append(f'''<div style="display: flex; flex-direction: column; gap: 4px;{" " + sep if blocks else ""}">
            <p style="margin: 0; font-size: 13px; color: #c9b8a6;">World Atlas · {obj_poss(pr).lower()} pick</p>
            <p style="margin: 0; font-weight: 600;">{esc(at["country"])}</p>
            <a href="{yt(vids[part], at["sec"])}" style="{link}">The draw at {fmt(at["sec"])}</a>
            <a href="{{{{lp}}}}Atlas.dc.html#{at["slug"]}" style="{link}">See it on the map</a>
          </div>''')
    if not blocks: return ''
    return f'''        <div style="padding: 24px; display: flex; flex-direction: column; gap: 16px; border: 1px solid rgba(254,203,122,0.2);">
          <p style="margin: 0; {MONO} font-size: 11px; font-weight: 800; letter-spacing: 0.12em; color: #fecb7a;">IN THE CHAIN</p>
          {(chr(10) + '          ').join(blocks)}
          <a href="{{{{lp}}}}Chain.dc.html" style="align-self: flex-start; padding: 8px 0; {MONO} font-size: 12px; font-weight: 800; letter-spacing: 0.04em;">SEE THE WHOLE CHAIN →</a>
        </div>
'''

def aside_html(spec, next_guest=None):
    p0 = spec['parts'][0]
    guest = f'''        <div style="display: flex; flex-direction: column; background: #0e0705; border: 1px solid rgba(254,203,122,0.2);">
          <div class="ep-guest-img" style="position: relative; aspect-ratio: 4 / 3; max-width: 100%; overflow: hidden;">
            <img src="/_blob/{p0["thumb"]}" alt="{esc(spec["name"])} on the Break The Routine set" style="position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; object-position: {spec.get("imgPos", "50% 30%")};">
            <div aria-hidden="true" style="position: absolute; inset: 0; background: linear-gradient(180deg, rgba(0,0,0,0) 50%, rgba(223,191,100,0.55) 100%);"></div>
          </div>
          <div style="padding: 24px; display: flex; flex-direction: column; gap: 8px;">
            <p style="margin: 0; {MONO} font-size: 11px; font-weight: 800; letter-spacing: 0.12em; color: #c9b8a6;">THE GUEST</p>
            <p style="margin: 0; {MONO} font-size: 24px; font-weight: 800; line-height: 1.15; color: #fcdf9a;">{esc(spec["name"].upper())}</p>
            <p style="margin: 0; color: #e8ddd1;">{esc(spec["bio"])}</p>
          </div>
        </div>
'''
    pol = ''
    if spec.get('polaroid'):
        pol = f'''
        <div data-polaroid="" style="padding: 24px; display: flex; flex-direction: column; align-items: center; gap: 18px; border: 1px solid rgba(254,203,122,0.2); background: repeating-linear-gradient(90deg, #0c0604 0px, #0c0604 30px, #120a06 30px, #120a06 38px);">
          <p style="align-self: flex-start; margin: 0; {MONO} font-size: 11px; font-weight: 800; letter-spacing: 0.12em; color: #fecb7a;">HALL OF FAME</p>
          <img src="/_blob/{spec["polaroid"]}" alt="Signed polaroid of {esc(spec["name"])} with Marius Iepure on the Break The Routine set" style="display: block; width: 100%; max-width: 240px; height: auto; transform: rotate(-2deg); box-shadow: 0 14px 30px rgba(0,0,0,0.55), 0 2px 6px rgba(0,0,0,0.4);">
          <a href="{{{{lp}}}}Episodes.dc.html#hof" style="align-self: flex-start; padding: 4px 0; font-size: 14px;">Every signed polaroid</a>
        </div>
'''
    ch = chain_html(spec, next_guest)
    return '\n' + guest + ('\n' + ch if ch else '') + pol + '\n      '

def nav_html(prev_row, next_row):
    card = "display: flex; flex-direction: column; gap: 6px; padding: 16px 16px 24px; border: 1px solid rgba(254,203,122,0.2); color: #ffffff; text-decoration: none;"
    img = "display: block; width: 100%; max-width: 100%; height: auto; aspect-ratio: 16 / 9; object-fit: cover; margin-bottom: 10px;"
    title = f"{MONO} font-size: 16px; font-weight: 800;"
    def one(r, label, right):
        name = r[0].split(' · ')[0]
        return (f'<a href="{{{{lp}}}}{r[6]}" style="{card}{" text-align: right;" if right else ""}"><img src="/_blob/{r[5]}" alt="{esc(name)} episode thumbnail" style="{img}">'
                f'<span style="font-size: 13px; color: #c9b8a6;">{label}</span><span style="{title}">{esc(r[1])}</span><span style="color: #fcdf9a; font-size: 15px;">{esc(name)}</span></a>')
    left = one(prev_row, f'← Previous episode · {prev_row[2]}', False) if prev_row else '<span></span>'
    if next_row:
        right = one(next_row, f'Next episode · {next_row[2]} →', True)
    else:
        right = (f'<a href="{{{{lp}}}}Episodes.dc.html" style="display: flex; flex-direction: column; justify-content: center; gap: 6px; padding: 24px; border: 1px dashed rgba(254,203,122,0.55); color: #ffffff; text-decoration: none; text-align: right;">'
                 f'<span style="font-size: 13px; color: #c9b8a6;">Latest episode</span><span style="{title}">Next guest coming soon</span><span style="color: #fcdf9a; font-size: 15px;">All episodes →</span></a>')
    return left, right

def replace_nav(s, prev_row, next_row):
    left, right = nav_html(prev_row, next_row)
    m = re.search(r'(<nav aria-label="More episodes"[^>]*>\n)(.*?)(\n    </nav>)', s, re.S)
    return s[:m.start(2)] + '      ' + left + '\n      ' + right + s[m.end(2):]

# ---------------------------------------------------------------- building the page

def render_page(spec, base, prev_row, keep_script_from=None):
    s = base
    name = spec['name']
    parts = spec['parts']
    s = re.sub(r'<title>.*?</title>', f'<title>{esc(name)} — Episode</title>', s, count=1)
    s = re.sub(r'(<a href="\{\{lp\}\}Episodes\.dc\.html" style="color: #c9b8a6;">Episodes</a> <span aria-hidden="true">/</span> <span style="color: #ffffff;">)[^<]*(</span>)',
               lambda m: m.group(1) + esc(name) + m.group(2), s, count=1)
    (a, b), blk = player_block(s, parts[0], 'WATCH ON YOUTUBE' if len(parts) == 1 else 'WATCH PART 1 ON YOUTUBE', name)
    s = s[:a] + blk + s[b:]
    m = re.search(r'(<div style="flex: 1 1 560px; min-width: 0; display: flex; flex-direction: column; gap: 12px;">\n        )(.*?)(\n      </div>\n      <div style="display: flex; flex-wrap: wrap; gap: 12px;">\n        )(.*?)(\n      </div>)', s, re.S)
    s = s[:m.start(2)] + header_col(spec) + m.group(3) + buttons(spec) + s[m.end(4):]
    m = re.search(r'(<h2 id="about-ep"[^>]*>About this episode</h2>\n          )(.*?)(\n        </section>)', s, re.S)
    s = s[:m.start(2)] + about_html(spec['about']) + s[m.end(2):]
    m = re.search(r'(<aside class="ep-aside"[^>]*>)(.*?)(</aside>)', s, re.S)
    s = s[:m.start(2)] + aside_html(spec) + s[m.end(2):]
    s = replace_nav(s, prev_row, None)
    # script data
    V = [p['vid'] for p in parts]
    T, CH = [], []
    for i, p in enumerate(parts):
        T += [[i, int(sec), txt] for sec, txt in p['transcript']]
        if len(parts) > 1: CH.append({'head': f'PART {i + 1}'})
        for c in p.get('chapters') or [{'sec': 0, 'label': 'Intro'}]:
            CH.append({'time': fmt(c['sec']), 'label': c['label'], 'url': yt_js(p['vid'], c['sec']), 'tags': []})
    s = set_js_array(s, 'V', V)
    s = set_js_array(s, 'T', T)
    s = set_js_array(s, 'CH', CH)
    if keep_script_from is None:
        s = set_js_array(s, 'R', [])
        s = set_js_array(s, 'soon', [{'label': 'REELS'}])
    else:
        s = set_js_array(s, 'R', js_array(keep_script_from, 'R') or [])
        s = set_js_array(s, 'soon', js_array(keep_script_from, 'soon') or [])
    return s

def spec_from_page(slug):
    """Rebuild a spec from an existing page, so a part 2 can be appended."""
    s = read(page_of(slug))
    name = re.search(r'<title>(.*?) — Episode</title>', s).group(1)
    rows = [r for r in reversed(episodes_rows()) if r[6] == page_of(slug)]
    V, T, CH = js_array(s, 'V'), js_array(s, 'T'), js_array(s, 'CH')
    thumbs = {r[4]: r[5] for r in rows}
    meta = {r[4]: r for r in rows}
    parts, ci = [], -1
    chapters = [[] for _ in V]
    for c in CH:
        if 'head' in c: ci += 1; continue
        ci = max(ci, 0)
        mm = re.search(r'[?&]t=(\d+)s', c['url']); vid = re.search(r'v=([^&]+)', c['url']).group(1)
        chapters[V.index(vid) if vid in V else ci].append({'sec': int(mm.group(1)) if mm else 0, 'label': c['label']})
    for i, vid in enumerate(V):
        r = meta.get(vid)
        secs = 0
        if r:
            hms = [int(x) for x in r[3].split(':')]
            secs = hms[0] * 3600 + hms[1] * 60 + hms[2] if len(hms) == 3 else hms[0] * 60 + hms[1]
        parts.append({'vid': vid, 'title': r[1] if r else '', 'date': r[2] if r else '', 'secs': secs, 'thumb': thumbs.get(vid, ''),
                      'chapters': chapters[i], 'transcript': [[t[1], t[2]] for t in T if t[0] == i]})
    about = re.findall(r'<p style="margin: 0; max-width: 680px; color: #(?:e8ddd1|c9b8a6);">(.*?)</p>', re.search(r'<h2 id="about-ep".*?</section>', s, re.S).group(0))
    bio = re.search(r'THE GUEST</p>\s*<p[^>]*>[^<]*</p>\s*<p style="margin: 0; color: #e8ddd1;">(.*?)</p>', s, re.S).group(1)
    pos = re.search(r'class="ep-guest-img".*?object-position: ([^;"]+)', s, re.S)
    pol = re.search(r'data-polaroid="".*?<img src="/_blob/([0-9a-f]+)"', s, re.S)
    return {'slug': slug, 'name': html.unescape(name), 'bio': html.unescape(bio), 'about': [html.unescape(a) for a in about],
            'imgPos': pos.group(1) if pos else '50% 30%', 'parts': parts, 'polaroid': pol.group(1) if pol else None,
            'pronoun': 'she' if re.search(r'>She (answers|leaves)|Her (question|answer)|World Atlas · her pick', s) else 'he' if re.search(r'>He (answers|leaves)|His (question|answer)|World Atlas · his pick', s) else 'they'}

# ---------------------------------------------------------------- other pages

def update_episodes_list(spec, is_part2):
    s = read('Episodes.dc.html')
    m = re.search(r'(    const list = \[\n)(.*?)(\n    \];)', s, re.S)
    lines = m.group(2).split('\n')
    page = page_of(spec['slug'])
    def jsq(x): return "'" + str(x).replace('\\', '\\\\').replace("'", "\\'") + "'"
    new_lines = []
    n_total = len(spec['parts']) if not is_part2 else None
    for i, p in enumerate(spec['parts']):
        if any(f"'{p['vid']}'" in l for l in lines): continue
        if is_part2:
            idx = spec['_part_index']
            label = f"{spec['name']} · Part {idx + 1}"
        else:
            label = spec['name'] if n_total == 1 else f"{spec['name']} · Part {i + 1}"
        new_lines.insert(0, '      [' + ', '.join(jsq(x) for x in [label, p['title'], p['date'], list_len(p['secs']), p['vid'], p['thumb'], page]) + '],')
    if is_part2:   # existing single row "Name" becomes "Name · Part 1"
        lines = [l.replace(f"['{spec['name']}', ", f"['{spec['name']} · Part 1', ", 1) if f", '{page}']" in l else l for l in lines]
    allrows = new_lines + lines
    allrows[-1] = allrows[-1].rstrip(',')
    allrows = [l if l.endswith(',') or l is allrows[-1] else l + ',' for l in allrows]
    s = s[:m.start(2)] + '\n'.join(allrows) + s[m.end(2):]
    # "15 conversations since July"
    n = len(allrows)
    s = re.sub(r'\b\d+ conversations since July', f'{n} conversations since July', s)
    write('Episodes.dc.html', s)

def update_search(spec):
    s = read('Search.dc.html')
    m = re.search(r'\n    const EPS = (\[.*?\]);\n', s, re.S)
    E = json.loads(m.group(1))
    have = {e['vid'] for e in E}
    add = [{'guest': spec['name'], 'episode': p['date'], 'vid': p['vid'], 'page': page_of(spec['slug']), 'lines': [[int(a), b] for a, b in p['transcript']]}
           for p in spec['parts'] if p['vid'] not in have]
    s = set_js_array(s, 'EPS', add[::-1] + E)
    m = re.search(r'\n    const TH = (\{.*?\});\n', s, re.S)
    TH = json.loads(m.group(1))
    for p in spec['parts']: TH[p['vid']] = p['thumb']
    s = s[:m.start(1)] + json.dumps(TH, ensure_ascii=False) + s[m.end(1):]
    write('Search.dc.html', s)

def update_prev_page(prev_page, spec):
    """Previous guest: 'next episode' card + who answers their question."""
    s = read(prev_page)
    newest = [r for r in episodes_rows() if r[6] == page_of(spec['slug'])][-1]   # first part of the new guest
    m = re.search(r'(<nav aria-label="More episodes"[^>]*>\n      )(.*?)(\n      )(.*?)(\n    </nav>)', s, re.S)
    _, right = nav_html(None, newest)
    s = s[:m.start(4)] + right + s[m.end(4):]
    a = (spec.get('chain') or {}).get('answers')
    if a:
        vids = [p['vid'] for p in spec['parts']]
        nm = spec['name']
        link = 'align-self: flex-start; padding: 4px 0; font-size: 14px;'
        block = re.search(r'<div style="padding: 24px; display: flex; flex-direction: column; gap: 16px; border: 1px solid rgba\(254,203,122,0\.2\);">\s*<p[^>]*>IN THE CHAIN</p>.*?SEE THE WHOLE CHAIN →</a>\n        </div>', s, re.S)
        if block:
            b = block.group(0)
            q = esc(a['question'])
            inner = (f'''<div style="display: flex; flex-direction: column; gap: 4px; padding-top: 16px; border-top: 1px dashed rgba(254,203,122,0.35);">
            <p style="margin: 0; font-size: 13px; color: #c9b8a6;">LEAVES_HEAD</p>
            <p style="margin: 0; font-weight: 600;">“{q}”</p>
            <a href="{{{{lp}}}}{page_of(spec["slug"])}" style="{link}">{esc(poss(nm))} episode</a>
            <a href="{yt(vids[a.get("part", 0)], a["sec"])}" style="{link}">{esc(poss(nm))} answer at {fmt(a["sec"])}</a>
          </div>''')
            # find the existing "question for the next guest" block and replace it (or add one)
            mm = re.search(r'<div style="display: flex; flex-direction: column; gap: 4px;(?: padding-top: 16px; border-top: 1px dashed rgba\(254,203,122,0\.35\);)?">\s*<p style="margin: 0; font-size: 13px; color: #c9b8a6;">((?:She|He|They) leaves a question for [^<]*|(?:Her|His|Their) question for the next guest)</p>.*?</div>', b, re.S)
            pr_word = 'She' if re.search(r'>She |>Her ', b) else 'He' if re.search(r'>He |>His ', b) else 'They'
            inner = inner.replace('LEAVES_HEAD', f'{pr_word} leaves a question for {esc(nm)}')
            if mm:
                b2 = b[:mm.start()] + inner + b[mm.end():]
            else:
                b2 = b.replace('\n          <a href="{{lp}}Chain.dc.html"', '\n          ' + inner + '\n          <a href="{{lp}}Chain.dc.html"', 1)
            s = s.replace(b, b2, 1)
    write(prev_page, s)

def apply(spec_path):
    spec = json.load(open(spec_path, encoding='utf-8'))
    is_part2 = bool(spec.get('addPartTo'))
    notes = []
    import btr_playlist as PL
    slug_now = spec.get('addPartTo') or spec['slug']
    keep_box = PL.get_box(slug_now)
    if is_part2:
        slug = spec['addPartTo']
        old = spec_from_page(slug)
        old_page = read(page_of(slug))
        merged = dict(old)
        for k in ('about', 'bio', 'imgPos', 'polaroid', 'pronoun'):
            if spec.get(k): merged[k] = spec[k]
        merged['parts'] = old['parts'] + spec['parts']
        merged['chain'] = spec.get('chain') or {}
        merged['atlas'] = spec.get('atlas')
        merged['_part_index'] = len(old['parts'])
        spec_full = merged
        order = guest_order()
        idx = order.index(page_of(slug))
        prev_row = row_for(order[idx - 1]) if idx > 0 else None
        s = render_page(spec_full, old_page, prev_row, keep_script_from=old_page)
        nxt = order[idx + 1] if idx + 1 < len(order) else None
        if nxt: s = replace_nav(s, prev_row, row_for(nxt))
        write(page_of(slug), s)
        spec_full['slug'] = slug
        update_episodes_list(dict(spec_full, parts=spec['parts'], _part_index=len(old['parts'])), True)
        update_search(dict(spec_full, parts=spec['parts']))
        import btr_pages as BP
        BP.update_main(spec_full, True)
        BP.update_chain(spec_full, True)
        if spec.get('atlas'): BP.update_atlas(dict(spec_full, atlasCards=spec.get('atlasCards')))
        if not spec_full['chain'] and old_page:   # keep the old chain block if none given
            notes.append('Chain block: none given, the page now shows no chain box: re-add it in the spec if needed.')
        notes.append(f'Updated {page_of(slug)} with part {len(merged["parts"])}.')
        target = spec_full
    else:
        if os.path.exists(os.path.join(DESIGN, page_of(spec['slug']))):
            sys.exit(f'{page_of(spec["slug"])} already exists: use "addPartTo" for a new part.')
        order = guest_order()
        prev_page = order[-1]
        prev_row = row_for(prev_page)
        base = read(TEMPLATE)
        s = render_page(spec, base, prev_row)
        write(page_of(spec['slug']), s)
        update_episodes_list(spec, False)
        update_search(spec)
        update_prev_page(prev_page, spec)
        import btr_pages as BP
        BP.update_main(spec, False)
        BP.update_chain(spec, False)
        BP.update_atlas(spec)
        notes.append(f'Created {page_of(spec["slug"])}; updated Episodes, Search and {prev_page}.')
        target = spec
    import btr_playlist as PL
    if spec.get('playlist'):
        PL.apply_spec(spec)
        notes.append(f'Playlist: "{spec["playlist"]["title"]}" by {spec["playlist"]["artist"]} on the page and the home list.')
    elif keep_box:   # part 2 without a new song: keep part 1's box
        PL.put_box(slug_now, keep_box)
    notes.append('Also updated Main (hero, previous episodes, chain teaser, World Atlas card), Chain and Atlas. Now: npm run compile && npm run build && node tools/auto/smoke.js <slug> "<name>"')
    print('\n'.join(notes))
    return target

def country(name):
    js = os.path.join(os.path.dirname(__file__), 'country_shape.mjs')
    out = subprocess.run(['node', js, name], cwd=ROOT, capture_output=True, text=True)
    sys.stdout.write(out.stdout); sys.stderr.write(out.stderr)

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'srt': print(json.dumps(srt_passages(sys.argv[2]), ensure_ascii=False))
    elif cmd == 'chapters': print(json.dumps(description_chapters(json.load(open(sys.argv[2])).get('description', '')), ensure_ascii=False))
    elif cmd == 'thumb': print(add_thumb(sys.argv[2]))
    elif cmd == 'apply': apply(sys.argv[2])
    elif cmd == 'country': country(sys.argv[2])
    elif cmd == 'atlas-sync':
        import btr_pages as BP
        done = BP.atlas_sync(sys.argv[2])
        print('Atlas cards filled from the carousel research: ' + (', '.join(done) if done else 'none'))
    elif cmd == 'playlist':
        import btr_playlist as PL
        PL.set_episode(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], int(sys.argv[6]), sys.argv[7] if len(sys.argv) > 7 else 'he')
        print('home list:', 'added' if PL.add_home(sys.argv[3], sys.argv[4]) else 'already there')
    elif cmd == 'stats':
        import btr_stats
        btr_stats.update_about()
    else: print(__doc__)
