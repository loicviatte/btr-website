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
out = out.replace("this.state = { query: 'judge' };", "this.state = { query: 'judge', guest: '', sort: 'rel', limit: 8 };")

k = out.index('    let total = 0;')
e = out.index('\n  }\n}\n</script>')
logic = '''    const TH = ''' + json.dumps(TH) + ''';
    const terms = ql.split(/\\s+/).filter((t) => t.length > 1);
    const count = (hay, needle) => { let n = 0, p = hay.indexOf(needle); while (p >= 0) { n++; p = hay.indexOf(needle, p + needle.length); } return n; };
    let hits = [];
    if (ql.length > 1) {
      EPS.forEach((e, ei) => {
        e.lines.forEach((l) => {
          const low = l[1].toLowerCase();
          const phrase = count(low, ql);
          let termHits = 0, distinct = 0;
          terms.forEach((t) => { const c = count(low, t); termHits += c; if (c) distinct++; });
          if (!phrase && distinct < terms.length) return;
          const score = phrase * 4 + termHits + distinct * 2 + Math.min(2, termHits * 200 / Math.max(200, low.length));
          const at = phrase ? low.indexOf(ql) : low.indexOf(terms[0]);
          const len = phrase ? q.length : terms[0].length;
          hits.push({ e, ei, l, at, len, score });
        });
      });
    }
    const perGuest = {};
    hits.forEach((h) => { perGuest[h.e.guest] = (perGuest[h.e.guest] || 0) + 1; });
    const guestF = this.state.guest && perGuest[this.state.guest] ? this.state.guest : '';
    let shown = guestF ? hits.filter((h) => h.e.guest === guestF) : hits.slice();
    if (this.state.sort === 'new') shown.sort((a, b) => a.ei - b.ei || a.l[0] - b.l[0]);
    else shown.sort((a, b) => b.score - a.score || a.ei - b.ei);
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
      : hits.length + (hits.length === 1 ? ' moment' : ' moments') + ' from ' + nEps + (nEps === 1 ? ' guest' : ' guests') + ' mention “' + q + '”' + (guestF ? ' · showing ' + guestF : '');
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
