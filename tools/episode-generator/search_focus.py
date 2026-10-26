"""Search bar focus: no gold outline lines around the input; a gold underline inside the black bar instead."""
import sys
for f in sys.argv[1:]:
    s = open(f).read()
    if 'srch-bar' in s: print('skip', f); continue
    a = '<div style="display: flex; align-items: center; gap: 12px; min-height: 64px; box-sizing: border-box; padding: 0 20px; background: #080403;">'
    assert a in s, f
    s = s.replace(a, a.replace('<div style=', '<div class="srch-bar" style=', 1), 1)
    css = ('.srch-bar{transition:box-shadow .3s ease}'
           '.srch-bar input:focus,.srch-bar input:focus-visible{outline:none !important}'
           '.srch-bar:focus-within{box-shadow:inset 0 -3px 0 #fecb7a,0 14px 34px rgba(8,4,3,0.28)}'
           '.srch-bar input::-webkit-search-cancel-button{cursor:pointer}\n')
    s = s.replace('</style>\n</helmet>', css + '</style>\n</helmet>', 1)
    open(f, 'w').write(s); print('ok', f)
