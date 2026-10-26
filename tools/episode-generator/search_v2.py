"""Builds Search-v2.dc.html (proposal): moments ranked by relevance, guest filter, sort, show more."""
import json, sys
D = sys.argv[1]
src = open(D + '/Search.dc.html').read()
TH = json.load(open('/home/claude/gen/thumbs.json'))
MONO = "font-family: 'PP Monument Extended', 'Arial Black', sans-serif;"
LINE = 'rgba(254,203,122,0.16)'

results = f'''<section aria-labelledby="results" style="max-width: 1440px; margin: 0 auto; box-sizing: border-box; padding: 40px clamp(16px, 4vw, 56px) 96px; display: flex; flex-direction: column; gap: 20px;">
      <div style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px 24px;">
        <h2 id="results" aria-live="polite" style="margin: 0; font-size: 16px; font-weight: 600; color: #c9b8a6;">{{{{summary}}}}</h2>
        <div role="group" aria-label="Sort results" style="display: flex; border: 1px solid rgba(254,203,122,0.4);">
          <sc-for list="{{{{sorts}}}}" as="s" hint-placeholder-count="2">
            <button type="button" onClick="{{{{s.pick}}}}" aria-pressed="{{{{s.pressed}}}}" style="{{{{s.style}}}}">{{{{s.label}}}}</button>
          </sc-for>
        </div>
      </div>

      <sc-if value="{{{{hasFacets}}}}" hint-placeholder-val="{{{{true}}}}">
        <div style="position: relative;">
          <div role="group" aria-label="Filter by guest" class="srch-facets" style="display: flex; gap: 8px; overflow-x: auto; padding: 2px 0 10px; scrollbar-width: none;">
            <sc-for list="{{{{facets}}}}" as="f" hint-placeholder-count="6">
              <button type="button" onClick="{{{{f.pick}}}}" aria-pressed="{{{{f.pressed}}}}" style="{{{{f.style}}}}"><span>{{{{f.name}}}}</span><span style="{{{{f.countStyle}}}}">{{{{f.count}}}}</span></button>
            </sc-for>
          </div>
          <div aria-hidden="true" style="position: absolute; right: 0; top: 0; bottom: 10px; width: 48px; background: linear-gradient(270deg, #080403 10%, rgba(8,4,3,0) 100%); pointer-events: none;"></div>
        </div>
      </sc-if>

      <ol style="list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 520px), 1fr)); gap: 12px;">
        <sc-for list="{{{{rows}}}}" as="r" hint-placeholder-count="6">
          <li style="display: flex; flex-direction: column; gap: 14px; min-width: 0; padding: 18px; background: #0e0705; border: 1px solid rgba(254,203,122,0.18);">
            <div style="display: flex; align-items: center; gap: 14px; min-width: 0;">
              <img src="{{{{r.thumb}}}}" alt="" style="flex: none; width: 88px; height: 50px; object-fit: cover; border: 1px solid rgba(254,203,122,0.2);">
              <div style="display: flex; flex-direction: column; gap: 2px; min-width: 0; flex: 1 1 auto;">
                <span style="{MONO} font-size: 14px; font-weight: 800; color: #fcdf9a; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{{{{r.guest}}}}</span>
                <span style="font-size: 13px; color: #c9b8a6; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{{{{r.episode}}}}</span>
              </div>
              <span style="flex: none; padding: 3px 8px; background: rgba(254,203,122,0.14); color: #fecb7a; font-size: 13px; font-weight: 700; font-variant-numeric: tabular-nums;">{{{{r.time}}}}</span>
            </div>
            <p style="margin: 0; font-size: 16px; line-height: 1.55; color: #e8ddd1;">{{{{r.before}}}}<span style="background: #fecb7a; color: #000000; padding: 0 3px;">{{{{r.match}}}}</span>{{{{r.after}}}}</p>
            <a href="{{{{r.url}}}}" aria-label="{{{{r.aria}}}}" style="align-self: flex-start; display: inline-flex; align-items: center; gap: 10px; min-height: 44px; padding: 0 16px; border: 1px solid rgba(254,203,122,0.55); color: #ffffff; text-decoration: none; {MONO} font-size: 12px; font-weight: 800; letter-spacing: 0.04em;"><svg width="12" height="12" viewBox="0 0 18 18" aria-hidden="true"><path d="M4 2.5 L15 9 L4 15.5 Z" fill="#fecb7a"></path></svg>PLAY MOMENT</a>
          </li>
        </sc-for>
      </ol>

      <sc-if value="{{{{hasMore}}}}" hint-placeholder-val="{{{{true}}}}">
        <button type="button" onClick="{{{{more}}}}" style="align-self: center; display: inline-flex; align-items: center; min-height: 48px; padding: 0 24px; background: transparent; border: 1px solid rgba(254,203,122,0.55); border-radius: 0; color: #fecb7a; cursor: pointer; {MONO} font-size: 12px; font-weight: 800; letter-spacing: 0.06em;">{{{{moreText}}}}</button>
      </sc-if>

      <sc-if value="{{{{empty}}}}" hint-placeholder-val="{{{{false}}}}">
        <div style="display: flex; flex-direction: column; gap: 8px; padding: 40px 28px; border: 2px dashed rgba(254,203,122,0.4);">
          <p style="margin: 0; {MONO} font-size: 18px; font-weight: 800;">No guest has said that yet</p>
          <p style="margin: 0; color: #c9b8a6;">Try a broader word, or one of the topics above.</p>
        </div>
      </sc-if>
      <p style="margin: 0; font-size: 13px; color: #a8998b;">Searching the full transcripts of every episode, best matches first. Transcripts are automatic, so some names may be misspelled.</p>
    </section>'''

i = src.index('<section aria-labelledby="results"'); j = src.index('</section>\n  </main>') + len('</section>')
out = src[:i] + results + src[j:]
out = out.replace('<title>Search</title>', '<title>Search · proposal</title>')
out = out.replace("</style>\n</helmet>", ".srch-facets::-webkit-scrollbar{display:none}\n</style>\n</helmet>", 1)
out = out.replace("this.state = { query: 'judge' };", """this.state = { query: 'judge', guest: '', sort: 'rel', limit: 8, ai: null };
    this.aiTimer = null;
  }
  componentDidUpdate(prevProps, prevState) {
    if (prevState.query !== this.state.query) this.askAi();
  }
  componentWillUnmount() { clearTimeout(this.aiTimer); }
  askAi() {
    clearTimeout(this.aiTimer);
    const api = typeof window !== 'undefined' && window.__btrSearchApi;
    if (!api) return;
    this.aiTimer = setTimeout(() => {
      const c = this._candidates;
      if (!c || !c.items.length || c.q.trim().split(/\\s+/).length < 2) return;
      fetch(api, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(c) })
        .then((r) => (r.status === 200 ? r.json() : null))
        .then((j) => { if (j && Array.isArray(j.ids) && (this.state.query || '').trim() === c.q) this.setState({ ai: { q: c.q, ids: j.ids } }); })
        .catch(() => {});
    }, 700);""")

k = out.index('    let total = 0;')
e = out.index('\n  }\n}\n</script>')
logic = '''    const TH = ''' + json.dumps(TH) + ''';
    const STOP = new Set('a an the is are was were be been being am do does did done to of in on at for with and or but if so as it its this that these those there here i you he she we they me him her us them my your his our their what which who whom whose how why when where can could should would will shall may might must just about than then too very not no yes uh um oh like really know think mean get got go going gonna wanna kind sort thing things way lot also even still yeah okay ok right well say said says one two get let make made much many more most some any all every each other another into from out up down over again because fairly quite pretty dealing deal'.split(' '));
    const stem = (w) => { let x = w.replace(/[’']s$/, '').replace(/[^a-z0-9]/g, ''); if (x.length > 4) x = x.replace(/(ations?|ingly|ings?|edly|ments?|ness|ities|ity|ies|ied|ers?|ous|ed|es|ly|s)$/, ''); if (x.length > 3) x = x.replace(/e$/, ''); return x; };
    const toks = (t) => (t.toLowerCase().match(/[a-z0-9’']+/g) || []).filter((w) => w.length > 1 && !STOP.has(w)).map(stem).filter((w) => w.length > 1);
    const GROUPS = [
      ['judg', 'adjudic', 'mark', 'scor', 'panel', 'result', 'placing', 'scrutin'],
      ['fair', 'unfair', 'bias', 'honest', 'corrupt', 'politic', 'transpar', 'justic', 'equal', 'objectiv', 'subjectiv', 'favourit'],
      ['money', 'cost', 'expens', 'afford', 'pay', 'paid', 'fee', 'pric', 'budget', 'sponsor', 'financ'],
      ['safeguard', 'protect', 'safe', 'abus', 'welfar', 'child', 'kid', 'minor'],
      ['train', 'practic', 'rehears', 'lesson', 'session', 'drill'],
      ['injur', 'pain', 'recover', 'physio', 'bodi', 'rest', 'strain', 'fitnes'],
      ['compet', 'comp', 'championship', 'champion', 'event', 'contest', 'tournament'],
      ['federat', 'wdsf', 'wdc', 'organis', 'organiz', 'govern', 'association', 'rul'],
      ['strictly', 'televis', 'tv', 'show', 'bbc', 'celebrit'],
      ['nerv', 'pressur', 'anxieti', 'anxious', 'stres', 'confid', 'mental', 'mindset', 'fear', 'scar'],
      ['partner', 'coupl', 'partnership'],
      ['teach', 'coach', 'pupil', 'student', 'teacher', 'mentor'],
      ['music', 'song', 'compos', 'rhythm', 'tempo'],
      ['latin', 'samba', 'cha', 'rumba', 'paso', 'jiv'],
      ['ballroom', 'standard', 'waltz', 'tango', 'foxtrot', 'quickstep'],
      ['young', 'youth', 'junior', 'children', 'kid', 'generat'],
      ['futur', 'chang', 'improv', 'reform', 'vision', 'next'],
      ['woman', 'women', 'girl', 'femal', 'gender', 'mother', 'mum'],
      ['quit', 'retir', 'stop', 'leav', 'left', 'end'],
      ['love', 'passion', 'joy', 'fun', 'enjoy', 'happi']
    ];
    const syn = {};
    GROUPS.forEach((g) => g.forEach((a) => { syn[a] = syn[a] || new Set(); g.forEach((b) => { if (b !== a) syn[a].add(b); }); }));
    if (!this._idx) {
      const docs = [], df = {};
      let totalLen = 0;
      EPS.forEach((e, ei) => e.lines.forEach((l0, li) => {
        // each moment = this line + its neighbours, so short lines keep their context
        const win = e.lines.slice(Math.max(0, li - 1), li + 2);
        const l = [win[0][0], win.map((w) => w[1]).join(' ')];
        const tf = {}; const tk = toks(l[1]);
        tk.forEach((t) => { tf[t] = (tf[t] || 0) + 1; });
        Object.keys(tf).forEach((t) => { df[t] = (df[t] || 0) + 1; });
        totalLen += tk.length; docs.push({ e, ei, l, tf, len: tk.length });
      }));
      this._idx = { docs, df, avg: totalLen / Math.max(1, docs.length), N: docs.length };
    }
    const IDX = this._idx;
    const qTerms = Array.from(new Set(toks(q)));
    const weights = {};
    qTerms.forEach((t) => { weights[t] = Math.max(weights[t] || 0, 1); (syn[t] ? Array.from(syn[t]) : []).forEach((s) => { weights[s] = Math.max(weights[s] || 0, 0.45); }); });
    // prefix matches: "judg" also hits "judgement" etc.
    const keys = Object.keys(weights);
    const idf = (t) => Math.log(1 + (IDX.N - (IDX.df[t] || 0) + 0.5) / ((IDX.df[t] || 0) + 0.5));
    let hits = [];
    if (qTerms.length) {
      IDX.docs.forEach((d) => {
        let score = 0, matched = 0;
        const dk = Object.keys(d.tf);
        keys.forEach((k) => {
          let f = 0, best = null;
          dk.forEach((w) => { if (w === k || (weights[k] < 1 && k.length >= 5 && w.indexOf(k) === 0)) { f += d.tf[w]; best = best || w; } });
          if (!f) return;
          const bm = idf(best) * (f * 2.2) / (f + 1.2 * (0.25 + 0.75 * d.len / IDX.avg));
          score += bm * weights[k];
          if (weights[k] === 1) matched++;
        });
        if (!score) return;
        const cover = qTerms.length ? matched / qTerms.length : 0;
        if (qTerms.length > 1 && matched === 0) return;
        score *= 0.4 + cover;
        const low = d.l[1].toLowerCase();
        if (ql.length > 3 && low.indexOf(ql) >= 0) score += 4;
        // highlight: first word in the passage that starts with a query stem (then a synonym)
        let at = -1, len = 0;
        const order = qTerms.concat(keys.filter((k) => weights[k] < 1));
        for (const k of order) {
          const m = new RegExp('\\\\b' + k.replace(/[^a-z0-9]/g, ''), 'i').exec(d.l[1]);
          if (m) { at = m.index; const rest = /^[A-Za-z’']+/.exec(d.l[1].slice(at)); len = rest ? rest[0].length : k.length; break; }
        }
        if (at < 0) { at = 0; len = 0; }
        hits.push({ e: d.e, ei: d.ei, l: d.l, at, len, score, id: d.e.vid + ':' + d.l[0] });
      });
      hits.sort((a, b) => b.score - a.score);
      // drop overlapping windows (same episode, within 40s) and weak matches
      const taken = [];
      const best = hits.length ? hits[0].score : 0;
      hits = hits.filter((h) => {
        if (h.score < best * 0.28) return false;
        if (taken.some((t) => t.ei === h.ei && Math.abs(t.l[0] - h.l[0]) < 40)) return false;
        taken.push(h); return true;
      }).slice(0, 80);
      const ai = this.state.ai && this.state.ai.q === q ? this.state.ai.ids : null;
      if (ai) { const rank = {}; ai.forEach((id, i) => { rank[id] = i; }); hits.forEach((h) => { if (rank[h.id] !== undefined) h.score = 1e6 - rank[h.id]; }); }
      this._candidates = { q, items: hits.slice(0, 40).map((h) => ({ id: h.id, guest: h.e.guest, text: h.l[1].slice(0, 700) })) };
    }
    const perGuest = {};
    hits.forEach((h) => { perGuest[h.e.guest] = (perGuest[h.e.guest] || 0) + 1; });
    const guestF = this.state.guest && perGuest[this.state.guest] ? this.state.guest : '';
    let shown = guestF ? hits.filter((h) => h.e.guest === guestF) : hits.slice();
    if (this.state.sort === 'new') shown.sort((a, b) => a.ei - b.ei || a.l[0] - b.l[0]);
    else shown.sort((a, b) => b.score - a.score || a.ei - b.ei);
    const aiOn = !!(this.state.ai && this.state.ai.q === q);
    const limit = this.state.limit || 8;
    const rows = shown.slice(0, limit).map((h) => ({
      ...snip(h.l[1], h.at, h.len),
      guest: h.e.guest, episode: h.e.episode, time: fmt(h.l[0]),
      thumb: '/_blob/' + (TH[h.e.vid] || ''),
      url: 'https://www.youtube.com/watch?v=' + h.e.vid + '&t=' + h.l[0] + 's',
      aria: 'Play the moment from ' + h.e.guest + ' at ' + fmt(h.l[0])
    }));
    const pill = (on) => 'display: inline-flex; align-items: center; gap: 8px; flex: none; min-height: 40px; padding: 0 14px; border-radius: 0; cursor: pointer; font: inherit; font-size: 14px; font-weight: 600; white-space: nowrap; ' + (on ? 'background: #fecb7a; color: #000000; border: 1px solid #fecb7a;' : 'background: transparent; color: #ffffff; border: 1px solid rgba(254,203,122,0.35);');
    const cnt = (on) => 'font-size: 12px; font-weight: 700; ' + (on ? 'color: #000000; opacity: 0.7;' : 'color: #fecb7a;');
    const facetList = Object.keys(perGuest).sort((a, b) => perGuest[b] - perGuest[a]);
    const facets = [{ name: 'All guests', count: hits.length, key: '' }].concat(facetList.map((g) => ({ name: g, count: perGuest[g], key: g }))).map((f) => {
      const on = f.key === guestF;
      return { name: f.name, count: f.count, pressed: on ? 'true' : 'false', style: pill(on), countStyle: cnt(on), pick: () => this.setState({ guest: f.key, limit: 8 }) };
    });
    const segs = (on) => 'min-height: 40px; padding: 0 14px; border: 0; border-radius: 0; cursor: pointer; font: inherit; font-size: 14px; font-weight: 600; ' + (on ? 'background: #fecb7a; color: #000000;' : 'background: transparent; color: #ffffff;');
    const sorts = [['rel', 'Most relevant'], ['new', 'Newest first']].map(([k, label]) => ({ label, pressed: this.state.sort === k ? 'true' : 'false', style: segs(this.state.sort === k), pick: () => this.setState({ sort: k, limit: 8 }) }));
    const nEps = Object.keys(perGuest).length;
    const chips = topics.map((t) => {
      const on = ql === t.toLowerCase();
      return {
        label: chipLabels[t],
        pressed: on ? 'true' : 'false',
        style: 'min-height: 44px; padding: 0 18px; border-radius: 0; cursor: pointer; font: inherit; font-size: 15px; font-weight: 600; border: 2px solid #080403; ' + (on ? 'background: #080403; color: #fecb7a;' : 'background: transparent; color: #000000;'),
        pick: () => this.setState({ query: t, guest: '', limit: 8 })
      };
    });
    const summary = ql.length < 2
      ? 'Type a word to search ' + EPS.length + ' episodes'
      : hits.length + (hits.length === 1 ? ' moment' : ' moments') + ' from ' + nEps + (nEps === 1 ? ' guest' : ' guests') + ' about “' + q + '”' + (guestF ? ' · showing ' + guestF : '') + (aiOn ? ' · ranked by meaning' : '');
    const remaining = shown.length - rows.length;
    return { motionRef: this._motionRef || (this._motionRef = (el) => { if (el) { this._motionEl = el; btrMotion(el); } else { btrMotionStop(this._motionEl); } }), lp: this.props.lp ?? '',
      query: this.state.query,
      onQuery: (e) => this.setState({ query: e.target.value, guest: '', limit: 8 }),
      chips, rows, facets, sorts, summary,
      hasFacets: facetList.length > 1,
      hasMore: remaining > 0,
      moreText: 'SHOW ' + Math.min(8, remaining) + ' MORE · ' + remaining + ' LEFT',
      more: () => this.setState({ limit: limit + 8 }),
      empty: ql.length > 1 && hits.length === 0
    };'''
out = out[:k] + logic + out[e:]
open(D + '/Search-v2.dc.html', 'w').write(out)
print('ok', len(out))
