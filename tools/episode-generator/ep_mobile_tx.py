"""Episode pages on phone/tablet (stacked layout): transcript moves to the end, just before "More episodes",
and its preview shrinks to the first 2 passages, 2 lines each. Usage: python3 ep_mobile_tx.py <files...>"""
import sys
CSS = ('@media (max-width: 1000px){.ep-cols{flex-direction:column !important;flex-wrap:nowrap !important;align-items:stretch !important}'
       '.ep-left{display:contents !important}.ep-aside{flex:none !important;order:1}.ep-tsec{order:2}}'
       '@media (max-width: 600px){.ep-tbox[data-preview="yes"]{gap:12px !important}'
       '.ep-tbox[data-preview="yes"] > .ep-trow:nth-child(n+3){display:none !important}'
       '.ep-tbox[data-preview="yes"] > .ep-trow p{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}\n')
for f in sys.argv[1:]:
    s = open(f).read()
    if 'ep-tsec' in s: print('skip', f); continue
    rep = [
        ('<div style="display: flex; flex-wrap: wrap; gap: 56px 64px; align-items: flex-start; padding-top: 12px;', '<div class="ep-cols" style="display: flex; flex-wrap: wrap; gap: 56px 64px; align-items: flex-start; padding-top: 12px;'),
        ('<div style="flex: 999 1 600px; min-width: 0; display: flex; flex-direction: column; gap: 64px; padding-top: 24px;">', '<div class="ep-left" style="flex: 999 1 600px; min-width: 0; display: flex; flex-direction: column; gap: 64px; padding-top: 24px;">'),
        ('<section aria-labelledby="transcript" style=', '<section class="ep-tsec" aria-labelledby="transcript" style='),
        ('<aside aria-label="About the guest" style=', '<aside class="ep-aside" aria-label="About the guest" style='),
        ('<div class="ep-tbox" style=', '<div class="ep-tbox" data-preview="{{tPreview}}" style='),
    ]
    for a, b in rep:
        assert s.count(a) == 1, (f, a[:50])
        s = s.replace(a, b)
    s = s.replace('</style>\n</helmet>', CSS + '</style>\n</helmet>', 1)
    a = "      tRows, tSummary, tCanToggle, tToggleLabel,"
    assert a in s
    s = s.replace(a, a + "\n      tPreview: tl.length > 1 ? 'no' : 'yes',", 1)
    open(f, 'w').write(s); print('ok', f.split('/')[-1])
