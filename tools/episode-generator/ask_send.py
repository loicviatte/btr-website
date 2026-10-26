"""Ask page: real submit. On the site (window.__btrAskApi set by the layout) the question is POSTed to /api/ask;
on the canvas it just shows the confirmation. Adds a sending state, an error line and a hidden honeypot field."""
import sys
for f in sys.argv[1:]:
    s = open(f).read()
    if '__btrAskApi' in s: print('skip', f); continue
    # button label + disabled while sending
    a = '>SEND MY QUESTION</button>'
    assert a in s
    s = s.replace('<button type="submit" style="', '<button type="submit" disabled="{{sending}}" style="', 1)
    s = s.replace(a, '>{{btnText}}</button>', 1)
    # honeypot + error line before the button
    hp = ('<input type="text" name="website" tabindex="-1" autocomplete="off" aria-hidden="true" value="{{hp}}" onChange="{{onHp}}" style="position: absolute; left: -9999px; width: 1px; height: 1px; opacity: 0;">\n'
          '          <sc-if value="{{hasError}}" hint-placeholder-val="{{false}}">\n'
          '            <p role="alert" style="margin: 0; padding: 12px 14px; border: 1px solid #fecb7a; color: #fecb7a; font-size: 15px;">{{error}}</p>\n'
          '          </sc-if>\n          ')
    i = s.index('<button type="submit"')
    s = s[:i] + hp + s[i:]
    s = s.replace("this.state = { name: '', ig: '', q: '', ok: true, sent: false };",
                  "this.state = { name: '', ig: '', q: '', ok: true, sent: false, sending: false, error: '', hp: '' };", 1)
    old = "      send: (e) => { if (e && e.preventDefault) e.preventDefault(); if (!s.name.trim() || !s.q.trim()) return; this.setState({ sent: true }); },"
    assert old in s
    new = """      sending: s.sending,
      btnText: s.sending ? 'SENDING…' : 'SEND MY QUESTION',
      hasError: !!s.error,
      error: s.error,
      hp: s.hp,
      onHp: (e) => this.setState({ hp: e.target.value }),
      send: (e) => {
        if (e && e.preventDefault) e.preventDefault();
        if (s.sending || !s.name.trim() || !s.q.trim()) return;
        const api = typeof window !== 'undefined' && window.__btrAskApi;
        if (!api) { this.setState({ sent: true }); return; }
        this.setState({ sending: true, error: '' });
        fetch(api, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ name: s.name, ig: s.ig, q: s.q, ok: s.ok, website: s.hp }) })
          .then((r) => r.json().catch(() => ({})).then((j) => ({ ok: r.ok, j })))
          .then(({ ok, j }) => {
            if (ok) this.setState({ sending: false, sent: true });
            else this.setState({ sending: false, error: (j && j.error) || 'Your question could not be sent. Please try again, or send it to us on Instagram @breaktheroutinepodcast.' });
          })
          .catch(() => this.setState({ sending: false, error: 'No connection. Please try again in a moment.' }));
      },"""
    s = s.replace(old, new, 1)
    s = s.replace("again: () => this.setState({ q: '', sent: false })", "again: () => this.setState({ q: '', sent: false, error: '' })", 1)
    open(f, 'w').write(s); print('ok', f)
