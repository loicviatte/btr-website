"""Atlas map: pinch to zoom on phone/tablet (two fingers), pan with one finger; drags start from the view on screen."""
import sys
START = "    const onDown = (e) => {"
END = "    const onUp = () => { const d = this.drag; this.drag = null; if (d && d.moved) { this.justDragged = true; setTimeout(() => { this.justDragged = false; }, 60); } if (this.state.dragging) this.setState({ dragging: false }); };"
NEW = r"""    const curV = () => this.shown || this.state.view || home();
    const pts = this.ptrs || (this.ptrs = new Map());
    const startPinch = (el) => {
      const [a, b] = Array.from(pts.values());
      const r = el.getBoundingClientRect();
      this.drag = null;
      this.pinch = { d0: Math.hypot(a.x - b.x, a.y - b.y) || 1, cx: (a.x + b.x) / 2 - r.left, cy: (a.y + b.y) / 2 - r.top, v: curV(), u: VW / r.width, r };
    };
    const onDown = (e) => {
      if (e.button !== undefined && e.button !== 0) return;
      pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
      if (pts.size === 2) {
        pts.forEach((_, id) => { try { e.currentTarget.setPointerCapture(id); } catch (err) {} });
        startPinch(e.currentTarget);
        return;
      }
      if (pts.size > 2) return;
      this.drag = { x: e.clientX, y: e.clientY, v: curV(), w: e.currentTarget.getBoundingClientRect().width, moved: false, id: e.pointerId, el: e.currentTarget };
    };
    const onMove = (e) => {
      if (pts.has(e.pointerId)) pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
      const p = this.pinch;
      if (p && pts.size >= 2) {
        const [a, b] = Array.from(pts.values());
        const nk = Math.max(1, Math.min(40, p.v.k * (Math.hypot(a.x - b.x, a.y - b.y) / p.d0)));
        const mx = (p.cx * p.u - p.v.tx) / p.v.k, my = (p.cy * p.u - p.v.ty) / p.v.k;
        const ncx = ((a.x + b.x) / 2 - p.r.left) * p.u, ncy = ((a.y + b.y) / 2 - p.r.top) * p.u;
        p.moved = true;
        this.setState({ dragging: true, view: clampV({ k: nk, tx: ncx - mx * nk, ty: ncy - my * nk }) });
        return;
      }
      const d = this.drag; if (!d || d.id !== e.pointerId) return;
      const dx = e.clientX - d.x, dy = e.clientY - d.y;
      if (!d.moved && Math.abs(dx) + Math.abs(dy) < 5) return;
      if (!d.moved) { d.moved = true; try { d.el.setPointerCapture(d.id); } catch (err) {} }
      const u = VW / d.w;
      this.setState({ dragging: true, view: clampV({ k: d.v.k, tx: d.v.tx + dx * u, ty: d.v.ty + dy * u }) });
    };
    const onUp = (e) => {
      if (e && e.pointerId !== undefined) pts.delete(e.pointerId); else pts.clear();
      const p = this.pinch, d = this.drag;
      if (p) {
        this.pinch = null;
        this.justDragged = true; setTimeout(() => { this.justDragged = false; }, 120);
        if (pts.size === 1 && e && e.currentTarget) {
          const [id, q] = Array.from(pts.entries())[0];
          this.drag = { x: q.x, y: q.y, v: curV(), w: e.currentTarget.getBoundingClientRect().width, moved: true, id, el: e.currentTarget };
          return;
        }
      }
      if (pts.size === 0) {
        this.drag = null;
        if (d && d.moved) { this.justDragged = true; setTimeout(() => { this.justDragged = false; }, 60); }
        if (this.state.dragging) this.setState({ dragging: false });
      }
    };"""
for f in sys.argv[1:]:
    s = open(f).read()
    if 'startPinch' in s: print('skip', f); continue
    i = s.index(START); j = s.index(END) + len(END)
    s = s[:i] + NEW + s[j:]
    s = s.replace("'; touch-action: ' + (zoomed ? 'none' : 'pan-y') + ';", "'; touch-action: ' + (zoomed ? 'none' : 'pan-y pinch-zoom') + ';", 1) if False else s
    open(f, 'w').write(s); print('ok', f)
# let two-finger gestures reach the map instead of zooming the whole page (iOS Safari included)
for f in sys.argv[1:]:
    s = open(f).read()
    if '_tsBlock' in s: continue
    a = "  componentDidMount() {\n"
    assert s.count(a) == 1, f
    s = s.replace(a, a + """    try {
      const m = document.querySelector('.atl-map');
      if (m) {
        this._mapEl = m;
        this._tsBlock = (ev) => { if (ev.touches && ev.touches.length > 1) ev.preventDefault(); };
        this._gBlock = (ev) => ev.preventDefault();
        m.addEventListener('touchstart', this._tsBlock, { passive: false });
        m.addEventListener('touchmove', this._tsBlock, { passive: false });
        m.addEventListener('gesturestart', this._gBlock);
        m.addEventListener('gesturechange', this._gBlock);
      }
    } catch (e) {}
""", 1)
    b = "  componentWillUnmount() {\n"
    assert s.count(b) == 1, f
    s = s.replace(b, b + """    try {
      const m = this._mapEl;
      if (m) { m.removeEventListener('touchstart', this._tsBlock); m.removeEventListener('touchmove', this._tsBlock); m.removeEventListener('gesturestart', this._gBlock); m.removeEventListener('gesturechange', this._gBlock); }
    } catch (e) {}
""", 1)
    open(f, 'w').write(s); print('touch block', f)
