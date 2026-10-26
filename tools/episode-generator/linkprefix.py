import re,glob,os,sys
P='/tmp/claude-0/-home-claude/d6bc218f-fd68-5061-924c-755d80960da0/scratchpad/btrweb/project/'
pages=[os.path.basename(f) for f in glob.glob(P+'*.dc.html') if not re.match(r'(Tablet|Phone)-',os.path.basename(f)) and os.path.basename(f)!='Episode.dc.html']
for f in sorted(pages):
    s=open(P+f).read()
    if "lp: this.props.lp" in s: print('skip',f); continue
    n0=len(re.findall(r'href="[A-Za-z0-9-]+\.dc\.html',s))
    s=re.sub(r'href="([A-Za-z0-9-]+\.dc\.html)',r'href="{{lp}}\1',s)
    s=s.replace('href="{{e.href}}"','href="{{lp}}{{e.href}}"').replace('href="{{g.page}}"','href="{{lp}}{{g.page}}"')
    lines=s.split('\n')
    i=next(k for k,l in enumerate(lines) if 'renderVals()' in l)
    j=next(k for k in range(i+1,len(lines)) if re.match(r'^    return \{',lines[k]))
    if lines[j].strip()=='return {};':
        lines[j]="    return { lp: this.props.lp ?? '' };"
    else:
        lines[j]=lines[j].replace('return {',"return { lp: this.props.lp ?? '',",1)
    s='\n'.join(lines)
    open(P+f,'w').write(s)
    print(f,n0,lines[j].strip()[:70])
