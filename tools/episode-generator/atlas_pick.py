import sys,re,unicodedata
def slug(s): return re.sub(r'[^a-z0-9]+','-',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()).strip('-')
f=sys.argv[1]; s=open(f).read()
def rep(a,b):
    global s
    assert s.count(a)==1,(f,a[:70],s.count(a)); s=s.replace(a,b)
if 'autoFit' not in s:
    rep("""  componentDidMount() {
    if (!this.mq) return;""","""  componentDidMount() {
    const n = 11;
    let i = -1;
    try {
      const h = decodeURIComponent((window.location.hash || '').slice(1)).toLowerCase();
      const slugs = ['pakistan', 'papua-new-guinea', 'mexico', 'namibia', 'chad', 'laos', 'rwanda', 'malawi', 'japan', 'morocco', 'sao-tome-and-principe'];
      i = slugs.indexOf(h);
    } catch (e) {}
    if (i < 0) i = Math.floor(Math.random() * n);
    this.setState({ picked: i, slide: 0, view: null, autoFit: false });
    this.fitTimer = setTimeout(() => { if (!this.state.view) this.setState({ autoFit: true }); }, 650);
    if (!this.mq) return;""")
    rep("const view = this.state.view || home();","const view = this.state.view || (this.state.autoFit ? fit(picked) : home());")
    rep("unzoom: () => this.setState({ view: null }),","unzoom: () => this.setState({ view: null, autoFit: false }),")
open(f,'w').write(s); print('atlas ok',f)
