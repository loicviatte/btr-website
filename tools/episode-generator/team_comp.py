import sys
import numpy as np
from PIL import Image, ImageFilter as F, ImageEnhance, ImageChops
from rembg import remove, new_session
src_photo, out, scale, x0, y0 = sys.argv[1], sys.argv[2], float(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
model = sys.argv[6] if len(sys.argv) > 6 else 'u2net_human_seg'
src=Image.open('/home/claude/btr-website/public/assets/639bcb5def2655892c2ad9725cd79114.jpg').convert('RGB')
L=src.crop((0,0,600,1080)); R=src.crop((1380,0,1920,1080))
plate=Image.new('RGB',(1080,1080)); plate.paste(R,(540,0))
m=np.zeros((1080,600),dtype=np.uint8); m[:, :480]=255
for x in range(480,600): m[:,x]=int(255*(600-x)/120)
plate.paste(L,(0,0),Image.fromarray(m)); plate=plate.filter(F.GaussianBlur(9))
ph=Image.open(src_photo).convert('RGB')
cut=remove(ph,session=new_session(model)).convert('RGBA')
from scipy import ndimage
A=np.array(cut.split()[3]).astype(np.float32)
A[A<70]=0
lab,n=ndimage.label(A>128)
if n>1:
    sizes=ndimage.sum(np.ones_like(A),lab,range(1,n+1)); keep=1+int(np.argmax(sizes))
    region=ndimage.binary_dilation(lab==keep,iterations=6)
    A[~region]=0
HS=np.array(remove(ph,session=new_session('u2net_human_seg'),only_mask=True)).astype(np.float32)
hsb=ndimage.binary_erosion(HS>128,iterations=int(sys.argv[8]) if len(sys.argv)>8 else 10)
hsa=np.array(Image.fromarray((hsb*255).astype(np.uint8)).filter(F.GaussianBlur(3))).astype(np.float32)
ycut=int(sys.argv[7]) if len(sys.argv)>7 else 0
A[:ycut]=np.minimum(A[:ycut],hsa[:ycut])
cut.putalpha(Image.fromarray(A.astype(np.uint8)))
cut.save(out+'.cut.png')
W,H=cut.size; cw,ch=int(W*scale),int(H*scale)
c=cut.resize((cw,ch),Image.LANCZOS)
r,g,b,a=c.split(); rgb=Image.merge('RGB',(r,g,b))
rgb=ImageEnhance.Brightness(rgb).enhance(0.9)
rgb=Image.blend(rgb,ImageChops.multiply(rgb,Image.new('RGB',rgb.size,(255,188,105))),0.3)
rgb=ImageEnhance.Contrast(rgb).enhance(1.07)
a=a.filter(F.GaussianBlur(1.0)); c=Image.merge('RGBA',(*rgb.split(),a))
pos=(x0,y0); stroke=8
al=c.split()[3]; hard=al.point(lambda v:255 if v>110 else 0)
from scipy import ndimage
hn=np.array(hard)>0
filled=ndimage.binary_fill_holes(hn)
holes=Image.fromarray(((filled & ~hn)*255).astype(np.uint8)).filter(F.MaxFilter(3))
hard=Image.fromarray((filled*255).astype(np.uint8))
big=hard.filter(F.MaxFilter(2*stroke+1)).filter(F.GaussianBlur(0.8))
glow=hard.filter(F.MaxFilter(2*stroke+1)).filter(F.GaussianBlur(stroke*2.2)).point(lambda v:int(v*0.55))
gold=Image.new('RGBA',c.size,(254,203,122,0))
inv=holes.point(lambda v:255-v)
big=ImageChops.multiply(big,inv); glow=ImageChops.multiply(glow,inv)
g2=gold.copy(); g2.putalpha(glow); plate.paste(g2,pos,g2)
g1=gold.copy(); g1.putalpha(big); plate.paste(g1,pos,g1)
plate.paste(c,pos,c)
plate.resize((960,960),Image.LANCZOS).save(out,quality=88)
Image.open(out).resize((480,480)).save(out+'.s.png')
