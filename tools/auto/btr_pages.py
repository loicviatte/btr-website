"""Home page, The Chain and World Atlas updates for a new episode (used by btr_auto.py apply)."""
import json, os, re, subprocess
from btr_auto import (ROOT, MONO, esc, read, write, yt, fmt, human_len, poss, episodes_rows, js_array, set_js_array, add_thumb)


def short_date(d):            # "4 Nov 2026" -> "4 Nov"
    return ' '.join(d.split(' ')[:2])


# ---------------------------------------------------------------- home page

def update_main(spec, is_part2):
    s = read('Main.dc.html')
    name, parts = spec['name'], spec['parts']
    latest = parts[-1]
    m = re.search(r'<section aria-label="Latest episode".*?</section>', s, re.S)
    b = m.group(0)
    b = re.sub(r'(<img src=")[^"]*(" alt=")[^"]*(")', lambda x: x.group(1) + '/_blob/' + latest['thumb'] + x.group(2) + esc(name + ' and Marius Iepure on set') + x.group(3), b, count=1)
    b = re.sub(r'(<a class="m-hero-btn" href=")[^"]*(")', lambda x: x.group(1) + yt(latest['vid']) + x.group(2), b, count=1)
    s = s[:m.start()] + b + s[m.end():]
    m = re.search(r'(<p style="margin: 0 0 14px;[^>]*>)LATEST EPISODE · [^<]*(</p>\s*<h1[^>]*>)[^<]*(</h1>\s*<p[^>]*>)[^<]*(</p>\s*</div>\s*<div style="display: flex; flex-wrap: wrap; gap: 12px;">\s*<a href=")[^"]*(")', s, re.S)
    lab = f'LATEST EPISODE · {latest["date"].upper()} · {human_len(latest["secs"]).upper()}' + (f' · PART {len(parts)}' if is_part2 else '')
    teaser = spec.get('teaser') or spec['bio']
    s = s[:m.start()] + m.group(1) + esc(lab) + m.group(2) + esc(latest['title']) + m.group(3) + esc(teaser) + m.group(4) + yt(latest['vid']) + m.group(5) + s[m.end():]
    # "Previous episodes": the 3 guests before the latest one
    rows = episodes_rows()
    pages = []
    for r in rows:
        if r[6] not in pages: pages.append(r[6])
    m = re.search(r'(<h2 id="eps"[^>]*>Previous episodes</h2>\s*<a [^>]*>)ALL \d+ EPISODES →(</a>\s*</div>\s*<div style="display: grid;[^>]*>\n)(.*?)(\n      </div>\n    </section>)', s, re.S)
    cards = []
    for pg in pages[1:4]:
        rs = [r for r in rows if r[6] == pg][::-1]          # oldest part first
        nm = rs[0][0].split(' · ')[0]
        if len(rs) > 1:
            meta = ' &amp; '.join(short_date(r[2]) for r in rs) + ' ' + rs[-1][2].split(' ')[-1] + f' · {len(rs)} parts'
        else:
            hms = [int(x) for x in rs[0][3].split(':')]
            secs = hms[0] * 3600 + hms[1] * 60 + hms[2] if len(hms) == 3 else hms[0] * 60 + hms[1]
            meta = f'{rs[0][2]} · {human_len(secs)}'
        cards.append(
            f'\n        <a href="{{{{lp}}}}{pg}" style="display: flex; flex-direction: column; gap: 16px; color: #ffffff; text-decoration: none; min-width: 0;">'
            f'\n          <img src="/_blob/{rs[0][5]}" alt="{esc(nm)} episode thumbnail" style="display: block; width: 100%; max-width: 100%; height: auto; aspect-ratio: 16 / 9; object-fit: cover;">'
            f'\n          <div style="display: flex; flex-direction: column; gap: 6px;">'
            f'\n            <p style="margin: 0; font-size: 13px; letter-spacing: 0.04em; color: #c9b8a6;">{meta}</p>'
            f'\n            <p style="margin: 0; {MONO} font-size: 18px; font-weight: 800; color: #fcdf9a;">{esc(nm.upper())}</p>'
            f'\n            <p style="margin: 0; font-size: 15px; color: #c9b8a6;">{esc(rs[0][1])}</p>'
            f'\n          </div>'
            f'\n        </a>\n')
    s = s[:m.start()] + m.group(1) + f'ALL {len(rows)} EPISODES →' + m.group(2) + ''.join(cards).lstrip('\n').rstrip('\n') + m.group(4) + s[m.end():]
    first_guest = rows[-1][0].split(' · ')[0]
    s = re.sub(r'\d+ guests so far, from [^<]*? to [^<]*?\.', f'{len(pages)} guests so far, from {esc(first_guest)} to {esc(name)}.', s, count=1)
    write('Main.dc.html', s)


def update_main_chain(guests, qs):
    """Home page chain teaser: last 5 guests + '?' and the latest answered question."""
    s = read('Main.dc.html')
    real = [g for g in guests if g['initials'] != '?']
    answered = [i for i, q in enumerate(qs) if q.get('ans') and not q.get('pending')]
    last_ans = answered[-1] if answered else None            # qs[i] is answered by guests[i+1]
    box = f"display: grid; place-items: center; width: 64px; height: 64px; {MONO} font-size: 14px; font-weight: 800;"
    line = '<span aria-hidden="true" style="width: 28px; height: 2px; background: rgba(254,203,122,0.5);"></span>'
    dash = '<span aria-hidden="true" style="width: 28px; height: 0; border-top: 2px dashed rgba(254,203,122,0.7);"></span>'
    lis = []
    for g in real[-5:]:
        gi = guests.index(g)
        if last_ans is not None and gi == last_ans + 1:
            sp, ln = f'<span style="{box} background: #fecb7a; color: #000000;">{g["initials"]}</span>', dash
        elif last_ans is not None and gi > last_ans + 1:
            sp, ln = f'<span style="{box} border: 2px dashed #fecb7a; color: #fecb7a;">{g["initials"]}</span>', dash
        else:
            sp, ln = f'<span style="{box} border: 1px solid rgba(254,203,122,0.4); color: #c9b8a6;">{g["initials"]}</span>', line
        lis.append(f'<li style="display: flex; align-items: center;">{sp}{ln}</li>')
    lis.append(f'<li style="display: flex; align-items: center;"><span style="display: grid; place-items: center; width: 64px; height: 64px; border: 2px dashed #fecb7a; {MONO} font-size: 24px; font-weight: 800; color: #fecb7a;">?</span></li>')
    m = re.search(r'(<ol aria-label="Guests in the chain"[^>]*>\n)(.*?)(\n          </ol>)', s, re.S)
    s = s[:m.start(2)] + '\n'.join('            ' + l for l in lis) + s[m.end(2):]
    if last_ans is not None:
        a, b = guests[last_ans], guests[last_ans + 1]
        q = qs[last_ans]
        nxt = qs[last_ans + 1] if last_ans + 1 < len(qs) else None
        nx = (f'Next: {poss(b["name"])} question, “{nxt["text"]}”' if nxt and nxt.get('kind') == 'QUESTION' and nxt.get('text')
              else f'Next: {poss(b["name"])} question for the next guest')
        m = re.search(r'(<p style="margin: 0; font-size: 13px; letter-spacing: 0.08em; text-transform: uppercase; color: #c9b8a6;">)Latest answered · [^<]*(</p>\s*<p[^>]*>)[^<]*(</p>\s*<a href=")[^"]*(" [^>]*>)[^<]*(</a>\s*<p[^>]*>)[^<]*(</p>)', s, re.S)
        s = (s[:m.start()] + m.group(1) + f'Latest answered · {esc(a["name"])} to {esc(b["name"])}' + m.group(2) + f'“{esc(q["text"])}”' + m.group(3)
             + yt(b['vid'], q['ans']) + m.group(4) + f'{esc(poss(b["name"]))} answer at {fmt(q["ans"])}' + m.group(5) + esc(nx) + m.group(6) + s[m.end():])
    write('Main.dc.html', s)


# ---------------------------------------------------------------- The Chain

def js_obj_list(block):
    """Parse the small hand-written JS object arrays of Chain.dc.html (one object per line)."""
    items = []
    for line in block.strip().split('\n'):
        line = line.strip().rstrip(',')
        if not line.startswith('{'): continue
        j = re.sub(r"'((?:[^'\\]|\\.)*)'", lambda m: json.dumps(m.group(1).replace("\\'", "'")), line)
        j = re.sub(r'([{,]\s*)(\w+):', r'\1"\2":', j)
        items.append(json.loads(j))
    return items


def js_obj_dump(o):
    parts = []
    for k, v in o.items():
        if isinstance(v, str): parts.append(f"{k}: '" + v.replace('\\', '\\\\').replace("'", "\\'") + "'")
        elif v is None: parts.append(f'{k}: null')
        elif isinstance(v, bool): parts.append(f'{k}: {"true" if v else "false"}')
        else: parts.append(f'{k}: {v}')
    return '{ ' + ', '.join(parts) + ' }'


def update_chain(spec, is_part2):
    s = read('Chain.dc.html')
    mg = re.search(r'(    const guests = \[\n)(.*?)(\n    \];)', s, re.S)
    mq = re.search(r'(    const qs = \[\n)(.*?)(\n    \];)', s, re.S)
    guests, qs = js_obj_list(mg.group(2)), js_obj_list(mq.group(2))
    ch = spec.get('chain') or {}
    parts = spec['parts']
    a, l = ch.get('answers'), ch.get('leaves')
    vid = parts[a['part']]['vid'] if a and a.get('part', 0) < len(parts) else parts[-1]['vid']
    if is_part2:
        gi = next(i for i, g in enumerate(guests) if g['name'] == spec['name'])
        guests[gi]['vid'] = vid
        dates = [p['date'] for p in parts]
        months = {d.split(' ')[1] for d in dates}
        guests[gi]['label'] = (' & '.join(d.split(' ')[0] for d in dates) + ' ' + dates[-1].split(' ')[1]) if len(months) == 1 else ' & '.join(short_date(d) for d in dates)
    else:
        nxt = next((i for i, g in enumerate(guests) if g['initials'] == '?'), len(guests))
        guests.insert(nxt, {'name': spec['name'], 'initials': spec['initials'], 'label': short_date(parts[0]['date']), 'vid': vid})
        gi = nxt
        while len(qs) < len(guests) - 1:
            qs.append({'text': '', 'kind': 'QUESTION', 'ask': None, 'ans': None})
    if a and gi >= 1:          # the question this guest answers = qs[gi-1]
        qs[gi - 1] = {'text': a['question'], 'kind': 'QUESTION', 'ask': qs[gi - 1].get('ask'), 'ans': int(a['sec'])}
    if l:                      # the question this guest leaves = qs[gi]
        qs[gi] = {'text': l['question'], 'kind': 'QUESTION', 'ask': int(l['sec']) if l.get('sec') else None, 'ans': None}
    elif gi < len(qs) and (not qs[gi].get('text') or qs[gi].get('kind') != 'QUESTION'):
        qs[gi] = {'text': f'{poss(spec["name"])} question for the next guest', 'kind': 'COMING SOON', 'ask': None, 'ans': None}
    s = s[:mg.start(2)] + ',\n'.join('      ' + js_obj_dump(g) for g in guests) + s[mg.end(2):]
    mq = re.search(r'(    const qs = \[\n)(.*?)(\n    \];)', s, re.S)
    s = s[:mq.start(2)] + ',\n'.join('      ' + js_obj_dump(q) for q in qs) + s[mq.end(2):]
    mt = re.search(r'(    const thumbs = \{\n)(.*?)(\n    \};)', s, re.S)
    pairs = dict(re.findall(r"'([^']+)': '([0-9a-f]+)'", mt.group(2)))
    for p in parts: pairs[p['vid']] = p['thumb']
    items = [f"'{k}': '{v}'" for k, v in pairs.items()]
    s = s[:mt.start(2)] + ',\n'.join('      ' + ', '.join(items[i:i + 3]) for i in range(0, len(items), 3)) + s[mt.end(2):]
    s = re.sub(r'this\.state = \{ picked: \d+,', f'this.state = {{ picked: {max(0, gi - 1)},', s, count=1)
    write('Chain.dc.html', s)
    update_main_chain(guests, qs)


# ---------------------------------------------------------------- World Atlas

def bigsize(t): return max(30, min(80, int(560 / max(4, len(t)))))
LINE_ST = f"margin: 4px 0 0; {MONO} font-size: clamp(18px, 2vw, 26px); font-weight: 800; line-height: 1.08; color: #ffffff;"
def big_st(t, color='#fecb7a'): return f"margin: 8px 0 4px; {MONO} font-size: clamp(30px, 5vw, {bigsize(t)}px); font-weight: 800; line-height: 1; color: {color}; overflow-wrap: anywhere;"
PARA0 = "margin: 0 0 0; font-size: 17px; line-height: 1.55; color: #ffffff;"
PARA = "margin: 12px 0 0; font-size: 17px; line-height: 1.55; color: #ffffff;"
TAG_ST = f"margin: 8px 0 6px; {MONO} font-size: 12px; font-weight: 800; line-height: 1.3; letter-spacing: 0.12em; color: #fecb7a;"


def segs(text):
    return [{'t': c, 'st': 'font-weight: 700;' if i % 2 else ''} for i, c in enumerate(re.split(r'\*\*(.+?)\*\*', text)) if c]


def atlas_cards(slides, country):
    """Simple slides (written by Claude from research) -> the card format of Atlas.dc.html.
    {"left": ["Latin &", "Ballroom?", {"big": "BARELY."}], "paras": ["text with **bold**", ...]}
    {"left": ["Typical dances"], "dances": [{"name": "DHAMAAL", "tag": "CENTURIES OLD · SEHWAN", "text": "…"}, …]}"""
    if not slides:
        slides = [{'left': ['Carousel', {'big': 'SOON'}], 'paras': [f'We are digging into how **{country}** dances. Follow **@breaktheroutinepodcast** on Instagram to see it first.']}]
    total = len(slides) + 1
    cards = []
    for i, sl in enumerate(slides):
        left = [{'st': big_st(x['big']), 'segs': [{'t': x['big'], 'st': ''}]} if isinstance(x, dict) else {'st': LINE_ST, 'segs': [{'t': x, 'st': ''}]} for x in sl['left']]
        if sl.get('dances'):
            groups = [{'blocks': [{'st': big_st(d['name'], '#ffffff'), 'segs': [{'t': d['name'], 'st': ''}]}, {'st': TAG_ST, 'segs': [{'t': d.get('tag', ''), 'st': ''}]},
                                  {'st': PARA0, 'segs': segs(d['text'])}]} for d in sl['dances']]
            right = 'display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px 36px;'
        else:
            groups = [{'blocks': [{'st': PARA0 if j == 0 else PARA, 'segs': segs(t)} for j, t in enumerate(sl.get('paras', []))]}]
            right = 'display: flex; flex-direction: column;'
        cards.append({'n': f'{i + 2:02d} / {total:02d}', 'left': left, 'groups': groups, 'rightStyle': right})
    return cards


def country_data(name, no):
    js = os.path.join(os.path.dirname(__file__), 'country_shape.mjs')
    svg = os.path.join(ROOT, 'data', 'tmp-country.svg')
    os.makedirs(os.path.dirname(svg), exist_ok=True)
    out = subprocess.run(['node', js, name, no, svg], cwd=ROOT, capture_output=True, text=True)
    if out.returncode: raise SystemExit('country_shape failed: ' + out.stderr)
    data = json.loads(out.stdout)
    data['svgAsset'] = add_thumb(svg)
    os.remove(svg)
    return data


def update_atlas(spec):
    at = spec.get('atlas')
    if not at: return None
    s = read('Atlas.dc.html')
    MAP, CAR = js_array(s, 'MAP'), js_array(s, 'CAR')
    no = f'{len(MAP) + 1:02d}'
    c = country_data(at.get('mapName') or at['country'], no)
    vid = spec['parts'][at.get('part', 0)]['vid']
    def q(x): return "'" + x.replace('\\', '\\\\').replace("'", "\\'") + "'"
    m = re.search(r'(    const raw = \[\n)(.*?)(\n    \];)', s, re.S)
    rows = [r.rstrip().rstrip(',') for r in m.group(2).split('\n') if r.strip()]
    rows.append(f"      {{ city: {q(at['country'])}, lat: {c['lat']}, lon: {c['lon']}, m: [[{q(spec['name'])}, {q(vid)}, {int(at['sec'])}]] }}")
    s = s[:m.start(2)] + ',\n'.join(rows) + s[m.end(2):]
    MAP.append(c['atlas'])
    s = set_js_array(s, 'MAP', MAP)
    CAR.append({'name': at['country'].upper(), 'map': '/_blob/' + c['svgAsset'], 'cards': atlas_cards(spec.get('atlasCards'), at['country'])})
    s = set_js_array(s, 'CAR', CAR)
    s = re.sub(r'(    const slugs = \[)(.*?)(\];)', lambda x: x.group(1) + x.group(2) + f", '{at['slug']}'" + x.group(3), s, count=1)
    s = re.sub(r'    const n = \d+;', f'    const n = {len(MAP)};', s, count=1)
    write('Atlas.dc.html', s)
    # home page card: country shape, pin (newest highlighted), count
    h = read('Main.dc.html')
    h = re.sub(r'(<svg class="m-atlas-shapes"[^>]*>)(.*?)(</svg>)', lambda x: x.group(1) + x.group(2) + f'<path d="{c["home"]["d"]}"></path>' + x.group(3), h, count=1, flags=re.S)
    hi = 'background: #fecb7a; box-shadow: 0 0 0 6px rgba(254,203,122,0.22);'
    h = h.replace(hi, 'background: #d29a3a; border: 2px solid #fecb7a;')
    last = list(re.finditer(r'\n(\s*)<span style="position: absolute; left: [\d.]+%; top: [\d.]+%; width: 12px;[^>]*></span>', h))[-1]
    pin = f'\n{last.group(1)}<span style="position: absolute; left: {c["home"]["left"]:.2f}%; top: {c["home"]["top"]:.2f}%; width: 12px; height: 12px; margin: -6px 0 0 -6px; box-sizing: border-box; border-radius: 50%; {hi}"></span>'
    h = h[:last.end()] + pin + h[last.end():]
    h = re.sub(r'\d+ countries from the World Atlas game', f'{len(MAP)} countries from the World Atlas game', h, count=1)
    write('Main.dc.html', h)
    return c['name']
