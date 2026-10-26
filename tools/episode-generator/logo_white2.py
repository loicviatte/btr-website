"""Header logo v2: white logo stays still; only the dancer fades to gold on hover (gold copy layered on top)."""
import sys, re
OLD_CSS = '.btr-logo-w{filter:brightness(0) invert(1);transition:filter .35s ease}a:hover > .btr-logo-w,a:focus-visible > .btr-logo-w{filter:none}\n'
NEW_CSS = '.btr-logo-w{filter:brightness(0) invert(1)}.btr-logo-c{position:absolute;left:0;top:0;opacity:0;transition:opacity .4s ease}@media (hover: hover) and (pointer: fine){a:hover > .btr-logo-c{opacity:1}}a:focus-visible > .btr-logo-c{opacity:1}\n'
for f in sys.argv[1:]:
    s = open(f).read()
    if 'btr-logo-c' in s or 'btr-logo-w' not in s: continue
    m = re.search(r'<a href="\{\{lp\}\}Main\.dc\.html" aria-label="Break The Routine, home" style="display: block; line-height: 0;">(<img class="btr-logo-w" src="([^"]+)" alt="[^"]*" style="([^"]*)">)', s)
    assert m, f
    a_new = '<a href="{{lp}}Main.dc.html" aria-label="Break The Routine, home" style="position: relative; display: block; line-height: 0;">' + m.group(1) + f'<img class="btr-logo-c" src="{m.group(2)}" alt="" aria-hidden="true" style="{m.group(3)}">'
    s = s[:m.start()] + a_new + s[m.end():]
    assert OLD_CSS in s, f
    s = s.replace(OLD_CSS, NEW_CSS, 1)
    open(f, 'w').write(s); print('ok', f.split('/')[-1])
