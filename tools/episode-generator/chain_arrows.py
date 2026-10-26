"""Chain: arrows on the guest strip edges (shown only when there is more to scroll that way)."""
import sys
LEFT_OLD = '<div aria-hidden="true" style="position: absolute; left: 0; top: 0; bottom: 0; width: 56px; background: linear-gradient(90deg, #080403 20%, rgba(8,4,3,0) 100%); pointer-events: none;"></div>'
RIGHT_OLD = '<div aria-hidden="true" style="position: absolute; right: 0; top: 0; bottom: 0; width: 56px; background: linear-gradient(270deg, #080403 20%, rgba(8,4,3,0) 100%); pointer-events: none;"></div>'
BTN = ('display: grid; place-items: center; width: 36px; height: 36px; padding: 0; background: #080403; border: 1px solid rgba(254,203,122,0.7); border-radius: 0; color: #fecb7a; cursor: pointer; pointer-events: auto; animation: chArr .25s ease both;')
def side(d):
    grad = '90deg' if d == 'left' else '270deg'
    path = 'M15 5l-7 7 7 7' if d == 'left' else 'M9 5l7 7-7 7'
    key = 'canL' if d == 'left' else 'canR'
    act = 'scrollL' if d == 'left' else 'scrollR'
    lab = 'Scroll back through the guests' if d == 'left' else 'Scroll forward through the guests'
    return (f'<div aria-hidden="true" style="position: absolute; {d}: 0; top: 0; bottom: 0; width: 64px; background: linear-gradient({grad}, #080403 35%, rgba(8,4,3,0) 100%); pointer-events: none;"></div>\n'
            f'      <sc-if value="{{{{{key}}}}}" hint-placeholder-val="{{{{true}}}}">\n'
            f'        <div style="position: absolute; {d}: 6px; top: 32px; pointer-events: none;"><button type="button" tabindex="-1" onClick="{{{{{act}}}}}" aria-label="{lab}" style="{BTN}"><svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="square"><path d="{path}"></path></svg></button></div>\n'
            f'      </sc-if>')
for f in sys.argv[1:]:
    s = open(f).read()
    if 'chArr' in s: print('skip', f); continue
    assert LEFT_OLD in s and RIGHT_OLD in s, f
    s = s.replace(LEFT_OLD, side('left')).replace(RIGHT_OLD, side('right'))
    s = s.replace('class="chain-strip" style=', 'class="chain-strip" onScroll="{{onStrip}}" style=', 1)
    s = s.replace('</style>\n</helmet>', '@keyframes chArr{from{opacity:0}to{opacity:1}}\n</style>\n</helmet>', 1)
    s = s.replace("this.state = { picked: 10, q: '' };", "this.state = { picked: 10, q: '', canL: false, canR: false };", 1)
    old = "  componentDidMount() { this.centerStrip(false); }"
    assert old in s
    s = s.replace(old, """  componentDidMount() {
    this.centerStrip(false);
    this.edges();
    this._onResize = () => this.edges();
    try { window.addEventListener('resize', this._onResize); } catch (e) {}
    setTimeout(() => this.edges(), 400);
  }
  componentWillUnmount() { try { window.removeEventListener('resize', this._onResize); } catch (e) {} }
  edges() {
    const s = this.strip; if (!s) return;
    const canL = s.scrollLeft > 8, canR = s.scrollLeft + s.clientWidth < s.scrollWidth - 8;
    if (canL !== this.state.canL || canR !== this.state.canR) this.setState({ canL, canR });
  }
  nudge(dir) {
    const s = this.strip; if (!s) return;
    const dx = dir * Math.max(160, s.clientWidth * 0.7);
    try { s.scrollBy({ left: dx, behavior: 'smooth' }); } catch (e) { s.scrollLeft += dx; }
  }""", 1)
    old = "      stripRef: (el) => { this.strip = el; },"
    assert old in s
    s = s.replace(old, old + """
      onStrip: () => this.edges(),
      canL: this.state.canL,
      canR: this.state.canR,
      scrollL: () => this.nudge(-1),
      scrollR: () => this.nudge(1),""", 1)
    open(f, 'w').write(s); print('ok', f)
