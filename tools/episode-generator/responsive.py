import re, glob, os
P = '/tmp/claude-0/-home-claude/d6bc218f-fd68-5061-924c-755d80960da0/scratchpad/btrweb/project/'
MONO = "font-family: 'PP Monument Extended', 'Arial Black', sans-serif;"
CSS = """.btr-burger{display:none}
summary.btr-burger-btn{list-style:none}summary.btr-burger-btn::-webkit-details-marker{display:none}
details[open] .btr-burger-open{display:none}details:not([open]) .btr-burger-close{display:none}
@media (max-width: 900px){.btr-links,.btr-sub{display:none !important}.btr-burger{display:block !important}.btr-chain-row{flex-wrap:nowrap !important;overflow-x:auto;padding-bottom:20px !important}}
"""
done = []
for f in sorted(glob.glob(P + '*.dc.html')):
    s = open(f).read()
    if 'btr-burger' in s:
        continue
    # links div
    m = re.search(r'(\n      <div )(style="display: flex; flex-wrap: wrap; align-items: center; gap: 0 26px;[^"]*">)(.*?)(\n      </div>)', s, re.S)
    if not m:
        print('no links', f); continue
    links_inner = m.group(3)
    s = s[:m.start()] + m.group(1) + 'class="btr-links" ' + m.group(2) + links_inner + m.group(4) + s[m.end():]
    # subscribe button
    sub_pat = '      <a href="https://www.youtube.com/@BreakTheRoutinePodcast" style="display: inline-flex; align-items: center; min-height: 44px;'
    assert sub_pat in s, f
    s = s.replace(sub_pat, sub_pat.replace('<a href=', '<a class="btr-sub" href=', 1), 1)
    # menu links: restyle each link
    menu_links = []
    for a in re.finditer(r'<a href="([^"]+)"([^>]*?)style="([^"]*)">([^<]+)</a>', links_inner):
        href, extra, st, label = a.groups()
        active = 'color: #fecb7a' in st
        menu_links.append(f'<a href="{href}"{extra}style="display: block; padding: 16px 0; border-bottom: 1px solid rgba(254,203,122,0.16); color: {"#fecb7a" if active else "#ffffff"}; text-decoration: none; {MONO} font-size: 15px; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase;">{label}</a>')
    burger = f'''
      <details class="btr-burger" style="position: static;">
        <summary class="btr-burger-btn" aria-label="Menu" style="display: grid; place-items: center; width: 48px; height: 48px; box-sizing: border-box; border: 1px solid rgba(254,203,122,0.55); color: #fecb7a; cursor: pointer;">
          <svg class="btr-burger-open" aria-hidden="true" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="square"><path d="M2 5h16M2 10h16M2 15h16"></path></svg>
          <svg class="btr-burger-close" aria-hidden="true" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="square"><path d="M4 4l12 12M16 4L4 16"></path></svg>
        </summary>
        <div style="position: absolute; left: 0; right: 0; top: 100%; box-sizing: border-box; padding: 8px clamp(16px, 4vw, 56px) 24px; background: #080403; border-bottom: 1px solid rgba(254,203,122,0.3); display: flex; flex-direction: column;">
          {chr(10).join('          ' + x for x in menu_links).lstrip()}
          <a href="https://www.youtube.com/@BreakTheRoutinePodcast" style="display: inline-flex; align-self: flex-start; align-items: center; min-height: 48px; margin-top: 20px; padding: 0 20px; background: #fecb7a; color: #000000; text-decoration: none; {MONO} font-size: 12px; font-weight: 800; letter-spacing: 0.04em; text-transform: uppercase;">Subscribe on YouTube</a>
        </div>
      </details>'''
    s = s.replace('\n    </nav>\n  </header>', burger + '\n    </nav>\n  </header>', 1)
    # helmet css
    s = s.replace('</style>\n</helmet>', CSS + '</style>\n</helmet>', 1)
    if os.path.basename(f) == 'Chain.dc.html':
        s = s.replace('<ol aria-label="Guests in order" style=', '<ol class="btr-chain-row" aria-label="Guests in order" style=', 1)
    open(f, 'w').write(s)
    done.append(os.path.basename(f))
print(len(done), done)
