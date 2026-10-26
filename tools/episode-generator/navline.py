import sys,glob
old='.btr-links a::after{content:"";position:absolute;left:0;right:0;bottom:8px;height:2px;background:#fecb7a;transform:scaleX(0);transform-origin:left;transition:transform .4s cubic-bezier(.16,1,.3,1)}'
new='.btr-links a::after{content:"";position:absolute;left:0;right:0;bottom:0;height:2px;background:#fecb7a;transform:scaleX(0);transform-origin:left;transition:transform .4s cubic-bezier(.16,1,.3,1)}\n.btr-links a[aria-current="page"]{border-bottom-color:transparent !important}\n.btr-links a[aria-current="page"]::after{transform:scaleX(1)}'
n=0
for f in sys.argv[1:]:
    s=open(f).read()
    if old in s:
        s=s.replace(old,new); open(f,'w').write(s); n+=1
print('patched',n)
