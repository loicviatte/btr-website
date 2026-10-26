"""Atlas map: crisp at any zoom (the SVG viewBox is animated instead of scaling a bitmap layer),
and the pins + country name fade out while the map moves, then fade back in when it stops."""
import sys
R = [
 ("    const view = this.state.view || (this.state.autoFit ? fit(picked) : home());\n    const k = view.k, tx = view.tx, ty = view.ty;",
  """    const target = this.state.view || (this.state.autoFit ? fit(picked) : home());
    const isDrag = !!this.state.dragging;
    const sameV = (a, b) => !!a && !!b && Math.abs(a.k - b.k) < 1e-4 && Math.abs(a.tx - b.tx) < 1e-3 && Math.abs(a.ty - b.ty) < 1e-3;
    if (typeof window === 'undefined' || !window.requestAnimationFrame || isDrag || !this.shown) { this.shown = target; this.tw = null; }
    else if (!sameV(target, this.tw ? this.tw.to : this.shown)) {
      const from = { ...this.shown }, to = target, cw = VW, ch = VH;
      const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      const tw = this.tw = { to, t0: 0 };
      const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
      const fcx = (cw / 2 - from.tx) / from.k, fcy = (ch / 2 - from.ty) / from.k, tcx = (cw / 2 - to.tx) / to.k, tcy = (ch / 2 - to.ty) / to.k;
      const step = (now) => {
        if (this.tw !== tw) return;
        if (!tw.t0) tw.t0 = now;
        const p = reduce ? 1 : Math.min(1, (now - tw.t0) / 900), e = ease(p);
        const kk = Math.exp(Math.log(from.k) + (Math.log(to.k) - Math.log(from.k)) * e);
        const cx = fcx + (tcx - fcx) * e, cy = fcy + (tcy - fcy) * e;
        this.shown = p >= 1 ? to : { k: kk, tx: cw / 2 - cx * kk, ty: ch / 2 - cy * kk };
        if (p >= 1) this.tw = null; else window.requestAnimationFrame(step);
        this.forceUpdate();
      };
      window.requestAnimationFrame(step);
    }
    const view = this.shown;
    const moving = !!this.tw;
    const k = view.k, tx = view.tx, ty = view.ty;"""),
 ("    const mapLayer = 'position: absolute; left: 0; top: 0; height: 100%; width: ' + (W / VW * 100).toFixed(3) + '%; transform-origin: 0 0; transform: translate(' + (tx / W * 100).toFixed(3) + '%, ' + (ty / H * 100).toFixed(3) + '%) scale(' + k.toFixed(3) + '); transition: ' + (dragging ? 'none' : 'transform 900ms cubic-bezier(0.65, 0, 0.35, 1)') + ';';",
  "    const mapLayer = 'position: absolute; inset: 0;';\n    const vb = (-tx / k).toFixed(3) + ' ' + (-ty / k).toFixed(3) + ' ' + (VW / k).toFixed(3) + ' ' + (VH / k).toFixed(3);\n    const pinFade = 'opacity: ' + (moving ? 0 : 1) + '; transition: opacity ' + (moving ? '120ms' : '420ms 60ms') + ' ease;' + (moving ? ' pointer-events: none;' : '');"),
 ("      const x = c.x / W * 100, y = c.y / H * 100;",
  "      const x = (c.x * k + tx) / VW * 100, y = (c.y * k + ty) / VH * 100;"),
 ("'; transform: scale(' + inv + '); transition: ' + (dragging ? 'none' : 'transform 900ms cubic-bezier(0.65, 0, 0.35, 1)') + ';';",
  "'; ' + pinFade;"),
 ("z-index: 4; transform-origin: 0 0; transform: scale(' + inv + ') ' + (narrow ? 'translate(-50%, 24px)' : (right ? 'translate(calc(-100% - 22px), -50%)' : 'translate(22px, -50%)')) + '; transition: transform 900ms cubic-bezier(0.65, 0, 0.35, 1);",
  "z-index: 4; transform: ' + (narrow ? 'translate(-50%, 24px)' : (right ? 'translate(calc(-100% - 22px), -50%)' : 'translate(22px, -50%)')) + '; ' + pinFade + '"),
 ('<svg aria-hidden="true" viewBox="0 0 1000 444" preserveAspectRatio="none" style="position: absolute; inset: 0; width: 100%; height: 100%;">',
  '<svg aria-hidden="true" viewBox="{{vb}}" preserveAspectRatio="none" style="position: absolute; inset: 0; width: 100%; height: 100%;">'),
 ("      mapLayer, shapes, zoomed,", "      mapLayer, vb, shapes, zoomed,"),
]
for f in sys.argv[1:]:
    s = open(f).read()
    if 'pinFade' in s: print('skip', f); continue
    for a, b in R:
        assert s.count(a) == 1, (f, a[:70], s.count(a))
        s = s.replace(a, b)
    open(f, 'w').write(s); print('ok', f)
