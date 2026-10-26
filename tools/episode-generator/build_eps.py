import json, re, html, sys
sys.path.insert(0, '/home/claude/gen')
from epdata import INTRO, CH

P = '/tmp/claude-0/-home-claude/d6bc218f-fd68-5061-924c-755d80960da0/scratchpad/btrweb/project/'
SPOTIFY = 'https://open.spotify.com/show/033MKpAWIDCQzSHvlWeTF1'
PLAYLIST = 'https://open.spotify.com/playlist/75ezrU9QqXelJ7TwSuAT6f'
APPLE = 'https://podcasts.apple.com/us/podcast/break-the-routine/id6789345225'
MONO = "font-family: 'PP Monument Extended', 'Arial Black', sans-serif;"
LINE = 'rgba(254,203,122,0.16)'

THUMB = {'pi1IhRO8v4w': '6704faaedd6251c16887bc9024d7381e', 'yO0vuX-Ygpc': 'd6442b82364bfd30966d31b8267286d1', 'SFl--dzjGvE': '24eb7384bb059d4fdbde52ab2838ee99',
 'gmLzaixhDqo': 'bcea0d26b5e611d1a856631033e7a45c', 'RCaYgpRc-b8': '0ee862b260ef371646c30a6ad984c008', 'o3Daq6WSuzs': '061d818947d1c0a6765d98577a1cb7bf',
 '-DigDTAnOfw': 'e6e537905245e1f20fd85494316b61c3', 'c8xICOkFwEI': 'fda5fad96e887160af9fa9a1fcf78002', 'aW03-xv1Iyc': '17ff73d440c3699a9cd0f1dbb6c14d99',
 '8tsAnwQanY0': 'bd668a798a2b7ef1ef1f2012744c7a8f', 'r3ZKwpj9J5U': 'a7b5d5f61d5830023b2850ae7d54663e', '-wx7h1S8eQ8': '62bea6b1946b2ce7570d19f8db90e02c',
 'bIJ-LJsgLbE': '497a5e87cb63153785580ffe42072102', '6SKeUQM4E1k': '09c68242801f4b282a3331acd5a342fd', 'ktcEnjS1SF4': 'f50ede373b1848443c2e35c4a49fbc4b'}

# key, name, slug, pronoun, role, parts[(vid, title, date, len)], guest image pos-x
G = [
 ('KB', 'Kiera Brunton', 'kiera-brunton', 'she', 'Dancer and performer who moved from film and musical theatre into American Smooth and Ballroom, by way of Disney sets and Strictly.', [('ktcEnjS1SF4', 'From Disney to American Smooth', '13 Jul 2026', '51 min')], 6),
 ('MS', 'Michael Shelton', 'michael-shelton', 'he', 'Lawyer, theatre producer and DanceSport judge for 32 years, with senior roles in governance and discipline, including the WDSF Disciplinary Council.', [('6SKeUQM4E1k', 'From Law & Theatre to DanceSport Authority', '20 Jul 2026', '1 h 11')], 10),
 ('JD', 'Jaime Dieguez', 'jaime-dieguez', 'he', 'Started at County Dance aged seven and now helps lead the school, nearly 70 years into its story.', [('bIJ-LJsgLbE', 'From County Dance to Ballroom Leadership', '28 Jul 2026', '1 h 24')], 10),
 ('NC', 'Nicole Cutler', 'nicole-cutler', 'she', 'Latin champion, performer, coach and adjudicator. Grew up competing in South Africa and built her career in the UK.', [('-wx7h1S8eQ8', 'From South Africa to DanceSport Voice', '4 Aug 2026', '2 h 20')], 12),
 ('JW', 'James Wilson', 'james-wilson', 'he', 'British National Latin finalist turned choreographer, performer and teacher. Two seasons on Dancing with the Stars Turkey.', [('r3ZKwpj9J5U', 'From Reluctant Beginnings to a Life in Dance', '11 Aug 2026', '1 h 48')], 4),
 ('AR', 'Anthony Rutherford', 'anthony-rutherford', 'he', 'Dancer, performer, presenter and entrepreneur from Newcastle.', [('8tsAnwQanY0', 'From Ballroom to Broadcasting', '18 Aug 2026', '1 h 54')], 8),
 ('PH', 'Phemelo Mabuse', 'phemelo-mabuse', 'she', 'Former South African Latin and Ballroom champion, teacher, Ironman athlete and renewable energy leader from Pretoria.', [('aW03-xv1Iyc', 'From DanceSport to Endurance & Leadership', '25 Aug 2026', '1 h 35')], 10),
 ('IW', 'Ian Waite', 'ian-waite', 'he', 'Original Strictly Come Dancing professional, European champion and the man behind FitSteps.', [('c8xICOkFwEI', 'From Strictly to Dance for Everyone', '1 Sep 2026', '1 h 14')], 4),
 ('OO', 'Oskar Odiakosa', 'oskar-odiakosa', 'he', 'Professional Latin dancer, coach and adjudicator, and founder of Black in the Ballroom.', [('-DigDTAnOfw', 'From Ballroom Outsider to Voice for Belonging', '8 Sep 2026', '1 h 00'), ('o3Daq6WSuzs', 'From Representation to the Future of Ballroom', '15 Sep 2026', '1 h 03')], 6),
 ('PN', 'Peter Nash', 'peter-nash', 'he', 'Operations Director of the British DanceSport Association. Competitor, coach, adjudicator and examiner for 50 years.', [('RCaYgpRc-b8', '50 Years Inside the DanceSport Machinery', '24 Sep 2026', '1 h 12'), ('gmLzaixhDqo', 'Fairness, Inclusion and a Life in Dance', '30 Sep 2026', '41 min')], None),
 ('PM', 'Peter Maxwell', 'peter-maxwell', 'he', 'Former World Latin champion, theatre maker, coach, adjudicator and studio builder.', [('SFl--dzjGvE', 'Why He Left at His Peak for New York', '6 Oct 2026', '1 h 26')], 4),
 ('LS', 'Leila Stewart', 'leila-stewart', 'she', 'Former British Under 21 champion, founder of Balliamo Dance Academy, and a frontline ambulance clinician.', [('yO0vuX-Ygpc', 'The Safeguarding Questions DanceSport Can’t Ignore', '14 Oct 2026', '1 h 44')], 4),
 ('OM', 'Oti Mabuse', 'oti-mabuse', 'she', 'Two-time Strictly Come Dancing champion. Left a civil engineering degree in South Africa to chase dance in Germany and the UK.', [('pi1IhRO8v4w', 'She Left Everything Behind to Chase Her Dance Dream', '22 Oct 2026', '58 min')], 0),
]
IDX = {g[0]: i for i, g in enumerate(G)}

# chain: question i is asked by G[i] and answered by G[i+1] in video at seconds
QS = [
 ('What made you fall in love with dance?', 3960),
 ('If you could ask any composer, living or dead, to write some music for you to dance to, who would it be and why?', 4600),
 ('If you could design the competitive world, how would you do it?', 8051),
 ('Do you think it would be a good idea to have AI judges?', 6080),
 ('Which dance would you add to the ballroom category, and which to the Latin, that hasn’t been acknowledged yet? And why?', 6420),
 ('If you could change three things about your journey in dance, what would they be?', 5300),
 ('What emphasis should coaches, teachers and the sport itself put on recovery and the physical strain on the body?', 4125),
 ('If you’re a coach or a dance teacher, what is the most important thing you want from your pupil?', 3577),
 ('What are the priorities that make a good dance culture in the UK? Pick three things we should focus on.', 2151),
 ('What can we all do to improve our dance world? Just the one thing.', 4990),
 ('Do we take ballroom and Latin dancing too seriously, or not seriously enough?', 6040),
]
ANSVID = {'OO': 'o3Daq6WSuzs', 'PN': 'gmLzaixhDqo'}

ATLAS = {'KB': ('Pakistan', 'ktcEnjS1SF4', 2456), 'MS': ('Papua New Guinea', '6SKeUQM4E1k', 1935), 'JD': ('Mexico', 'bIJ-LJsgLbE', 1927),
 'NC': ('Namibia', '-wx7h1S8eQ8', 6150), 'JW': ('Chad', 'r3ZKwpj9J5U', 4068), 'AR': ('Laos', '8tsAnwQanY0', 4689), 'PH': ('Rwanda', 'aW03-xv1Iyc', 4349),
 'IW': ('Malawi', 'c8xICOkFwEI', 3677), 'OO': ('Japan', 'o3Daq6WSuzs', 2408), 'PN': ('Morocco', 'gmLzaixhDqo', 1355), 'PM': ('São Tomé and Príncipe', 'SFl--dzjGvE', 4146)}

TRACK = {'KB': ('Vivir Mi Vida', 'Marc Anthony', 'ktcEnjS1SF4', 2961), 'MS': ('Two Kites', 'Antônio Carlos Jobim', '6SKeUQM4E1k', 3930),
 'JD': ('Mil pasos', 'Soha, Antoine Essertier', 'bIJ-LJsgLbE', 4555), 'NC': ('Lolita (Cha Cha)', 'Ross Mitchell, His Band & Singers', '-wx7h1S8eQ8', 7918),
 'JW': ('NUEVAYoL', 'Bad Bunny', 'r3ZKwpj9J5U', 5991), 'AR': ('Chan Chan', 'Buena Vista Social Club', '8tsAnwQanY0', 6334),
 'PH': ('Dalie', 'Kamo Mphela, Tyler ICU, Khalil Harrison, Baby S.O.N', 'aW03-xv1Iyc', 5244), 'OO': ('Manteca', 'Dizzy Gillespie', 'o3Daq6WSuzs', 3409),
 'IW': ('A Madonna track', 'Madonna', 'c8xICOkFwEI', 4074)}

PN_REELS = [('DeFSd-jjHOX', '273b3cdc5e79224af9b588cc2e911720', 'UK national teams: kids pay for their own dreams?', 12305),
 ('DeH2WP0iZNd', 'b0b031df1f38725ad73a0e28e75d13a6', 'Would a 7-year-old recognise ballroom today?', 6988),
 ('DdzM5wEDYJ3', 'd356983f4aee509528b5b5b4402816a7', 'Tango beyond competition', 5973),
 ('Dd9kFjaCi-P', '287bee68bd5ce919e4b5c284a7503c23', 'What success really means', 2700),
 ('DeCs34qgK0l', 'd3da556d570299d2f5bc74c9b6684475', 'Para dance deserves more visibility', 2119)]

reels = json.load(open('/home/claude/gen/reels.json'))
blobs = json.load(open('/home/claude/gen/blobs.json'))

def e(s): return html.escape(s, quote=True)
def secs(t):
    p = [int(x) for x in t.split(':')]
    return p[0] * 3600 + p[1] * 60 + p[2] if len(p) == 3 else p[0] * 60 + p[1]
def fmt(s):
    h, m, x = s // 3600, s % 3600 // 60, s % 60
    return (f'{h}:{m:02d}' if h else f'{m:02d}') + f':{x:02d}'
def yt(v, t=0): return f'https://www.youtube.com/watch?v={v}' + (f'&amp;t={t}s' if t else '')
def kv(n): return f'{n/1000:.1f}k'.replace('.0k', 'k') if n >= 1000 else str(n)
def page(slug): return f'Episode-{slug}.dc.html'
def first(name): return name.split(' ')[0]

tpl = open(P + 'Episode.dc.html').read()
HEAD = tpl[:tpl.index('<main')]
FOOT = tpl[tpl.index('  <footer'):tpl.index('<script type="text/x-dc"')]

def chap_section(vid, chs, tags, label=None):
    out = []
    if label:
        out.append(f'          <p style="margin: 16px 0 0; {MONO} font-size: 12px; font-weight: 800; letter-spacing: 0.1em; color: #c9b8a6;">{label}</p>')
    out.append(f'          <ol style="list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; border-top: 1px solid {LINE};">')
    for line in chs.strip().splitlines():
        t, title = line.split(' ', 1)
        s = secs(t)
        tag = ''.join(f'<span style="margin-left: 8px; padding: 2px 8px; font-size: 12px; white-space: nowrap; background: rgba(254,203,122,0.14); color: #fecb7a;">{x}</span>' for x in tags.get((vid, s), []))
        out.append(f'            <li style="border-bottom: 1px solid {LINE};"><a href="{yt(vid, s)}" style="display: grid; grid-template-columns: 88px 1fr; gap: 16px; align-items: baseline; padding: 14px 0; color: #ffffff; text-decoration: none;"><span style="font-variant-numeric: tabular-nums; color: #fecb7a; font-weight: 600;">{t}</span><span>{e(title)}{tag}</span></a></li>')
    out.append('          </ol>')
    return '\n'.join(out)

def chapter_at(vid, s):
    starts = [secs(l.split(' ', 1)[0]) for l in CH[vid].strip().splitlines()]
    return max(x for x in starts if x <= s + 15)

def reel_card(code, blob, hook, views):
    if blob:
        media = f'<img src="/_blob/{blob}" alt="Reel: {e(hook)}" style="position: absolute; inset: 0; width: 100%; height: 100%; max-width: none; object-fit: cover;">\n              <div aria-hidden="true" style="position: absolute; inset: 0; background: linear-gradient(180deg, rgba(0,0,0,0) 45%, rgba(8,4,3,0.6) 72%, rgba(8,4,3,0.94) 100%);"></div>'
        bg = '#0e0705'
    else:
        media = '<img src="/_blob/745152d7135187f4378802fc563253b5" alt="" style="position: absolute; left: 14px; top: 14px; width: 64px; height: auto;">\n              <svg aria-hidden="true" width="44" height="44" viewBox="0 0 44 44" style="position: absolute; left: 50%; top: 42%; transform: translate(-50%, -50%);"><circle cx="22" cy="22" r="21" fill="none" stroke="#fecb7a" stroke-width="2"></circle><path d="M17 13 L32 22 L17 31 Z" fill="#fecb7a"></path></svg>'
        bg = 'linear-gradient(160deg, #2a1a0c 0%, #120a06 55%, #080403 100%); border: 1px solid rgba(254,203,122,0.28); box-sizing: border-box'
    return f'''            <a href="https://www.instagram.com/reel/{code}/" style="position: relative; display: block; aspect-ratio: 9 / 16; max-width: 100%; overflow: hidden; color: #ffffff; text-decoration: none; background: {bg};">
              {media}
              <span style="position: absolute; left: 14px; right: 14px; bottom: 14px; display: flex; flex-direction: column; gap: 6px;"><span style="{MONO} font-size: 13px; font-weight: 800; line-height: 1.25;">{e(hook)}</span><span style="font-size: 13px; color: #fecb7a; font-variant-numeric: tabular-nums;">{kv(views)} views · Instagram</span></span>
            </a>'''

def box(label, inner):
    return f'''        <div style="padding: 24px; display: flex; flex-direction: column; gap: 10px; border: 1px solid rgba(254,203,122,0.2);">
          <p style="margin: 0; {MONO} font-size: 11px; font-weight: 800; letter-spacing: 0.12em; color: #fecb7a;">{label}</p>
{inner}
        </div>'''

def btn(href, label, primary=False):
    st = 'background: #fecb7a; color: #000000;' if primary else 'border: 1px solid rgba(254,203,122,0.55); color: #ffffff;'
    return f'<a href="{href}" style="display: inline-flex; align-items: center; min-height: 48px; padding: 0 20px; {st} text-decoration: none; {MONO} font-size: 12px; font-weight: 800; letter-spacing: 0.04em;">{label}</a>'

sizes = {}
for i, (k, name, slug, pr, role, parts, posx) in enumerate(G):
    He = pr.capitalize()
    his = 'her' if pr == 'she' else 'his'
    v0 = parts[0][0]
    vlast = parts[-1][0]
    ansvid = ANSVID.get(k, v0)
    # tags on chapters
    tags = {}
    if k in ATLAS:
        c, av, at = ATLAS[k]; tags.setdefault((av, chapter_at(av, at)), []).append('On the map')
    if i > 0 and i - 1 < len(QS):
        tags.setdefault((ansvid, chapter_at(ansvid, QS[i - 1][1])), []).append('The Chain')
    if k in TRACK:
        _, _, tv, ts = TRACK[k]; tags.setdefault((tv, chapter_at(tv, ts)), []).append('Playlist')
    # parts nav
    if len(parts) > 1:
        chips = []
        for j, (v, t, d, ln) in enumerate(parts):
            lab = f'PART {j+1} · {d.upper()} · {ln.upper()}'
            st = f'display: inline-flex; align-items: center; min-height: 36px; padding: 0 14px; {MONO} font-size: 11px; font-weight: 800; letter-spacing: 0.06em; text-decoration: none;'
            if j == 0:
                chips.append(f'<span style="{st} background: #fecb7a; color: #000000;">{lab}</span>')
            else:
                chips.append(f'<a href="{yt(v)}" style="{st} border: 1px solid rgba(254,203,122,0.55); color: #ffffff;">{lab}</a>')
        meta = '<nav aria-label="Parts" style="display: flex; flex-wrap: wrap; gap: 8px;">' + ''.join(chips) + '</nav>'
        title = parts[0][1]
    else:
        v, t, d, ln = parts[0]
        meta = f'<p style="margin: 0; {MONO} font-size: 11px; font-weight: 800; letter-spacing: 0.08em; color: #c9b8a6;">{d.upper()} · {ln.upper()}</p>'
        title = t
    watch = 'WATCH PART 1 ON YOUTUBE' if len(parts) > 1 else 'WATCH ON YOUTUBE'
    intro = INTRO[v0]
    intro_html = '\n'.join(f'          <p style="margin: 0; max-width: 680px; color: {"#e8ddd1" if j == 0 else "#c9b8a6"};">{e(p)}</p>' for j, p in enumerate(intro))
    ch_rows = []
    for j, (v, *_r) in enumerate(parts):
        if len(parts) > 1:
            ch_rows.append({'head': f'PART {j + 1}'})
        for line in CH[v].strip().splitlines():
            t, title = line.split(' ', 1)
            sec = secs(t)
            ch_rows.append({'time': t, 'label': title, 'url': yt(v, sec).replace('&amp;', '&'), 'tags': tags.get((v, sec), [])})
    ch_js = json.dumps(ch_rows, ensure_ascii=False).replace('</', '<\\/')
    # reels
    if k == 'PN':
        rl = PN_REELS
    else:
        rl = [(r['code'], blobs.get(r['yt']) if r['yt'] else None, r['hook'], r['views']) for r in reels[k]]
    vids = json.load(open('/home/claude/gen/videos.json'))
    reels_js = json.dumps([{'code': c, 'hook': hk, 'views': kv(vw), 'poster': ('/_blob/' + b) if b else '', 'src': vids.get(c, '')} for c, b, hk, vw in rl], ensure_ascii=False)
    nsoon = 3 if not rl else (1 if i == len(G) - 1 else 0)
    soon_js = json.dumps([{'label': 'NEXT REEL'} for _ in range(nsoon)])
    TR = json.load(open('/home/claude/gen/trans.json'))
    vids_js = json.dumps([v for v, *_r in parts])
    trans_js = json.dumps([[pi, p[0], p[1]] for pi, (v, *_r) in enumerate(parts) for p in TR[v]], ensure_ascii=False).replace('</', '<\\/')
    # guest card image
    if k == 'PN':
        gimg, gpos = '473a5f23d5037c39a8992196778f73b5', '44% 30%'
    else:
        gimg, gpos = THUMB[v0], f'{posx}% 30%'
    # chain box
    ch = []
    if i == 0:
        ch.append(f'''          <div style="display: flex; flex-direction: column; gap: 4px;">
            <p style="margin: 0; font-size: 13px; color: #c9b8a6;">{He} started the chain</p>
            <p style="margin: 0; font-weight: 600;">The first guest of the show, so nobody had asked a question yet.</p>
          </div>''')
    elif i - 1 < len(QS):
        q, s = QS[i - 1]
        part = ' · Part 2' if k in ANSVID else ''
        ch.append(f'''          <div style="display: flex; flex-direction: column; gap: 4px;">
            <p style="margin: 0; font-size: 13px; color: #c9b8a6;">{He} answers {G[i-1][1]}</p>
            <p style="margin: 0; font-weight: 600;">“{e(q)}”</p>
            <a href="{yt(ansvid, s)}" style="align-self: flex-start; padding: 4px 0; font-size: 14px;">{He.replace('He','His').replace('She','Her')} answer{part} at {fmt(s)}</a>
          </div>''')
    else:
        ch.append(f'''          <div style="display: flex; flex-direction: column; gap: 4px;">
            <p style="margin: 0; font-size: 13px; color: #c9b8a6;">{He} answers {G[i-1][1]}</p>
            <p style="margin: 0; font-weight: 600;">Leila’s question comes in part 2 of Oti’s episode.</p>
          </div>''')
    if i < len(QS):
        q, s = QS[i]
        nx = G[i + 1]
        nv = ANSVID.get(nx[0], nx[5][0][0])
        ch.append(f'''          <div style="display: flex; flex-direction: column; gap: 4px; padding-top: 16px; border-top: 1px dashed rgba(254,203,122,0.35);">
            <p style="margin: 0; font-size: 13px; color: #c9b8a6;">{He} leaves a question for {nx[1]}</p>
            <p style="margin: 0; font-weight: 600;">“{e(q)}”</p>
            <a href="{page(nx[2])}" style="align-self: flex-start; padding: 4px 0; font-size: 14px;">{first(nx[1])}’s episode</a>
            <a href="{yt(nv, s)}" style="align-self: flex-start; padding: 4px 0; font-size: 14px;">{first(nx[1])}’s answer at {fmt(s)}</a>
          </div>''')
    elif k == 'LS':
        ch.append(f'''          <div style="display: flex; flex-direction: column; gap: 4px; padding-top: 16px; border-top: 1px dashed rgba(254,203,122,0.35);">
            <p style="margin: 0; font-size: 13px; color: #c9b8a6;">She leaves a question for Oti Mabuse</p>
            <p style="margin: 0; font-weight: 600;">Oti hears it in part 2 of her episode.</p>
            <a href="{page('oti-mabuse')}" style="align-self: flex-start; padding: 4px 0; font-size: 14px;">Oti’s episode</a>
          </div>''')
    else:
        ch.append(f'''          <div style="display: flex; flex-direction: column; gap: 4px; padding-top: 16px; border-top: 1px dashed rgba(254,203,122,0.35);">
            <p style="margin: 0; font-size: 13px; color: #c9b8a6;">Her question for the next guest</p>
            <p style="margin: 0; font-weight: 600;">Coming in part 2.</p>
          </div>''')
    if k in ATLAS:
        c, av, at = ATLAS[k]
        ch.append(f'''          <div style="display: flex; flex-direction: column; gap: 4px; padding-top: 16px; border-top: 1px dashed rgba(254,203,122,0.35);">
            <p style="margin: 0; font-size: 13px; color: #c9b8a6;">World Atlas · {his} pick</p>
            <p style="margin: 0; font-weight: 600;">{e(c)}</p>
            <a href="{yt(av, at)}" style="align-self: flex-start; padding: 4px 0; font-size: 14px;">The draw at {fmt(at)}</a>
            <a href="Atlas.dc.html" style="align-self: flex-start; padding: 4px 0; font-size: 14px;">See it on the map</a>
          </div>''')
    chain_box = f'''        <div style="padding: 24px; display: flex; flex-direction: column; gap: 16px; border: 1px solid rgba(254,203,122,0.2);">
          <p style="margin: 0; {MONO} font-size: 11px; font-weight: 800; letter-spacing: 0.12em; color: #fecb7a;">IN THE CHAIN</p>
{chr(10).join(ch)}
          <a href="Chain.dc.html" style="align-self: flex-start; padding: 8px 0; {MONO} font-size: 12px; font-weight: 800; letter-spacing: 0.04em;">SEE THE WHOLE CHAIN →</a>
        </div>'''
    track_box = ''
    if k in TRACK:
        tt, ta, tv, ts = TRACK[k]
        inner = f'''          <p style="margin: 0; font-weight: 600;">{e(tt)}</p>
          <p style="margin: 0; color: #c9b8a6;">{e(ta)}</p>
          <a href="{yt(tv, ts)}" style="align-self: flex-start; padding: 4px 0; font-size: 14px;">Why {pr} picked it, at {fmt(ts)}</a>
          <a href="{PLAYLIST}" style="align-self: flex-start; padding: 4px 0; font-size: 15px;">Break The Routine curated on Spotify →</a>'''
        track_box = box(f'{his.upper()} TRACK FOR THE PLAYLIST', inner)
    # prev / next
    nav = []
    if i > 0:
        p = G[i - 1]; pv = p[5][-1][0]
        nav.append(f'<a href="{page(p[2])}" style="display: flex; flex-direction: column; gap: 6px; padding: 16px 16px 24px; border: 1px solid rgba(254,203,122,0.2); color: #ffffff; text-decoration: none;"><img src="/_blob/{THUMB[pv]}" alt="{e(p[1])} episode thumbnail" style="display: block; width: 100%; max-width: 100%; height: auto; aspect-ratio: 16 / 9; object-fit: cover; margin-bottom: 10px;"><span style="font-size: 13px; color: #c9b8a6;">← Previous episode · {p[5][0][2]}</span><span style="{MONO} font-size: 16px; font-weight: 800;">{e(p[5][0][1])}</span><span style="color: #fcdf9a; font-size: 15px;">{e(p[1])}</span></a>')
    else:
        nav.append('<span></span>')
    if i < len(G) - 1:
        n = G[i + 1]; nv0 = n[5][0][0]
        nav.append(f'<a href="{page(n[2])}" style="display: flex; flex-direction: column; gap: 6px; padding: 16px 16px 24px; border: 1px solid rgba(254,203,122,0.2); color: #ffffff; text-decoration: none; text-align: right;"><img src="/_blob/{THUMB[nv0]}" alt="{e(n[1])} episode thumbnail" style="display: block; width: 100%; max-width: 100%; height: auto; aspect-ratio: 16 / 9; object-fit: cover; margin-bottom: 10px;"><span style="font-size: 13px; color: #c9b8a6;">Next episode · {n[5][0][2]} →</span><span style="{MONO} font-size: 16px; font-weight: 800;">{e(n[5][0][1])}</span><span style="color: #fcdf9a; font-size: 15px;">{e(n[1])}</span></a>')
    else:
        nav.append(f'<a href="Episodes.dc.html" style="display: flex; flex-direction: column; justify-content: center; gap: 6px; padding: 24px; border: 1px dashed rgba(254,203,122,0.55); color: #ffffff; text-decoration: none; text-align: right;"><span style="font-size: 13px; color: #c9b8a6;">Latest episode</span><span style="{MONO} font-size: 16px; font-weight: 800;">Next guest coming soon</span><span style="color: #fcdf9a; font-size: 15px;">All episodes →</span></a>')

    head = HEAD.replace('<title>Peter Nash — Episode</title>', f'<title>{e(name)} — Episode</title>')
    body = f'''<main style="max-width: 1440px; margin: 0 auto; box-sizing: border-box; padding: 28px clamp(16px, 4vw, 56px) 96px; display: flex; flex-direction: column; gap: 36px;">

    <p style="margin: 0; font-size: 14px; color: #c9b8a6;"><a href="Main.dc.html" style="color: #c9b8a6;">Home</a> <span aria-hidden="true">/</span> <a href="Episodes.dc.html" style="color: #c9b8a6;">Episodes</a> <span aria-hidden="true">/</span> <span style="color: #ffffff;">{e(name)}</span></p>

    <div style="position: relative; width: 100%; aspect-ratio: 16 / 9; max-width: 100%; overflow: hidden; container-type: inline-size; background: #080403;">
      <img src="/_blob/{THUMB[v0]}" alt="{e(name)} and Marius Iepure on the Break The Routine set" style="position: absolute; inset: 0; width: 100%; height: 100%; max-width: none; object-fit: cover;">
      <a href="{yt(v0)}" style="position: absolute; left: 3.2%; bottom: 5.5%; display: inline-flex; align-items: center; gap: 1cqw; min-height: 44px; padding: 1cqw 1.6cqw; background: #fecb7a; color: #000000; text-decoration: none; {MONO} font-size: max(12px, 1.05cqw); font-weight: 800; letter-spacing: 0.04em;">
        <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true" style="flex: none;"><path d="M4 2.5 L15 9 L4 15.5 Z" fill="#000000"></path></svg>
        {watch}
      </a>
    </div>

    <div style="display: flex; flex-wrap: wrap; gap: 24px 48px; align-items: flex-end; justify-content: space-between;">
      <div style="flex: 1 1 560px; min-width: 0; display: flex; flex-direction: column; gap: 12px;">
        {meta}
        <h1 style="margin: 0; {MONO} font-size: clamp(26px, 3.2vw, 46px); font-weight: 800; line-height: 1.08; text-wrap: balance;">{e(title)}</h1>
        <p style="margin: 0; {MONO} font-size: 18px; font-weight: 800; color: #fcdf9a;">with {e(name.upper())}</p>
      </div>
      <div style="display: flex; flex-wrap: wrap; gap: 12px;">
        {btn(yt(v0), 'YOUTUBE', True)}
        {btn(SPOTIFY, 'SPOTIFY')}
        {btn(APPLE, 'APPLE PODCASTS')}
      </div>
    </div>

    <div style="display: flex; flex-wrap: wrap; gap: 56px 64px; align-items: flex-start; padding-top: 12px; border-top: 1px solid {LINE};">

      <div style="flex: 999 1 600px; min-width: 0; display: flex; flex-direction: column; gap: 64px; padding-top: 24px;">

        <section aria-labelledby="about-ep" style="display: flex; flex-direction: column; gap: 12px;">
          <h2 id="about-ep" style="margin: 0; {MONO} font-size: 20px; font-weight: 800;">About this episode</h2>
{intro_html}
        </section>

        <section aria-labelledby="chapters" style="display: flex; flex-direction: column; gap: 16px;">
          <h2 id="chapters" style="margin: 0; {MONO} font-size: 20px; font-weight: 800;">Chapters</h2>
          <ol style="list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; border-top: 1px solid {LINE};">
            <sc-for list="{{{{chRows}}}}" as="r" hint-placeholder-count="8">
              <sc-if value="{{{{r.isHead}}}}" hint-placeholder-val="{{{{false}}}}">
                <li style="padding: 22px 0 10px; border-bottom: 1px solid {LINE}; {MONO} font-size: 12px; font-weight: 800; letter-spacing: 0.1em; color: #c9b8a6;">{{{{r.head}}}}</li>
              </sc-if>
              <sc-if value="{{{{r.isRow}}}}" hint-placeholder-val="{{{{true}}}}">
                <li style="border-bottom: 1px solid {LINE};"><a href="{{{{r.url}}}}" style="display: grid; grid-template-columns: 88px 1fr; gap: 16px; align-items: baseline; padding: 14px 0; color: #ffffff; text-decoration: none;"><span style="font-variant-numeric: tabular-nums; color: #fecb7a; font-weight: 600;">{{{{r.time}}}}</span><span>{{{{r.label}}}}<sc-for list="{{{{r.tags}}}}" as="t" hint-placeholder-count="0"><span style="margin-left: 8px; padding: 2px 8px; font-size: 12px; white-space: nowrap; background: rgba(254,203,122,0.14); color: #fecb7a;">{{{{t}}}}</span></sc-for></span></a></li>
              </sc-if>
            </sc-for>
          </ol>
          <sc-if value="{{{{chCanToggle}}}}" hint-placeholder-val="{{{{false}}}}">
            <button type="button" onClick="{{{{chToggle}}}}" aria-expanded="{{{{chExpanded}}}}" style="align-self: flex-start; min-height: 46px; margin-top: 8px; padding: 0 20px; background: transparent; border: 1px solid rgba(254,203,122,0.55); border-radius: 0; color: #ffffff; {MONO} font-size: 12px; font-weight: 800; letter-spacing: 0.04em; cursor: pointer;">{{{{chToggleLabel}}}}</button>
          </sc-if>
        </section>

        <section aria-labelledby="clips" style="display: flex; flex-direction: column; gap: 20px;">
          <div style="display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 8px 24px;">
            <h2 id="clips" style="margin: 0; {MONO} font-size: 20px; font-weight: 800;">Reels from this episode</h2>
            <a href="https://www.instagram.com/breaktheroutinepodcast/reels/" style="padding: 8px 0; font-size: 15px;">All Reels on Instagram →</a>
          </div>
          <p style="margin: 0; font-size: 14px; color: #c9b8a6;">They play on their own, muted. Tap one to hear it, tap again to mute.</p>
          <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 16px;">
            <sc-for list="{{{{reels}}}}" as="r" hint-placeholder-count="5">
              <div style="position: relative; aspect-ratio: 9 / 16; max-width: 100%; overflow: hidden; background: #0e0705; outline: {{{{r.ring}}}};">
                <sc-if value="{{{{r.hasPoster}}}}" hint-placeholder-val="{{{{true}}}}">
                  <img src="{{{{r.poster}}}}" alt="" style="position: absolute; inset: 0; width: 100%; height: 100%; max-width: none; object-fit: cover;">
                </sc-if>
                <sc-if value="{{{{r.noPoster}}}}" hint-placeholder-val="{{{{false}}}}">
                  <div aria-hidden="true" style="position: absolute; inset: 0; background: linear-gradient(160deg, #2a1a0c 0%, #120a06 55%, #080403 100%); border: 1px solid rgba(254,203,122,0.28);">
                    <img src="/_blob/745152d7135187f4378802fc563253b5" alt="" style="position: absolute; left: 14px; top: 14px; width: 64px; height: auto;">
                  </div>
                </sc-if>
                <sc-if value="{{{{r.hasVideo}}}}" hint-placeholder-val="{{{{false}}}}">
                  <video src="{{{{r.src}}}}" poster="{{{{r.poster}}}}" ref="{{{{r.ref}}}}" autoplay="" muted="" loop="" playsinline="" preload="metadata" style="position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; background: #0e0705;"></video>
                </sc-if>
                <div aria-hidden="true" style="position: absolute; inset: 0; pointer-events: none; background: linear-gradient(180deg, rgba(0,0,0,0) 45%, rgba(8,4,3,0.6) 72%, rgba(8,4,3,0.94) 100%);"></div>
                <sc-if value="{{{{r.hasVideo}}}}" hint-placeholder-val="{{{{false}}}}">
                  <button type="button" onClick="{{{{r.toggle}}}}" aria-pressed="{{{{r.pressed}}}}" aria-label="{{{{r.label}}}}" style="position: absolute; inset: 0; width: 100%; height: 100%; padding: 0; background: transparent; border: 0; border-radius: 0; cursor: pointer;"></button>
                  <span aria-hidden="true" style="position: absolute; top: 10px; right: 10px; display: grid; place-items: center; width: 34px; height: 34px; border-radius: 50%; pointer-events: none; {{{{r.badgeStyle}}}}">
                    <sc-if value="{{{{r.on}}}}" hint-placeholder-val="{{{{false}}}}"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5 6 9H2v6h4l5 4V5z"></path><path d="M15.5 8.5a5 5 0 0 1 0 7"></path><path d="M19 5a10 10 0 0 1 0 14"></path></svg></sc-if>
                    <sc-if value="{{{{r.off}}}}" hint-placeholder-val="{{{{true}}}}"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5 6 9H2v6h4l5 4V5z"></path><path d="m22 9-6 6"></path><path d="m16 9 6 6"></path></svg></sc-if>
                  </span>
                </sc-if>
                <sc-if value="{{{{r.noVideo}}}}" hint-placeholder-val="{{{{true}}}}">
                  <a href="{{{{r.ig}}}}" aria-label="{{{{r.igLabel}}}}" style="position: absolute; inset: 0; display: grid; place-items: center;"><svg aria-hidden="true" width="44" height="44" viewBox="0 0 44 44" style="margin-bottom: 30%;"><circle cx="22" cy="22" r="21" fill="rgba(8,4,3,0.55)" stroke="#fecb7a" stroke-width="2"></circle><path d="M17 13 L32 22 L17 31 Z" fill="#fecb7a"></path></svg></a>
                </sc-if>
                <span style="position: absolute; left: 12px; right: 12px; bottom: 12px; display: flex; flex-direction: column; gap: 4px; pointer-events: none;">
                  <span style="{MONO} font-size: 13px; font-weight: 800; line-height: 1.25;">{{{{r.hook}}}}</span>
                  <a href="{{{{r.ig}}}}" style="align-self: flex-start; padding: 6px 0; font-size: 13px; color: #fecb7a; font-variant-numeric: tabular-nums; text-decoration: none; pointer-events: auto;">{{{{r.views}}}} views · Instagram ↗</a>
                </span>
              </div>
            </sc-for>
            <sc-for list="{{{{soon}}}}" as="s" hint-placeholder-count="1">
              <a href="https://www.instagram.com/breaktheroutinepodcast/" style="position: relative; display: flex; flex-direction: column; justify-content: center; align-items: center; gap: 10px; aspect-ratio: 9 / 16; max-width: 100%; box-sizing: border-box; padding: 16px; border: 2px dashed rgba(254,203,122,0.55); color: #ffffff; text-decoration: none; text-align: center;">
                <svg aria-hidden="true" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#fecb7a" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 2"></path></svg>
                <span style="{MONO} font-size: 11px; font-weight: 800; letter-spacing: 0.12em; color: #fecb7a;">{{{{s.label}}}}</span>
                <span style="{MONO} font-size: 14px; font-weight: 800; line-height: 1.25;">Coming soon</span>
                <span style="font-size: 13px; color: #c9b8a6;">Follow on Instagram so you don’t miss it</span>
              </a>
            </sc-for>
          </div>
        </section>

        <section aria-labelledby="transcript" style="display: flex; flex-direction: column; gap: 16px;">
          <div style="display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 12px 24px;">
            <h2 id="transcript" style="margin: 0; {MONO} font-size: 20px; font-weight: 800;">Transcript</h2>
            <div style="display: flex; flex-direction: column; gap: 4px; flex: 0 1 340px; min-width: 0;">
              <label for="tq" style="font-size: 13px; color: #c9b8a6;">Search this episode</label>
              <input id="tq" type="search" value="{{{{tq}}}}" onChange="{{{{onTq}}}}" placeholder="A word or a name" autocomplete="off" style="min-height: 46px; box-sizing: border-box; padding: 0 14px; background: #120a06; border: 1px solid rgba(254,203,122,0.35); border-radius: 0; color: #ffffff; font: inherit; font-size: 16px;">
            </div>
          </div>
          <p aria-live="polite" style="margin: 0; font-size: 14px; color: #c9b8a6;">{{{{tSummary}}}}</p>
          <div style="display: flex; flex-direction: column; gap: 18px; padding: 28px; background: #0e0705; border: 1px solid rgba(254,203,122,0.16);">
            <sc-for list="{{{{tRows}}}}" as="p" hint-placeholder-count="6">
              <div style="display: grid; grid-template-columns: 92px 1fr; gap: 16px;">
                <a href="{{{{p.url}}}}" aria-label="{{{{p.aria}}}}" style="align-self: start; padding: 2px 0; font-size: 14px; font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap;">{{{{p.time}}}}</a>
                <p style="margin: 0; color: #e8ddd1;">{{{{p.before}}}}<span style="{{{{p.markStyle}}}}">{{{{p.match}}}}</span>{{{{p.after}}}}</p>
              </div>
            </sc-for>
            <sc-if value="{{{{tCanToggle}}}}" hint-placeholder-val="{{{{true}}}}">
              <button type="button" onClick="{{{{tToggle}}}}" aria-expanded="{{{{tExpanded}}}}" style="align-self: flex-start; min-height: 46px; padding: 0 20px; background: transparent; border: 1px solid rgba(254,203,122,0.55); border-radius: 0; color: #ffffff; {MONO} font-size: 12px; font-weight: 800; letter-spacing: 0.04em; cursor: pointer;">{{{{tToggleLabel}}}}</button>
            </sc-if>
          </div>
          <p style="margin: 0; font-size: 13px; color: #a8998b;">Transcribed automatically from the episode audio, so some names may be misspelled. Tap a time to play that moment on YouTube.</p>
        </section>
      </div>

      <aside aria-label="About the guest" style="flex: 1 1 340px; min-width: 0; display: flex; flex-direction: column; gap: 20px; padding-top: 24px;">

        <div style="display: flex; flex-direction: column; background: #0e0705; border: 1px solid rgba(254,203,122,0.2);">
          <div style="position: relative; aspect-ratio: 4 / 3; max-width: 100%; overflow: hidden;">
            <img src="/_blob/{gimg}" alt="{e(name)} on the Break The Routine set" style="position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; object-position: {gpos};">
            <div aria-hidden="true" style="position: absolute; inset: 0; background: linear-gradient(180deg, rgba(0,0,0,0) 50%, rgba(223,191,100,0.55) 100%);"></div>
          </div>
          <div style="padding: 24px; display: flex; flex-direction: column; gap: 8px;">
            <p style="margin: 0; {MONO} font-size: 11px; font-weight: 800; letter-spacing: 0.12em; color: #c9b8a6;">THE GUEST</p>
            <p style="margin: 0; {MONO} font-size: 24px; font-weight: 800; line-height: 1.15; color: #fcdf9a;">{e(name.upper())}</p>
            <p style="margin: 0; color: #e8ddd1;">{e(role)}</p>
          </div>
        </div>

{chain_box}
{track_box}
      </aside>
    </div>

    <nav aria-label="More episodes" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; padding-top: 32px; border-top: 1px solid {LINE};">
      {nav[0]}
      {nav[1]}
    </nav>
  </main>

'''
    nch = sum(len(CH[v].strip().splitlines()) for v, *_ in parts)
    h = 3350 + min(nch, 21) * 50
    sizes[page(slug)] = (h, name)
    script = f'''<script type="text/x-dc" data-dc-script data-props='{{"$preview":{{"width":1440,"height":{h}}}}}'>
class Component extends DCLogic {{
  constructor(props) {{
    super(props);
    this.state = {{ on: -1, tq: '', tAll: false, chAll: false }};
    this.vids = {{}};
  }}
  renderVals() {{
    const R = {reels_js};
    const on = this.state.on;
    const reels = R.map((r, i) => ({{
      hook: r.hook,
      views: r.views,
      poster: r.poster,
      src: r.src,
      ig: 'https://www.instagram.com/reel/' + r.code + '/',
      igLabel: 'Watch on Instagram: ' + r.hook,
      hasPoster: !!r.poster,
      noPoster: !r.poster,
      hasVideo: !!r.src,
      noVideo: !r.src,
      on: on === i,
      off: on !== i,
      pressed: on === i ? 'true' : 'false',
      label: (on === i ? 'Mute: ' : 'Play with sound: ') + r.hook,
      ring: on === i ? '3px solid #fecb7a' : 'none',
      badgeStyle: on === i ? 'background: #fecb7a; color: #000000;' : 'background: rgba(8,4,3,0.7); color: #ffffff;',
      ref: (el) => {{
        if (!el) return;
        this.vids[i] = el;
        el.muted = this.state.on !== i;
        if (el.paused) el.play().catch(() => {{}});
      }},
      toggle: () => {{
        const next = this.state.on === i ? -1 : i;
        Object.keys(this.vids).forEach((k) => {{
          const v = this.vids[k];
          if (!v) return;
          v.muted = Number(k) !== next;
          if (Number(k) === next) {{ v.currentTime = 0; v.play().catch(() => {{}}); }}
        }});
        this.setState({{ on: next }});
      }}
    }}));
    const soon = {soon_js};
    const V = {vids_js};
    const T = {trans_js};
    const fmt = (s) => {{ const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60; return (h ? h + ':' + String(m).padStart(2, '0') : String(m).padStart(2, '0')) + ':' + String(x).padStart(2, '0'); }};
    const tq = (this.state.tq || '').trim();
    const tl = tq.toLowerCase();
    const mk = (r, at) => {{
      const p = V.length > 1 ? 'P' + (r[0] + 1) + ' · ' : '';
      const base = {{ time: p + fmt(r[1]), url: 'https://www.youtube.com/watch?v=' + V[r[0]] + (r[1] ? '&t=' + r[1] + 's' : ''), aria: 'Play from ' + p + fmt(r[1]) + ' on YouTube' }};
      if (at < 0) return {{ ...base, before: r[2], match: '', after: '', markStyle: 'display: none;' }};
      return {{ ...base, before: r[2].slice(0, at), match: r[2].slice(at, at + tq.length), after: r[2].slice(at + tq.length), markStyle: 'background: #fecb7a; color: #000000; padding: 0 2px;' }};
    }};
    let tRows, tSummary, tCanToggle = false, tToggleLabel = '';
    if (tl.length > 1) {{
      const hits = [];
      T.forEach((r) => {{ const at = r[2].toLowerCase().indexOf(tl); if (at >= 0) hits.push(mk(r, at)); }});
      tRows = hits.slice(0, 80);
      tSummary = hits.length ? hits.length + (hits.length === 1 ? ' moment mentions “' : ' moments mention “') + tq + '”' + (hits.length > 80 ? ', first 80 shown' : '') : 'Nothing about “' + tq + '” in this episode. Try another word.';
    }} else {{
      tRows = (this.state.tAll ? T : T.slice(0, 8)).map((r) => mk(r, -1));
      tSummary = 'The full conversation, ' + T.length + ' passages';
      tCanToggle = true;
      tToggleLabel = this.state.tAll ? 'SHOW LESS' : 'READ THE FULL TRANSCRIPT';
    }}
    const CH = {ch_js};
    let shown = 0;
    const chRows = [];
    CH.forEach((r) => {{
      if (r.head) {{ if (this.state.chAll || shown < 20) chRows.push({{ isHead: true, isRow: false, head: r.head }}); return; }}
      if (!this.state.chAll && shown >= 20) return;
      shown++;
      chRows.push({{ isHead: false, isRow: true, time: r.time, label: r.label, url: r.url, tags: r.tags }});
    }});
    return {{
      reels, soon,
      tq: this.state.tq,
      onTq: (e) => this.setState({{ tq: e.target.value }}),
      tRows, tSummary, tCanToggle, tToggleLabel,
      tExpanded: this.state.tAll ? 'true' : 'false',
      tToggle: () => this.setState({{ tAll: !this.state.tAll }}),
      chRows, chCanToggle: CH.filter((r) => !r.head).length > 20,
      chToggleLabel: this.state.chAll ? 'SHOW FEWER CHAPTERS' : 'SHOW ALL ' + CH.filter((r) => !r.head).length + ' CHAPTERS',
      chExpanded: this.state.chAll ? 'true' : 'false',
      chToggle: () => this.setState({{ chAll: !this.state.chAll }})
    }};
  }}
}}
</script>
</body>
</html>
'''
    open(P + page(slug), 'w').write(head + body + FOOT + script)

json.dump(sizes, open('/home/claude/gen/sizes.json', 'w'))
print(sizes)
