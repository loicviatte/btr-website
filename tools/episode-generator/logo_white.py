"""Header logo: full white on every page except the home page; hovering it brings back the gold dancer."""
import sys, os
CSS = '.btr-logo-w{filter:brightness(0) invert(1);transition:filter .35s ease}a:hover > .btr-logo-w,a:focus-visible > .btr-logo-w{filter:none}\n'
A = '<a href="{{lp}}Main.dc.html" aria-label="Break The Routine, home" style="display: block; line-height: 0;"><img src="/_blob/745152d7135187f4378802fc563253b5"'
for f in sys.argv[1:]:
    b = os.path.basename(f)
    if b in ('Main.dc.html', 'Intro.dc.html', 'NotFound.dc.html') or b.startswith(('Phone-', 'Tablet-')): continue
    s = open(f).read()
    if 'btr-logo-w' in s or A not in s: print('skip', b); continue
    s = s.replace(A, A.replace('<img src=', '<img class="btr-logo-w" src='), 1)
    s = s.replace('</style>\n</helmet>', CSS + '</style>\n</helmet>', 1)
    open(f, 'w').write(s); print('ok', b)
