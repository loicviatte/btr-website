"""About > Partners figures, refreshed from data/stats/*.json.

  data/stats/base.json       figures of 26 Oct 2026 + Spotify (by hand, no API) + frozen Instagram views of old reels
  data/stats/youtube.json    written by the GitHub Action once a day (subscribers, channel views, views per full episode)
  data/stats/metricool.json  written by the scheduled Claude task once a day from Metricool (Instagram followers and
                             reel views, TikTok followers and video views), raw rows as Metricool returns them

python3 tools/auto/btr_auto.py stats        → rewrites the three figures and "Figures as of …" in design/About.dc.html
A source that is missing, empty or clearly incomplete keeps the base figure (a number never drops because an API
returned nothing).
"""
import datetime, json, os, re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
STATS = os.path.join(ROOT, 'data', 'stats')
ABOUT = os.path.join(ROOT, 'design', 'About.dc.html')


def load(name):
    try:
        return json.load(open(os.path.join(STATS, name), encoding='utf-8'))
    except Exception:
        return {}


def num(x):
    try:
        return int(float(x))
    except Exception:
        return 0


def figures():
    base, yt, mc = load('base.json'), load('youtube.json'), load('metricool.json')
    dates = [base.get('asOf', '')]

    # Instagram: followers + (frozen views of reels older than Metricool's window + current views of newer reels)
    ig = dict(base['instagram'])
    if num(mc.get('instagramFollowers')) > 0:
        ig['followers'] = num(mc['instagramFollowers'])
    reels = [r for r in mc.get('reels') or [] if len(r) >= 3 and str(r[0]) >= base['instagram']['metricoolSince']]
    if reels:
        views = base['instagram']['olderReelViews'] + sum(num(r[-1]) for r in reels)
        if views >= base['instagram']['views'] * 0.95:      # a partial Metricool answer never lowers the total
            ig['views'] = views
            dates.append(mc.get('date', ''))

    # TikTok: Metricool when it returns real numbers
    tk = dict(base['tiktok'])
    if num(mc.get('tiktokFollowers')) > 0:
        tk['followers'] = num(mc['tiktokFollowers'])
    tv = sum(num(r[-1]) for r in mc.get('tiktokVideos') or [])
    if tv >= base['tiktok']['views'] * 0.95:
        tk['views'] = tv

    # YouTube: from the GitHub Action (YouTube Data API)
    y = dict(base['youtube'])
    if num(yt.get('subscribers')) > 0:
        y['subscribers'] = num(yt['subscribers'])
    elif num(mc.get('youtubeSubscribers')) > 0:      # Metricool, until the Action has written youtube.json
        y['subscribers'] = num(mc['youtubeSubscribers'])
    if num(yt.get('channelViews')) >= base['youtube']['channelViews']:
        y['channelViews'] = num(yt['channelViews'])
    eps = yt.get('episodes') or []
    if len(eps) >= base['youtube']['episodes']:
        y['episodes'] = len(eps)
        y['episodeViews'] = sum(num(e.get('views')) for e in eps)
        dates.append(yt.get('date', ''))

    sp = base['spotify']
    return {
        'followers': ig['followers'] + y['subscribers'] + sp['followers'] + tk['followers'],
        'followersBy': [('Instagram', ig['followers']), ('YouTube', y['subscribers']), ('Spotify', sp['followers']), ('TikTok', tk['followers'])],
        'avg': round((y['episodeViews'] + sp['plays']) / max(y['episodes'], 1)),
        'episodes': y['episodes'],
        'views': ig['views'] + tk['views'] + y['channelViews'] + sp['plays'],
        'viewsBy': [('Instagram', ig['views']), ('TikTok', tk['views']), ('YouTube', y['channelViews']), ('Spotify', sp['plays'])],
        'date': max(d for d in dates if d),
    }


def fmt(n):
    return f'{n:,}'


def by(pairs):
    pairs = sorted(pairs, key=lambda p: -p[1])
    return ' · '.join(f'{k} {fmt(v)}' for k, v in pairs)


def update_about():
    f = figures()
    s = open(ABOUT, encoding='utf-8').read()
    old = s

    def block(label, big, small, s):
        pat = re.compile(r'(<dt[^>]*>' + re.escape(label) + r'</dt>\s*<dd[^>]*>)[^<]*(</dd>\s*<dd[^>]*>)[^<]*(</dd>)')
        if not pat.search(s):
            raise SystemExit('About: block not found: ' + label)
        return pat.sub(lambda m: m.group(1) + big + m.group(2) + small + m.group(3), s, count=1)

    s = block('Followers across all platforms', fmt(f['followers']), by(f['followersBy']), s)
    s = block('Average views per episode', fmt(f['avg']), f'YouTube views + Spotify plays, across {f["episodes"]} full episodes', s)
    s = block('Total views, all videos', fmt(f['views']), by(f['viewsBy']), s)
    d = datetime.date.fromisoformat(f['date'])
    s = re.sub(r'Figures as of [^<.]*\.', f'Figures as of {d.day} {d.strftime("%b %Y")}.', s, count=1)
    if s != old:
        open(ABOUT, 'w', encoding='utf-8').write(s)
    print(json.dumps({k: v for k, v in f.items()}, ensure_ascii=False))
    print('About updated' if s != old else 'About unchanged')
    return s != old
