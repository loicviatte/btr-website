"""Platform links as a row of logos (Linktree style).

- Home page: the "Watch and listen wherever you are" text links become logo buttons.
- Every page with the phone menu (burger): the same logos sit above "Subscribe on YouTube".
Icons: Simple Icons (CC0), paths in social_icons.json. Idempotent.
Run: python3 tools/episode-generator/social_icons.py   (then npm run compile)
"""
import glob, json, os, re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
ICONS = json.load(open(os.path.join(os.path.dirname(__file__), 'social_icons.json')))
LINKS = [
    ('youtube', 'YouTube', 'https://www.youtube.com/@BreakTheRoutinePodcast'),
    ('spotify', 'Spotify', 'https://open.spotify.com/show/033MKpAWIDCQzSHvlWeTF1'),
    ('apple', 'Apple Podcasts', 'https://podcasts.apple.com/us/podcast/break-the-routine/id6789345225'),
    ('instagram', 'Instagram', 'https://www.instagram.com/breaktheroutinepodcast/'),
    ('tiktok', 'TikTok', 'https://www.tiktok.com/@breaktheroutinepodcast'),
]
CSS = ('.btr-soc{display:inline-grid;place-items:center;box-sizing:border-box;border:1px solid rgba(254,203,122,0.55);color:#ffffff;'
       'text-decoration:none;transition:background-color .25s ease,color .25s ease,border-color .25s ease,transform .25s cubic-bezier(.16,1,.3,1)}'
       '.btr-soc svg{display:block}'
       '@media (hover: hover) and (pointer: fine){.btr-soc:hover{background:#fecb7a;border-color:#fecb7a;color:#000000;transform:translateY(-2px)}}'
       '@media (max-width: 600px){.btr-soc-home{gap:10px !important;width:100%;box-sizing:border-box}.btr-soc-home .btr-soc{width:calc((100% - 40px) / 5) !important;max-width:64px;height:auto !important;aspect-ratio:1}}'
       'details.btr-burger[open] > div > .btr-soc-row{animation:btrMenu .45s 230ms cubic-bezier(.16,1,.3,1) both}')


def row(size, icon, gap, extra=''):
    out = [f'<div class="btr-soc-row" style="display: flex; flex-wrap: wrap; gap: {gap}px;{extra}">']
    for key, label, url in LINKS:
        out.append(f'<a class="btr-soc" href="{url}" aria-label="{label}" title="{label}" style="width: {size}px; height: {size}px;">'
                   f'<svg aria-hidden="true" width="{icon}" height="{icon}" viewBox="0 0 24 24"><path fill="currentColor" d="{ICONS[key]}"></path></svg></a>')
    out.append('</div>')
    return ''.join(out)


def patch(path):
    s = open(path, encoding='utf-8').read()
    if 'btr-soc' in s or 'btr-burger' not in s:
        return False
    s = s.replace('.btr-burger{display:none}\n', '.btr-burger{display:none}\n' + CSS + '\n', 1)
    # phone menu: logos above "Subscribe on YouTube"
    m = re.search(r'\n(\s*)<a href="https://www.youtube.com/@BreakTheRoutinePodcast" style="display: inline-flex; align-self: flex-start; align-items: center; min-height: 48px; margin-top: 20px;[^>]*>Subscribe on YouTube</a>', s)
    if m:
        s = s[:m.start()] + '\n' + m.group(1) + row(48, 22, 10, ' margin-top: 24px;') + s[m.start():]
    # home page row
    h = re.search(r'(<p[^>]*>Watch and listen wherever you are</p>\s*)<div style="display: flex; flex-wrap: wrap; gap: 4px 34px;[^"]*">.*?</div>', s, re.S)
    if h:
        home = row(64, 28, 14).replace('class="btr-soc-row" style="display: flex; flex-wrap: wrap;', 'class="btr-soc-row btr-soc-home" style="display: flex; flex-wrap: nowrap;')
        home = home.replace('style="width: 64px; height: 64px;"', 'style="width: 64px; height: 64px; flex: 0 1 64px;"')
        s = s[:h.start()] + h.group(1) + home + s[h.end():]
    open(path, 'w', encoding='utf-8').write(s)
    return True


if __name__ == '__main__':
    done = [os.path.basename(p) for p in sorted(glob.glob(os.path.join(ROOT, 'design', '*.dc.html'))) if patch(p)]
    print('patched:', ', '.join(done) or 'nothing')
