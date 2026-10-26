#!/usr/bin/env python3
"""Finds new Break The Routine episodes on YouTube and downloads what the site needs.

Runs in GitHub Actions (YouTube can't be reached from Claude's workspace). For every upload that is
PUBLIC and longer than 15 minutes and not on the site yet, it writes data/incoming/<videoId>/:
  meta.json     title, description, publishedAt, durationSec, url
  thumb.jpg     the YouTube thumbnail (largest available)
  captions.srt  the captions (manual track if there is one, else YouTube's automatic one)
A folder without captions.srt is retried on the next run (YouTube needs a while to make auto captions).

Credentials (GitHub → Settings → Secrets and variables → Actions):
  YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN   (OAuth of the channel owner; see tools/auto/get_token.py)
Fallback without OAuth: YT_API_KEY + YT_CHANNEL_ID for the list, yt-dlp for the captions (less reliable).
"""
import json, os, re, subprocess, sys, urllib.parse, urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
INCOMING = os.path.join(ROOT, 'data', 'incoming')
MIN_SECS = 15 * 60
API = 'https://www.googleapis.com/youtube/v3/'

def http(url, data=None, headers=None, raw=False):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read()
    return body if raw else json.loads(body)

TOKEN = None
def token():
    global TOKEN
    if TOKEN is None and os.environ.get('YT_REFRESH_TOKEN'):
        body = urllib.parse.urlencode({
            'client_id': os.environ['YT_CLIENT_ID'], 'client_secret': os.environ['YT_CLIENT_SECRET'],
            'refresh_token': os.environ['YT_REFRESH_TOKEN'], 'grant_type': 'refresh_token'}).encode()
        TOKEN = http('https://oauth2.googleapis.com/token', data=body)['access_token']
    return TOKEN

def api(path, **params):
    if token():
        return http(API + path + '?' + urllib.parse.urlencode(params), headers={'Authorization': 'Bearer ' + token()})
    params['key'] = os.environ['YT_API_KEY']
    return http(API + path + '?' + urllib.parse.urlencode(params))

def iso_secs(d):
    m = re.match(r'P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', d)
    dd, h, mi, s = (int(x or 0) for x in m.groups())
    return dd * 86400 + h * 3600 + mi * 60 + s

def known_vids():
    vids = set()
    for name in os.listdir(os.path.join(ROOT, 'design')):
        if name.endswith('.dc.html'):
            vids |= set(re.findall(r'watch\?v=([A-Za-z0-9_-]{11})', open(os.path.join(ROOT, 'design', name), encoding='utf-8').read()))
    return vids

def uploads():
    if token():
        ch = api('channels', part='contentDetails', mine='true')
    else:
        ch = api('channels', part='contentDetails', id=os.environ['YT_CHANNEL_ID'])
    pl = ch['items'][0]['contentDetails']['relatedPlaylists']['uploads']
    items = api('playlistItems', part='contentDetails', playlistId=pl, maxResults=50)['items']
    ids = [i['contentDetails']['videoId'] for i in items]
    out = []
    for k in range(0, len(ids), 50):
        out += api('videos', part='snippet,contentDetails,status', id=','.join(ids[k:k + 50]))['items']
    return out

def captions_oauth(vid, dest):
    tracks = api('captions', part='snippet', videoId=vid).get('items', [])
    if not tracks: return False
    def rank(t):
        sn = t['snippet']
        return (sn.get('trackKind') != 'standard', not sn.get('language', '').startswith('en'), sn.get('status') != 'serving')
    t = sorted(tracks, key=rank)[0]
    body = http(API + 'captions/' + t['id'] + '?tfmt=srt', headers={'Authorization': 'Bearer ' + token()}, raw=True)
    if len(body) < 200: return False
    open(dest, 'wb').write(body)
    return True

def captions_ytdlp(vid, dest):
    tmp = dest + '.tmp'
    cmd = ['yt-dlp', '--skip-download', '--write-subs', '--write-auto-subs', '--sub-langs', 'en.*,en', '--sub-format', 'srt/vtt/best',
           '--convert-subs', 'srt', '-o', tmp, 'https://www.youtube.com/watch?v=' + vid]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
    except Exception as e:
        print('  yt-dlp failed:', getattr(e, 'stderr', b'')[-300:] if hasattr(e, 'stderr') else e)
        return False
    got = [f for f in os.listdir(os.path.dirname(dest)) if f.startswith(os.path.basename(tmp)) and f.endswith('.srt')]
    if not got: return False
    os.replace(os.path.join(os.path.dirname(dest), got[0]), dest)
    return True

def main():
    os.makedirs(INCOMING, exist_ok=True)
    known = known_vids()
    found = 0
    for v in uploads():
        vid = v['id']
        secs = iso_secs(v['contentDetails']['duration'])
        if v['status'].get('privacyStatus') != 'public' or secs < MIN_SECS or vid in known:
            continue
        d = os.path.join(INCOMING, vid)
        if os.path.exists(os.path.join(d, 'captions.srt')) or os.path.exists(os.path.join(d, 'done')):
            continue
        os.makedirs(d, exist_ok=True)
        sn = v['snippet']
        meta = {'id': vid, 'url': 'https://www.youtube.com/watch?v=' + vid, 'title': sn['title'], 'description': sn.get('description', ''),
                'publishedAt': sn['publishedAt'], 'durationSec': secs}
        json.dump(meta, open(os.path.join(d, 'meta.json'), 'w'), ensure_ascii=False, indent=1)
        th = sn.get('thumbnails', {})
        best = next((th[k]['url'] for k in ('maxres', 'standard', 'high', 'medium', 'default') if k in th), None)
        if best and not os.path.exists(os.path.join(d, 'thumb.jpg')):
            open(os.path.join(d, 'thumb.jpg'), 'wb').write(http(best, raw=True))
        ok = False
        if token():
            try: ok = captions_oauth(vid, os.path.join(d, 'captions.srt'))
            except Exception as e: print('  captions API failed:', e)
        if not ok:
            ok = captions_ytdlp(vid, os.path.join(d, 'captions.srt'))
        print(('NEW ' if ok else 'WAITING FOR CAPTIONS ') + vid + ' · ' + sn['title'] + f' · {secs // 60} min')
        found += 1
    print(f'{found} new video(s)')

if __name__ == '__main__':
    main()
