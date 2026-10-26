"""Episode pages: "Read the full transcript" opens a full-screen popup (Esc, backdrop or × to close).
Tapping a time closes it and plays that moment in the episode player. Usage: python3 ep_tmodal.py <files...>"""
import sys
MONO = "font-family: 'PP Monument Extended', 'Arial Black', sans-serif;"
ROW = '''<div class="ep-trow" style="display: grid; grid-template-columns: 92px 1fr; gap: 16px;">
                    <a href="{{p.url}}" aria-label="{{p.aria}}" style="align-self: start; padding: 2px 0; font-size: 14px; font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap;">{{p.time}}</a>
                    <p style="margin: 0; color: #e8ddd1;">{{p.before}}</p>
                  </div>'''
MODAL = f'''
          <sc-if value="{{{{tModal}}}}" hint-placeholder-val="{{{{false}}}}">
            <div role="dialog" aria-modal="true" aria-labelledby="tmodal-title" onClick="{{{{tBackdrop}}}}" style="position: fixed; inset: 0; z-index: 200; display: flex; align-items: center; justify-content: center; box-sizing: border-box; padding: max(16px, env(safe-area-inset-top, 0px)) 16px max(16px, env(safe-area-inset-bottom, 0px)); background: rgba(8,4,3,0.84); backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px); animation: btrTIn .3s cubic-bezier(.16,1,.3,1) both;">
              <div style="width: 100%; max-width: 880px; max-height: 100%; display: flex; flex-direction: column; background: #0e0705; border: 1px solid rgba(254,203,122,0.3); box-shadow: 0 30px 80px rgba(0,0,0,0.6);">
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 16px 16px 16px 24px; border-bottom: 1px solid rgba(254,203,122,0.16);">
                  <div style="display: flex; flex-direction: column; gap: 4px; min-width: 0;">
                    <p id="tmodal-title" style="margin: 0; {MONO} font-size: 12px; font-weight: 800; letter-spacing: 0.12em; color: #fecb7a;">FULL TRANSCRIPT</p>
                    <p style="margin: 0; font-size: 14px; color: #c9b8a6;">{{{{tModalSub}}}}</p>
                  </div>
                  <button type="button" onClick="{{{{tClose}}}}" aria-label="Close the transcript" style="flex: none; display: flex; align-items: center; justify-content: center; width: 46px; height: 46px; padding: 0; background: transparent; border: 1px solid rgba(254,203,122,0.55); border-radius: 0; color: #ffffff; cursor: pointer;"><svg aria-hidden="true" width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="square"><path d="M4 4l12 12M16 4L4 16"></path></svg></button>
                </div>
                <div onClick="{{{{tPick}}}}" style="overflow-y: auto; overscroll-behavior: contain; padding: 24px; display: flex; flex-direction: column; gap: 18px;">
                  <sc-for list="{{{{tAllRows}}}}" as="p" hint-placeholder-count="6">
                  {ROW}
                  </sc-for>
                </div>
              </div>
            </div>
          </sc-if>
'''
for f in sys.argv[1:]:
    s = open(f).read()
    if 'tmodal-title' in s: print('skip', f); continue
    # popup markup, at the end of the transcript section
    a = 'Tap a time to play that moment on YouTube.</p>\n        </section>'
    assert a in s, f
    s = s.replace(a, 'Tap a time to play that moment.</p>' + MODAL + '        </section>', 1)
    s = s.replace('</style>\n</helmet>', '@keyframes btrTIn{from{opacity:0}to{opacity:1}}\n</style>\n</helmet>', 1)
    # state + helpers
    s = s.replace("this.state = { on: -1, tq: '', tAll: false, chAll: false };", "this.state = { on: -1, tq: '', tAll: false, chAll: false, tModal: false };", 1)
    helpers = '''  openT() {
    this.setState({ tModal: true });
    try { this._tOverflow = document.documentElement.style.overflow; document.documentElement.style.overflow = 'hidden'; } catch (e) {}
    this._tKey = (e) => { if (e.key === 'Escape') this.closeT(); };
    document.addEventListener('keydown', this._tKey);
  }
  closeT() {
    this.setState({ tModal: false });
    try { document.documentElement.style.overflow = this._tOverflow || ''; } catch (e) {}
    if (this._tKey) document.removeEventListener('keydown', this._tKey);
  }
  componentWillUnmount() { if (this.state.tModal) this.closeT(); }
  renderVals() {'''
    assert s.count('  renderVals() {') == 1, f
    s = s.replace('  renderVals() {', helpers, 1)
    old_else = """      tRows = (this.state.tAll ? T : T.slice(0, 8)).map((r) => mk(r, -1));
      tSummary = 'The full conversation, ' + T.length + ' passages';
      tCanToggle = true;
      tToggleLabel = this.state.tAll ? 'SHOW LESS' : 'READ THE FULL TRANSCRIPT';"""
    assert old_else in s, f
    s = s.replace(old_else, """      tRows = T.slice(0, 8).map((r) => mk(r, -1));
      tSummary = 'The full conversation, ' + T.length + ' passages';
      tCanToggle = T.length > 8;
      tToggleLabel = 'READ THE FULL TRANSCRIPT';""", 1)
    old_ret = """      tExpanded: this.state.tAll ? 'true' : 'false',
      tToggle: () => this.setState({ tAll: !this.state.tAll }),"""
    assert old_ret in s, f
    s = s.replace(old_ret, """      tExpanded: this.state.tModal ? 'true' : 'false',
      tToggle: () => this.openT(),
      tModal: this.state.tModal,
      tModalSub: T.length + ' passages · tap a time to play that moment',
      tAllRows: this.state.tModal ? T.map((r) => mk(r, -1)) : [],
      tClose: () => this.closeT(),
      tBackdrop: (e) => { if (e.target === e.currentTarget) this.closeT(); },
      tPick: (e) => { if (e.target && e.target.closest && e.target.closest('a[href]')) this.closeT(); },""", 1)
    s = s.replace('aria-expanded="{{tExpanded}}"', 'aria-haspopup="dialog" aria-expanded="{{tExpanded}}"', 1)
    open(f, 'w').write(s); print('ok', f.split('/')[-1])
