import glob,re
def rep(s,a,b,n=1,f=''):
    assert s.count(a)==n,(f,a[:70],s.count(a)); return s.replace(a,b)
def addcss(s,css,f):
    return rep(s,"@media (max-width: 900px){.btr-links",css+"\n@media (max-width: 900px){.btr-links",1,f)
# Episode pages
for f in sorted(glob.glob('Episode-*.dc.html')):
    s=open(f).read()
    if 'ep-guest-img' in s: continue
    s=rep(s,'<div style="position: relative; aspect-ratio: 4 / 3; max-width: 100%; overflow: hidden;">','<div class="ep-guest-img" style="position: relative; aspect-ratio: 4 / 3; max-width: 100%; overflow: hidden;">',1,f)
    s=rep(s,'<div style="display: grid; grid-template-columns: 92px 1fr; gap: 16px;">','<div class="ep-trow" style="display: grid; grid-template-columns: 92px 1fr; gap: 16px;">',1,f)
    s=rep(s,'<div style="display: flex; flex-direction: column; gap: 18px; padding: 28px; background: #0e0705;','<div class="ep-tbox" style="display: flex; flex-direction: column; gap: 18px; padding: 28px; background: #0e0705;',1,f)
    s=rep(s,'font-size: 13px; font-weight: 800; line-height: 1.25;">{{r.hook}}','font-size: 13px; font-weight: 800; line-height: 1.25;" class="ep-hook">{{r.hook}}',1,f)
    s=re.sub(r'(<a href="https://www\.youtube\.com/watch\?v=[^"]+" )(style="position: absolute; left: 3\.2%; bottom: 5\.5%;)',r'\1class="ep-hero-btn" \2',s,count=1)
    assert 'ep-hero-btn' in s,f
    s=addcss(s,"@media (max-width: 900px){.ep-guest-img{aspect-ratio:16/9 !important}.ep-guest-img img{object-position:center !important}}\n@media (max-width: 600px){.ep-trow{grid-template-columns:52px 1fr !important;gap:12px !important}.ep-tbox{padding:18px 16px !important}.ep-hook{font-size:11px !important}.ep-hero-btn{display:none !important}}",f)
    open(f,'w').write(s)
# Main
f='Main.dc.html'; s=open(f).read()
s=rep(s,'<a href="https://www.youtube.com/watch?v=pi1IhRO8v4w" style="position: absolute; left: 3.2%;','<a class="m-hero-btn" href="https://www.youtube.com/watch?v=pi1IhRO8v4w" style="position: absolute; left: 3.2%;',1,f)
s=addcss(s,"@media (max-width: 600px){.m-hero-btn{display:none !important}}",f)
open(f,'w').write(s)
# About
f='About.dc.html'; s=open(f).read()
s=rep(s,'<img src="/_blob/498ce30b455f065345e90254b58348bb" alt="Marius Iepure laughing on the Break The Routine set" style="position: absolute;','<img class="ab-hero-img" src="/_blob/498ce30b455f065345e90254b58348bb" alt="Marius Iepure laughing on the Break The Routine set" style="position: absolute;',1,f)
s=rep(s,'<div style="position: relative; max-width: 1440px; margin: 0 auto; box-sizing: border-box; padding: 96px clamp(16px, 4vw, 56px) 104px;','<div class="ab-hero-in" style="position: relative; max-width: 1440px; margin: 0 auto; box-sizing: border-box; padding: 96px clamp(16px, 4vw, 56px) 104px;',1,f)
s=s.replace('font-size: 16px; font-weight: 800; color: #fecb7a; user-select: all;">breaktheroutine','font-size: 16px; font-weight: 800; color: #fecb7a; user-select: all;" class="btr-email">breaktheroutine')
s=s.replace('font-size: 16px; font-weight: 800; user-select: all;">breaktheroutine','font-size: 16px; font-weight: 800; user-select: all;" class="btr-email">breaktheroutine')
assert s.count('class="btr-email"')==2
s=addcss(s,".btr-email{overflow-wrap:anywhere;min-width:0}\n@media (max-width: 900px){.ab-hero-img{left:0 !important;width:100% !important;height:min(62vw,460px) !important;object-position:65% 25% !important;-webkit-mask-image:linear-gradient(180deg,#000 50%,rgba(0,0,0,0) 100%) !important;mask-image:linear-gradient(180deg,#000 50%,rgba(0,0,0,0) 100%) !important}.ab-hero-in{padding-top:calc(min(62vw,460px) - 40px) !important;padding-bottom:72px !important}}\n@media (max-width: 600px){.btr-email{font-size:13px !important}}",f)
open(f,'w').write(s)
print('done')
