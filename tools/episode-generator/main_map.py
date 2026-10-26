import sys,re,json
atlas=open(sys.argv[1]).read()
MAP=json.loads(re.search(r'const MAP = (\[.*?\]);\n',atlas).group(1))
def simp(d):
    out=[];prev=None
    for cmd,x,y in re.findall(r'([MLZ]?)(-?[\d.]+),(-?[\d.]+)',d.replace('Z','Z ')):
        pt=(round(float(x)),round(float(y)))
        if cmd=='M': out.append('M%d,%d'%pt); prev=pt; continue
        if pt!=prev: out.append('L%d,%d'%pt); prev=pt
    return ''.join(out).replace('M','ZM')[1:]+'Z'
paths=''.join('<path d="%s"></path>'%simp(m['d']) for m in MAP)
for f in sys.argv[2:]:
    s=open(f).read()
    if 'class="m-atlas-shapes"' in s: print('skip',f); continue
    img='<img src="/_blob/31a333fde001c22d71340b7ca1561eca" alt="" style="position: absolute; inset: 0; width: 100%; height: 100%; max-width: none;">'
    assert s.count(img)==1,f
    svg='<svg class="m-atlas-shapes" aria-hidden="true" viewBox="0 0 1000 444" preserveAspectRatio="none" style="position: absolute; inset: 0; width: 100%; height: 100%;" fill="#b8862f">'+paths+'</svg>'
    s=s.replace(img,img+'\n          '+svg)
    s=s.replace('background: #080403; border: 2px solid #fecb7a;"></span>','background: #d29a3a; border: 2px solid #fecb7a;"></span>')
    open(f,'w').write(s); print('ok',f,len(paths))
