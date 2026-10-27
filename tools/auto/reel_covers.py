#!/usr/bin/env python3
"""Fills the missing Instagram reel covers on the episode pages ("Reels from this episode").

Runs in the GitHub Action (Instagram can't be reached from Claude's workspace). For every reel in a
design/Episode-*.dc.html `const R` list whose "poster" is empty, it gets the cover image:
  1. from data/stats/metricool.json "reelCovers" ([reel url, image url] rows the scheduled task saves from Metricool;
     Metricool only knows reels from late August 2026 on),
  2. else from the reel's public embed page (instagram.com/p/<code>/embed/),
downloads it to public/assets/<md5>.jpg and writes "/_blob/<md5>" into the page. Prints what it did; exit code 0 always.
After it changed something, run `npm run compile` (the workflow does).
"""
import glob, hashlib, html, json, os, re, urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
ASSETS = os.path.join(ROOT, 'public', 'assets')
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'en'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def metricool_covers():
    try:
        rows = json.load(open(os.path.join(ROOT, 'data', 'stats', 'metricool.json'))).get('reelCovers') or []
    except Exception:
        return {}
    out = {}
    for row in rows:
        m = re.search(r'/(?:reel|p)/([A-Za-z0-9_-]+)', str(row[0]))
        if m and len(row) > 1 and row[1]:
            out[m.group(1)] = row[1]
    return out


def embed_cover(code):
    page = get(f'https://www.instagram.com/p/{code}/embed/').decode('utf-8', 'ignore')
    m = re.search(r'class="EmbeddedMediaImage"[^>]*?src="([^"]+)"', page) or re.search(r'<img[^>]+class="EmbeddedMediaImage"[^>]*>', page)
    if m and m.groups():
        return html.unescape(m.group(1))
    m = re.search(r'"display_url"\s*:\s*"([^"]+)"', page) or re.search(r'"thumbnail_src"\s*:\s*"([^"]+)"', page)
    if m:
        return json.loads('"' + m.group(1) + '"')
    return None


def save(img):
    if len(img) < 5000 or img[:2] != b'\xff\xd8' and img[:4] != b'\x89PNG' and img[8:12] != b'WEBP':
        raise ValueError('not an image')
    ext = 'png' if img[:4] == b'\x89PNG' else 'webp' if img[8:12] == b'WEBP' else 'jpg'
    aid = hashlib.md5(img).hexdigest()
    os.makedirs(ASSETS, exist_ok=True)
    open(os.path.join(ASSETS, f'{aid}.{ext}'), 'wb').write(img)
    return aid


def main():
    mc = metricool_covers()
    done, failed = [], []
    for path in sorted(glob.glob(os.path.join(ROOT, 'design', 'Episode-*.dc.html'))):
        s = open(path, encoding='utf-8').read()
        m = re.search(r'const R = (\[.*?\]);\n', s)
        if not m:
            continue
        codes = [r['code'] for r in json.loads(m.group(1)) if not r.get('poster')]
        for code in codes:
            try:
                url = mc.get(code) or embed_cover(code)
                if not url:
                    raise ValueError('no cover found')
                aid = save(get(url))
            except Exception as e:
                failed.append(f'{code} ({e})')
                continue
            pat = re.compile(r'("code": "' + re.escape(code) + r'"(?:(?!"code": ).)*?"poster": )""')
            s, n = pat.subn(lambda x: x.group(1) + f'"/_blob/{aid}"', s, count=1)
            if n:
                done.append(f'{os.path.basename(path)} {code}')
        open(path, 'w', encoding='utf-8').write(s)
    print(f'Reel covers added: {len(done)}' + ''.join('\n  ' + d for d in done))
    if failed:
        print(f'Reel covers still missing: {len(failed)}' + ''.join('\n  ' + f for f in failed))


if __name__ == '__main__':
    main()
