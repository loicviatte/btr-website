"""Episode pages: add the guest's signed polaroid (Hall of Fame) at the bottom of the sidebar, when one exists.
Usage: python3 ep_polaroid.py <design dir>   (polaroid ids are read from Episodes.dc.html)"""
import re, sys, glob, os
D = sys.argv[1]
eps = open(os.path.join(D, 'Episodes.dc.html')).read()
pol = {m.group(1): (m.group(2), m.group(3)) for m in re.finditer(r'<a href="\{\{lp\}\}Episode-([a-z-]+)\.dc\.html" aria-label="[^"]*signed polaroid[^"]*"[^>]*>\s*<img src="(/_blob/[0-9a-f]+)" alt="([^"]*)"', eps)}
MONO = "font-family: 'PP Monument Extended', 'Arial Black', sans-serif;"
done = []
for f in sorted(glob.glob(os.path.join(D, 'Episode-*.dc.html'))):
    slug = os.path.basename(f)[len('Episode-'):-len('.dc.html')]
    if slug not in pol: continue
    s = open(f).read()
    if 'data-polaroid' in s: continue
    src, alt = pol[slug]
    block = f'''        <div data-polaroid="" style="padding: 24px; display: flex; flex-direction: column; align-items: center; gap: 18px; border: 1px solid rgba(254,203,122,0.2); background: repeating-linear-gradient(90deg, #0c0604 0px, #0c0604 30px, #120a06 30px, #120a06 38px);">
          <p style="align-self: flex-start; margin: 0; {MONO} font-size: 11px; font-weight: 800; letter-spacing: 0.12em; color: #fecb7a;">HALL OF FAME</p>
          <img src="{src}" alt="{alt}" style="display: block; width: 100%; max-width: 240px; height: auto; transform: rotate(-2deg); box-shadow: 0 14px 30px rgba(0,0,0,0.55), 0 2px 6px rgba(0,0,0,0.4);">
          <a href="{{{{lp}}}}Episodes.dc.html#hof" style="align-self: flex-start; padding: 4px 0; font-size: 14px;">Every signed polaroid</a>
        </div>

      </aside>'''
    i = s.rindex('      </aside>')
    s = s[:i].rstrip() + '\n\n' + block + s[i + len('      </aside>'):]
    open(f, 'w').write(s); done.append(slug)
print(len(done), done)
