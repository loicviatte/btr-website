import sys,re
for f in sys.argv[1:]:
    s=open(f).read()
    a='PLAY FROM {{r.time}}'
    assert s.count(a)==1,f; s=s.replace(a,'PLAY MOMENT · {{r.time}}')
    s,n=re.subn(r'\s*<a href="\{\{g\.page\}\}"[^>]*>\{\{g\.moreText\}\}</a>','',s)
    assert n==1,f
    open(f,'w').write(s); print('ok',f)
