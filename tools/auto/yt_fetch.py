#!/usr/bin/env python3
"""Finds new Break The Routine episodes on YouTube and downloads what the site needs.

Runs in GitHub Actions (YouTube can't be reached from Claude's workspace). For every upload that is
PUBLIC and longer than 15 minutes and not on the site yet, it writes data/incoming/<videoId>/:
  meta.json     title, description, publishedAt, durationSec, url
  thumb.jpg     the YouTube thumbnail (largest available)
  captions.srt  Loïc's DaVinci SRT from the shared Drive folder when one matches the title
                (oti_Subtitle_part2.srt → "Oti … Part 2"), else YouTube's captions (manual, then automatic)
A folder without captions.srt is retried on the next run (YouTube needs a while to make auto captions).
A folder with YouTube captions is upgraded to the Drive SRT if it shows up before the page is made.
Drive folder (shared by link, no login): DRIVE_SRT_FOLDER, default BREAKTHEROUTINE/SRT. Matching rules are
the Telegram bot's (bot/btrbot/drive.py), so both read the same file the same way.

Credentials (GitHub → Settings → Secrets and variables → Actions):
  YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN   (OAuth of the channel owner; see tools/auto/get_token.py)
Fallback without OAuth: YT_API_KEY + YT_CHANNEL_ID for the list, yt-dlp for the captions (less reliable).
"""
import importlib.util, json, os, re, subprocess, sys, urllib.parse, urllib.request

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
CHANNEL = {}
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
        ch = api('channels', part='contentDetails,snippet,statistics', mine='true')
    else:
        ch = api('channels', part='contentDetails,snippet,statistics', id=os.environ['YT_CHANNEL_ID'])
    print('Channel:', ch['items'][0]['snippet']['title'])
    CHANNEL.update(ch['items'][0].get('statistics', {}))
    pl = ch['items'][0]['contentDetails']['relatedPlaylists']['uploads']
    ids, page = [], None
    for _ in range(4):      # the latest 200 uploads (shorts included): every episode, for the About figures
        kw = {'part': 'contentDetails', 'playlistId': pl, 'maxResults': 50}
        if page: kw['pageToken'] = page
        res = api('playlistItems', **kw)
        ids += [i['contentDetails']['videoId'] for i in res['items']]
        page = res.get('nextPageToken')
        if not page: break
    out = []
    for k in range(0, len(ids), 50):
        out += api('videos', part='snippet,contentDetails,status,statistics', id=','.join(ids[k:k + 50]))['items']
    print(f'{len(out)} uploads checked (latest: ' + (out[0]['snippet']['title'] if out else '—') + ')')
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

DRIVE_FOLDER = os.environ.get('DRIVE_SRT_FOLDER') or '1OF0ALQxvNZb2Qc5TqYURbx04BDe4Kk5-'

def drive_mod():
    spec = importlib.util.spec_from_file_location('btr_drive', os.path.join(ROOT, 'bot', 'btrbot', 'drive.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def drive_srts():
    try:
        files = drive_mod().list_srt(DRIVE_FOLDER)
        print(f'Drive SRT folder: {len(files)} file(s) · ' + ', '.join(n for _, n in files))
        return files
    except Exception as e:
        print('Drive SRT folder not readable (YouTube captions only):', e)
        return []

def used_drive_ids():
    ids = set()
    for d in os.listdir(INCOMING):
        try: ids.add(json.load(open(os.path.join(INCOMING, d, 'meta.json'))).get('srtDriveId'))
        except Exception: pass
    return ids

def captions_drive(title, files, dest, meta):
    """Loïc's SRT for this video, if one in the Drive folder matches its title (and isn't used by another video)."""
    if not files: return False
    dm = drive_mod()
    used = used_drive_ids() - {meta.get('srtDriveId')}
    hits = [(fid, n) for fid, n in files if fid not in used and dm.matches(n, title)]
    # same part number on both sides beats "no part number" on one side
    hits.sort(key=lambda h: not (dm.part_number(h[1]) and dm.part_number(h[1]) == dm.part_number(title)))
    for fid, name in hits:
        try:
            dm.download(fid, __import__('pathlib').Path(dest + '.tmp'))
            if os.path.getsize(dest + '.tmp') < 200 or '-->' not in open(dest + '.tmp', encoding='utf-8', errors='ignore').read(4000):
                os.remove(dest + '.tmp'); continue
            os.replace(dest + '.tmp', dest)
            meta.update(captionsSource='drive', srtDriveId=fid, srtName=name)
            return True
        except Exception as e:
            print('  Drive download failed for', name, e)
    return False

def save_stats(videos):
    """Once a day: YouTube figures for About > Partners (tools/auto/btr_stats.py)."""
    import datetime
    path = os.path.join(ROOT, 'data', 'stats', 'youtube.json')
    today = datetime.date.today().isoformat()
    try:
        if json.load(open(path)).get('date') == today: return
    except Exception: pass
    # full episodes = the videos in the site's Episodes list (design/Episodes.dc.html, `const list`, 5th value)
    lst = re.search(r'const list = \[\n(.*?)\n    \];', open(os.path.join(ROOT, 'design', 'Episodes.dc.html'), encoding='utf-8').read(), re.S)
    on_site = {vals[4] for vals in (re.findall(r"'((?:[^'\\]|\\.)*)'", l) for l in lst.group(1).split('\n')) if len(vals) == 7}
    eps = [{'id': v['id'], 'title': v['snippet']['title'], 'views': int(v.get('statistics', {}).get('viewCount', 0))}
           for v in videos if v['id'] in on_site]
    if not CHANNEL.get('viewCount') or not eps: return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump({'date': today, 'subscribers': int(CHANNEL.get('subscriberCount', 0)), 'channelViews': int(CHANNEL['viewCount']),
               'episodes': sorted(eps, key=lambda e: e['title'])}, open(path, 'w'), ensure_ascii=False, indent=1)
    print(f"YouTube figures: {CHANNEL.get('subscriberCount')} subscribers, {CHANNEL['viewCount']} views, {len(eps)} full episodes")

def main():
    os.makedirs(INCOMING, exist_ok=True)
    known = known_vids()
    files = drive_srts()
    found = 0
    videos = uploads()
    try: save_stats(videos)
    except Exception as e: print('YouTube figures not saved:', e)
    for v in videos:
        vid = v['id']
        secs = iso_secs(v['contentDetails']['duration'])
        if v['status'].get('privacyStatus') != 'public' or secs < MIN_SECS or vid in known:
            continue
        d = os.path.join(INCOMING, vid)
        cap, mp = os.path.join(d, 'captions.srt'), os.path.join(d, 'meta.json')
        if os.path.exists(os.path.join(d, 'done')):
            continue
        sn = v['snippet']
        old = json.load(open(mp)) if os.path.exists(mp) else {}
        if os.path.exists(cap):
            # already has captions: only upgrade YouTube's to Loïc's SRT if it has appeared in Drive since
            if old.get('captionsSource') != 'drive' and captions_drive(sn['title'], files, cap, old):
                json.dump(old, open(mp, 'w'), ensure_ascii=False, indent=1)
                print('DRIVE SRT ' + vid + ' · ' + old['srtName'] + ' replaces the YouTube captions')
                found += 1
            continue
        os.makedirs(d, exist_ok=True)
        meta = {'id': vid, 'url': 'https://www.youtube.com/watch?v=' + vid, 'title': sn['title'], 'description': sn.get('description', ''),
                'publishedAt': sn['publishedAt'], 'durationSec': secs}
        th = sn.get('thumbnails', {})
        best = next((th[k]['url'] for k in ('maxres', 'standard', 'high', 'medium', 'default') if k in th), None)
        if best and not os.path.exists(os.path.join(d, 'thumb.jpg')):
            open(os.path.join(d, 'thumb.jpg'), 'wb').write(http(best, raw=True))
        ok = captions_drive(sn['title'], files, cap, meta)
        if not ok and token():
            try: ok = captions_oauth(vid, cap)
            except Exception as e: print('  captions API failed:', e)
            if ok: meta['captionsSource'] = 'youtube'
        if not ok:
            ok = captions_ytdlp(vid, cap)
            if ok: meta['captionsSource'] = 'youtube'
        json.dump(meta, open(mp, 'w'), ensure_ascii=False, indent=1)
        src = (' · SRT ' + meta['srtName']) if meta.get('captionsSource') == 'drive' else (' · YouTube captions' if ok else '')
        print(('NEW ' if ok else 'WAITING FOR CAPTIONS ') + vid + ' · ' + sn['title'] + f' · {secs // 60} min' + src)
        found += 1
    print(f'{found} new video(s)')

if __name__ == '__main__':
    main()
