#!/usr/bin/env python3
"""One-time: get the YouTube refresh token the GitHub Action uses to read the channel's captions.

On your Mac:
  python3 tools/auto/get_token.py ~/Downloads/client_secret_XXXX.json
A browser opens, you sign in with the Google account that owns the Break The Routine channel and accept.
The script then prints three values to paste into GitHub (repo → Settings → Secrets and variables → Actions):
YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN. Nothing is saved anywhere else.
"""
import http.server, json, sys, threading, urllib.parse, urllib.request, webbrowser

if len(sys.argv) < 2:
    sys.exit(__doc__)
cfg = json.load(open(sys.argv[1]))
cfg = cfg.get('installed') or cfg.get('web')
PORT = 8765
REDIRECT = f'http://127.0.0.1:{PORT}/'
code_box = {}

class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        code_box['code'] = (q.get('code') or [''])[0]
        self.send_response(200); self.send_header('content-type', 'text/html; charset=utf-8'); self.end_headers()
        self.wfile.write('<h2>C’est bon, tu peux fermer cet onglet et revenir au Terminal.</h2>'.encode())
    def log_message(self, *a): pass

srv = http.server.HTTPServer(('127.0.0.1', PORT), H)
threading.Thread(target=srv.handle_request, daemon=True).start()
url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode({
    'client_id': cfg['client_id'], 'redirect_uri': REDIRECT, 'response_type': 'code', 'access_type': 'offline', 'prompt': 'consent',
    'scope': 'https://www.googleapis.com/auth/youtube.force-ssl'})
print('Opening the browser… if nothing opens, paste this link:\n' + url)
webbrowser.open(url)
while 'code' not in code_box:
    threading.Event().wait(0.3)
body = urllib.parse.urlencode({'code': code_box['code'], 'client_id': cfg['client_id'], 'client_secret': cfg['client_secret'],
                               'redirect_uri': REDIRECT, 'grant_type': 'authorization_code'}).encode()
try:
    tok = json.loads(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', data=body)).read())
except Exception:   # Python without certificates on macOS: let curl (system certificates) do the call
    import subprocess
    tok = json.loads(subprocess.run(['curl', '-s', '-d', body.decode(), 'https://oauth2.googleapis.com/token'], capture_output=True, text=True).stdout)
if 'refresh_token' not in tok:
    sys.exit('No refresh token returned: ' + json.dumps(tok))
print('\nPaste these three secrets into GitHub (repo → Settings → Secrets and variables → Actions → New repository secret):\n')
print('YT_CLIENT_ID      =', cfg['client_id'])
print('YT_CLIENT_SECRET  =', cfg['client_secret'])
print('YT_REFRESH_TOKEN  =', tok['refresh_token'])
