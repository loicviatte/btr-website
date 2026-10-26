"""Footer: a small Privacy link on the credit row (the credit text itself is unchanged)."""
import sys
OLD = '<p style="margin: 0; padding-top: 24px; border-top: 1px solid rgba(254,203,122,0.16); font-size: 14px; color: #a8998b;">A Dance United &amp; Oti Marius Dance Studio Production · © 2026 Break The Routine</p>'
NEW = ('<div style="display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 8px 24px; padding-top: 24px; border-top: 1px solid rgba(254,203,122,0.16);">'
       '<p style="margin: 0; font-size: 14px; color: #a8998b;">A Dance United &amp; Oti Marius Dance Studio Production · © 2026 Break The Routine</p>'
       '<a href="/privacy" style="padding: 4px 0; font-size: 14px; color: #a8998b;">Privacy</a></div>')
n = 0
for f in sys.argv[1:]:
    s = open(f).read()
    if OLD in s:
        open(f, 'w').write(s.replace(OLD, NEW)); n += 1
print(n)
