"""The guest's song for the Break The Routine playlist, on the site.

Two places: the "Every guest leaves us a song" list on the home page (design/Main.dc.html) and the
"HIS/HER TRACK FOR THE PLAYLIST" box in the episode page sidebar.

Spec field (data/episodes/<slug>.json):  "playlist": {"title": "...", "artist": "...", "sec": 4953, "part": 0}
  title/artist exactly as on Spotify; sec = the moment Marius asks for the song (in that part's video).
CLI:  python3 tools/auto/btr_auto.py playlist <slug> "<title>" "<artist>" <videoId> <sec> [he|she|they]
"""
import html, os, re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DESIGN = os.path.join(ROOT, 'design')
SPOTIFY = 'https://open.spotify.com/playlist/75ezrU9QqXelJ7TwSuAT6f'
MONO = "font-family: 'PP Monument Extended', 'Arial Black', sans-serif;"
LI = ('<li style="display: grid; grid-template-columns: 32px 1fr; gap: 12px; align-items: baseline; padding: 14px 0; '
      'border-bottom: 1px solid rgba(254,203,122,0.16);">')


def esc(s):
    return html.escape(s, quote=True)


def hms(sec):
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'


def box(title, artist, vid, sec, pronoun='he'):
    his = {'she': 'HER', 'they': 'THEIR'}.get(pronoun, 'HIS')
    who = {'she': 'she', 'they': 'they'}.get(pronoun, 'he')
    return f'''        <div data-playlist="" style="padding: 24px; display: flex; flex-direction: column; gap: 10px; border: 1px solid rgba(254,203,122,0.2);">
          <p style="margin: 0; {MONO} font-size: 11px; font-weight: 800; letter-spacing: 0.12em; color: #fecb7a;">{his} TRACK FOR THE PLAYLIST</p>
          <p style="margin: 0; font-weight: 600;">{esc(title)}</p>
          <p style="margin: 0; color: #c9b8a6;">{esc(artist)}</p>
          <a href="https://www.youtube.com/watch?v={vid}&amp;t={sec}s" style="align-self: flex-start; padding: 4px 0; font-size: 14px;">Why {who} picked it, at {hms(sec)}</a>
          <a href="{SPOTIFY}" style="align-self: flex-start; padding: 4px 0; font-size: 15px;">Break The Routine curated on Spotify →</a>
        </div>
'''


BOX_RE = r'        <div[^>]*>\n          <p[^>]*>(?:HIS|HER|THEIR) TRACK FOR THE PLAYLIST</p>.*?\n        </div>\n'


def get_box(slug):
    path = os.path.join(DESIGN, f'Episode-{slug}.dc.html')
    if not os.path.exists(path):
        return None
    m = re.search(BOX_RE, open(path, encoding='utf-8').read(), re.S)
    return m.group(0) if m else None


def set_episode(slug, title, artist, vid, sec, pronoun='he'):
    put_box(slug, box(title, artist, vid, int(sec), pronoun))


def put_box(slug, new):
    path = os.path.join(DESIGN, f'Episode-{slug}.dc.html')
    s = open(path, encoding='utf-8').read()
    old = re.search(BOX_RE, s, re.S)
    if old:
        s = s[:old.start()] + new + s[old.end():]
    else:
        # after the Chain box (its last line is the "SEE THE WHOLE CHAIN" link), else just before </aside>
        m = re.search(r'<a href="\{\{lp\}\}Chain\.dc\.html"[^>]*>[^<]*</a>\n        </div>\n', s)
        at = m.end() if m else s.index('      </aside>')
        s = s[:at] + new + s[at:]
    open(path, 'w', encoding='utf-8').write(s)


def add_home(title, artist):
    path = os.path.join(DESIGN, 'Main.dc.html')
    s = open(path, encoding='utf-8').read()
    m = re.search(r'(<ol aria-label="Tracks in the playlist"[^>]*>\n)(.*?)(\n\s*</ol>)', s, re.S)
    items = [l for l in m.group(2).split('\n') if '<li' in l]
    for l in items:   # already listed
        if f'>{esc(title)}</span>' in l:
            return False
    tpl = items[-1]
    num = re.search(r'<span style="([^"]*)">\d+</span>', tpl).group(1)
    st_t = re.findall(r'<span style="([^"]*)">', tpl)
    # template: <li><span num>NN</span><span wrap><span title>T</span><span artist>A</span></span></li>
    wrap, st_title, st_artist = st_t[1], st_t[2], st_t[3]
    indent = re.match(r'\s*', tpl).group(0)
    li_tag = re.match(r'\s*(<li[^>]*>)', tpl).group(1)
    li = (f'{indent}{li_tag}<span style="{num}">{len(items) + 1:02d}</span><span style="{wrap}">'
          f'<span style="{st_title}">{esc(title)}</span><span style="{st_artist}">{esc(artist)}</span></span></li>')
    s = s[:m.end(2)] + '\n' + li + s[m.end(2):]
    open(path, 'w', encoding='utf-8').write(s)
    return True


def apply_spec(spec):
    pl = spec.get('playlist')
    if not pl:
        return
    part = spec['parts'][min(pl.get('part', 0), len(spec['parts']) - 1)]
    slug = spec.get('addPartTo') or spec['slug']
    set_episode(slug, pl['title'], pl['artist'], part['vid'], pl['sec'], spec.get('pronoun', 'he'))
    add_home(pl['title'], pl['artist'])
