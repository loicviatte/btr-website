"""Replace a team placeholder with a photo. Usage: team_photo.py <About.dc.html> <alt-prefix> <blob-id> [object-position]"""
import sys, re
f, who, blob = sys.argv[1], sys.argv[2], sys.argv[3]
pos = sys.argv[4] if len(sys.argv) > 4 else 'center 30%'
s = open(f).read()
m = re.search(r'<div role="img" aria-label="(' + re.escape(who) + r'[^"]*)" (style="[^"]*")>\s*<span aria-hidden="true"[^>]*>[^<]*</span>', s)
assert m, who
alt = m.group(1)
new = f'<div {m.group(2)}>\n            <img src="/_blob/{blob}" alt="{alt}" style="position: absolute; inset: 0; width: 100%; height: 100%; max-width: none; object-fit: cover; object-position: {pos};">'
s = s[:m.start()] + new + s[m.end():]
open(f, 'w').write(s)
print('ok', alt)
