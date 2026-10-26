import json, re
d = json.load(open('/mnt/user-data/uploads/BTR-SHORTS/SRT/_all.json'))
out = {}
for v, x in d.items():
    cues = []
    for blk in x['srt'].split('\n\n'):
        L = blk.strip().split('\n')
        if len(L) < 3: continue
        h, m, s = L[1][:8].split(':')
        cues.append((int(h) * 3600 + int(m) * 60 + int(s), ' '.join(L[2:]).strip()))
    paras, cur, start = [], [], 0
    for t, txt in cues:
        new_turn = txt.startswith('>>')
        txt = txt.lstrip('>').strip()
        if not txt: continue
        size = sum(len(c) for c in cur)
        if cur and (new_turn or (t - start > 45 and re.search(r'[.?!]$', cur[-1])) or size > 700):
            paras.append([start, ' '.join(cur)]); cur = []
        if not cur: start = t
        cur.append(txt)
    if cur: paras.append([start, ' '.join(cur)])
    out[v] = paras
    print(x['name'], len(cues), '->', len(paras), sum(len(p[1]) for p in paras))
json.dump(out, open('trans.json', 'w'), ensure_ascii=False)
