"""Atlas: the cover's '01 / 07' follows the number of cards of the picked country."""
import sys
for f in sys.argv[1:]:
    s = open(f).read()
    if 'coverN' in s: continue
    a = 'letter-spacing: 0.18em;">01 / 07</span>'
    assert s.count(a) == 1, f
    s = s.replace(a, 'letter-spacing: 0.18em;">{{coverN}}</span>')
    b = '      slideDots,'
    assert s.count(b) == 1, f
    s = s.replace(b, "      slideDots,\n      coverN: '01 / ' + String(total).padStart(2, '0'),")
    open(f, 'w').write(s); print('ok', f)
