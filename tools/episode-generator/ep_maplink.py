import sys,re,glob,unicodedata
def slug(s): return re.sub(r'[^a-z0-9]+','-',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()).strip('-')
for f in glob.glob(sys.argv[1]+'/Episode-*.dc.html'):
    s=open(f).read()
    i=s.find('See it on the map</a>')
    if i<0: continue
    seg=s[max(0,i-3000):i]
    txt=re.sub(r'<[^>]*>',' ',seg); txt=re.sub(r'\s+',' ',txt)
    m=re.search(r'(?:his|her) pick (.+?) The draw',txt)
    c=slug(m.group(1).strip())
    j=s.rfind('href="{{lp}}Atlas.dc.html"',0,i)
    assert j>i-400,f
    s=s[:j]+f'href="{{{{lp}}}}Atlas.dc.html#{c}"'+s[j+len('href="{{lp}}Atlas.dc.html"'):]
    open(f,'w').write(s); print(f.split('/')[-1],c)
