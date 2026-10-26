"""Atlas: picking a country zooms until it fills most of the map (small countries like Rwanda or São Tomé too)."""
import sys
R = [
    ("const clampV = (v) => { const kk = Math.max(1, Math.min(8, v.k));", "const clampV = (v) => { const kk = Math.max(1, Math.min(40, v.k));"),
    ("const kk = Math.max(narrow ? 1.6 : 2.2, Math.min(7, Math.min(VW * 0.42 / bw, VH * 0.55 / bh)));",
     "const kk = Math.max(narrow ? 1.6 : 2.2, Math.min(36, Math.min(VW * 0.78 / bw, VH * 0.78 / bh)));"),
    ("const nk = Math.max(1, Math.min(8, v.k * f));", "const nk = Math.max(1, Math.min(40, v.k * f));"),
]
for f in sys.argv[1:]:
    s = open(f).read()
    for a, b in R:
        if b in s: continue
        assert a in s, (f, a[:40]); s = s.replace(a, b)
    open(f, 'w').write(s); print('ok', f)
# narrow (phone) layout: also sync on mount, so the statically rendered site picks it up after hydration
for f in sys.argv[1:]:
    s = open(f).read()
    a = "    if (!this.mq) return;\n    this.onMq = () =>"
    b = "    if (!this.mq) return;\n    if (this.mq.matches !== this.state.narrow) this.setState({ narrow: this.mq.matches, view: null });\n    this.onMq = () =>"
    if b not in s:
        assert a in s, f; s = s.replace(a, b, 1); open(f, 'w').write(s); print('narrow sync', f)
# phone: country label sits under the pin, centred, so long names (São Tomé and Príncipe) stay inside the map
for f in sys.argv[1:]:
    s = open(f).read()
    a = "(right ? 'translate(calc(-100% - 22px), -50%)' : 'translate(22px, -50%)')"
    b = "(narrow ? 'translate(-50%, 24px)' : (right ? 'translate(calc(-100% - 22px), -50%)' : 'translate(22px, -50%)'))"
    if b not in s:
        assert a in s, f; s = s.replace(a, b, 1); open(f, 'w').write(s); print('label', f)
# first client render must match the static HTML (else React never patches aspect-ratio): start wide, switch on mount
for f in sys.argv[1:]:
    s = open(f).read()
    a = "narrow: !!(mq && mq.matches) };"
    if a in s: s = s.replace(a, "narrow: false };", 1); open(f, 'w').write(s); print('hydration-safe', f)
