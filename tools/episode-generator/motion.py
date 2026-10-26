"""Adds the site-wide motion layer (scroll reveals, header state, hover polish, menu animation)
to every Claude Design page in a folder. Idempotent. Usage: python3 motion.py <dir>"""
import glob, os, re, sys

D = sys.argv[1]

CSS = """
/* motion */
html{scroll-behavior:smooth}
[data-rv]{transition:opacity 900ms cubic-bezier(.16,1,.3,1),transform 900ms cubic-bezier(.16,1,.3,1),color .25s ease,background-color .25s ease,border-color .25s ease;transition-delay:var(--rvd,0ms)}
[data-rv="0"]{opacity:0;transform:translateY(22px)}
img[data-rv="0"]{transform:scale(1.045)}
[data-zoom]{transition:transform 1100ms cubic-bezier(.16,1,.3,1) !important}
a:hover [data-zoom]{transform:scale(1.045)}
[data-btn]{transition:background-color .25s ease,border-color .25s ease,color .25s ease,transform .25s cubic-bezier(.16,1,.3,1),box-shadow .25s ease !important}
[data-btn="gold"]:hover{background-color:#ffe0a6 !important;transform:translateY(-2px);box-shadow:0 10px 28px rgba(254,203,122,0.22)}
[data-btn="line"]:hover{background-color:rgba(254,203,122,0.08) !important;border-color:#fecb7a !important;transform:translateY(-2px)}
[data-btn]:active{transform:translateY(0) !important}
.btr-links a{position:relative}
.btr-links a::after{content:"";position:absolute;left:0;right:0;bottom:0;height:2px;background:#fecb7a;transform:scaleX(0);transform-origin:left;transition:transform .4s cubic-bezier(.16,1,.3,1)}
.btr-links a[aria-current="page"]{border-bottom-color:transparent !important}
.btr-links a[aria-current="page"]::after{transform:scaleX(1)}
.btr-links a:hover::after{transform:scaleX(1)}
header{transition:box-shadow .4s ease,background-color .4s ease}
header[data-scrolled="1"]{box-shadow:0 12px 32px rgba(0,0,0,0.45)}
@keyframes btrMenu{from{opacity:0;transform:translateY(-8px)}to{opacity:1;transform:none}}
details.btr-burger[open] > div{animation:btrMenu .38s cubic-bezier(.16,1,.3,1) both}
details.btr-burger[open] > div > a{animation:btrMenu .45s cubic-bezier(.16,1,.3,1) both}
details.btr-burger[open] > div > a:nth-child(2){animation-delay:40ms}details.btr-burger[open] > div > a:nth-child(3){animation-delay:80ms}details.btr-burger[open] > div > a:nth-child(4){animation-delay:120ms}details.btr-burger[open] > div > a:nth-child(5){animation-delay:160ms}details.btr-burger[open] > div > a:nth-child(6){animation-delay:200ms}
@media (prefers-reduced-motion: reduce){html{scroll-behavior:auto}[data-rv]{transition:none !important;opacity:1 !important;transform:none !important}[data-zoom],[data-btn]{transition:none !important}}
"""

JS = r"""function btrMotion(root) {
  if (!root || root.__btrMotion) return;
  root.__btrMotion = true;
  const doc = root.ownerDocument, win = doc.defaultView;
  if (!win || !('IntersectionObserver' in win)) return;
  const reduce = win.matchMedia && win.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const gold = 'rgb(254, 203, 122)';
  root.querySelectorAll('a, button, summary').forEach((el) => {
    if (el.closest('header') && !el.closest('details')) { if (getComputedStyle(el).backgroundColor !== gold) return; }
    const cs = getComputedStyle(el);
    if (cs.position === 'absolute' && !el.closest('main')) return;
    if (cs.backgroundColor === gold) el.dataset.btn = 'gold';
    else if (parseFloat(cs.borderTopWidth) > 0 && cs.borderTopStyle === 'solid' && parseFloat(cs.minHeight) >= 40 && cs.display.indexOf('flex') >= 0) el.dataset.btn = 'line';
  });
  root.querySelectorAll('main a img').forEach((img) => {
    const p = img.parentElement;
    if (p && getComputedStyle(p).overflow === 'hidden') img.dataset.zoom = '1';
  });
  const header = root.querySelector('header');
  const mainEl = root.querySelector('main');
  if (header && mainEl && mainEl.firstElementChild) {
    const hh = header.offsetHeight || 80;
    const t = Array.from({ length: 21 }, (_, i) => i / 20);
    const hio = new win.IntersectionObserver((es) => { es.forEach((e) => { header.dataset.scrolled = e.boundingClientRect.top < hh - 4 ? '1' : '0'; }); }, { threshold: t });
    hio.observe(mainEl.firstElementChild);
    root.__btrHio = hio;
  }
  if (reduce) return;
  const SEL = 'main h1, main h2, main h3, main p, main img, main li, main article, main figure, main blockquote, main video, footer img, footer p';
  const SKIP = '.atl-map, .atl-track, [role="dialog"], .btr-intro, header, details, form, [aria-live], button';
  const all = Array.from(root.querySelectorAll(SEL)).filter((el) => {
    if (el.closest(SKIP)) return false;
    const cs = getComputedStyle(el);
    if ((cs.position === 'absolute' || cs.position === 'fixed') && el.tagName !== 'IMG') return false;
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    return true;
  });
  const set = new Set(all);
  const targets = all.filter((el) => { let a = el.parentElement; while (a && a !== root) { if (set.has(a)) return false; a = a.parentElement; } return true; });
  const start = () => {
    targets.forEach((el) => { el.dataset.rv = '0'; });
    let queue = [], timer = null;
    const flush = () => {
      queue.sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top || a.getBoundingClientRect().left - b.getBoundingClientRect().left);
      queue.forEach((el, i) => { el.style.setProperty('--rvd', Math.min(i * 70, 560) + 'ms'); el.dataset.rv = '1'; });
      queue = []; timer = null;
    };
    const io = new win.IntersectionObserver((es) => {
      es.forEach((e) => { if (e.isIntersecting) { queue.push(e.target); io.unobserve(e.target); } });
      if (queue.length && !timer) timer = win.setTimeout(flush, 30);
    }, { rootMargin: '0px', threshold: 0.06 });
    targets.forEach((el) => io.observe(el));
    root.__btrIo = io;
  };
  const intro = () => { const b = root.querySelector('.btr-intro'); return b && b.offsetParent !== null && getComputedStyle(b).display !== 'none'; };
  if (!intro()) { start(); return; }
  const wait = win.setInterval(() => { if (!intro()) { win.clearInterval(wait); start(); } }, 120);
  root.__btrWait = wait;
}
function btrMotionStop(root) {
  if (!root) return;
  if (root.__btrIo) root.__btrIo.disconnect();
  if (root.__btrHio) root.__btrHio.disconnect();
  if (root.__btrWait) root.ownerDocument.defaultView.clearInterval(root.__btrWait);
  root.__btrMotion = false;
}
"""

done = []
for f in sorted(glob.glob(os.path.join(D, '*.dc.html'))):
    b = os.path.basename(f)
    if b.startswith(('Tablet-', 'Phone-')) or b in ('Intro.dc.html', 'Episode.dc.html'):
        continue
    s = open(f).read()
    if 'function btrMotion' in s:
        continue
    # css
    i = s.index('</style>\n</helmet>')
    s = s[:i] + CSS.strip() + '\n' + s[i:]
    # root ref
    m = re.search(r'</helmet>\s*\n<div style="background: #080403;', s)
    assert m, b
    s = s[:m.end() - len('<div style="background: #080403;')] + '<div ref="{{motionRef}}" style="background: #080403;' + s[m.end():]
    # js
    j = s.index('class Component extends DCLogic')
    s = s[:j] + JS + s[j:]
    k = s.index("return { lp: this.props.lp ?? ''")
    s = s[:k] + "return { motionRef: this._motionRef || (this._motionRef = (el) => { if (el) { this._motionEl = el; btrMotion(el); } else { btrMotionStop(this._motionEl); } }), lp: this.props.lp ?? ''" + s[k + len("return { lp: this.props.lp ?? ''"):]
    open(f, 'w').write(s)
    done.append(b)
print(len(done), done)
