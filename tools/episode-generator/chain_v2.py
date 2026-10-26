"""Builds Chain-v2.dc.html (proposal) from Chain.dc.html: same header/footer/data, new scalable layout."""
import re, sys
D = sys.argv[1]
src = open(D + '/Chain.dc.html').read()
MONO = "font-family: 'PP Monument Extended', 'Arial Black', sans-serif;"
LINE = 'rgba(254,203,122,0.16)'

main = f'''<main style="max-width: 1440px; margin: 0 auto; box-sizing: border-box; padding: 48px clamp(16px, 4vw, 56px) 96px; display: flex; flex-direction: column; gap: 28px;">

    <div style="display: flex; flex-wrap: wrap; gap: 16px 64px; align-items: flex-end; justify-content: space-between;">
      <div style="flex: 1 1 560px; min-width: 0; display: flex; flex-direction: column; gap: 12px;">
        <p style="margin: 0; {MONO} font-size: 12px; font-weight: 800; letter-spacing: 0.12em; color: #fecb7a;">THE CHAIN</p>
        <h1 style="margin: 0; {MONO} font-size: clamp(28px, 3.6vw, 52px); font-weight: 800; line-height: 1.04; text-wrap: balance;">One question, passed from guest to guest</h1>
      </div>
      <p style="margin: 0; flex: 0 1 420px; min-width: 0; color: #c9b8a6;">Every guest records a question for the next one, without knowing who it will be. Walk the chain link by link, or jump straight to a guest.</p>
    </div>

    <div style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 14px 24px; padding-top: 8px;">
      <div style="display: flex; align-items: baseline; gap: 14px; min-width: 0; flex-wrap: wrap;">
        <span style="{MONO} font-size: 12px; font-weight: 800; letter-spacing: 0.12em; color: #fecb7a; white-space: nowrap;">LINK {{{{nav.pos}}}} / {{{{nav.total}}}}</span>
        <span style="color: #c9b8a6; font-size: 15px;">{{{{nav.from}}}} → {{{{nav.to}}}}</span>
      </div>
      <div style="display: flex; align-items: center; gap: 8px; flex: 0 1 auto;">
        <div style="position: relative; flex: 1 1 220px; min-width: 0;">
          <label for="chainq" style="position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap;">Find a guest in the chain</label>
          <input id="chainq" type="search" value="{{{{q}}}}" onChange="{{{{onQ}}}}" placeholder="Find a guest" autocomplete="off" style="width: 100%; min-width: 0; height: 48px; box-sizing: border-box; padding: 0 16px; background: #0e0705; border: 1px solid rgba(254,203,122,0.35); border-radius: 0; color: #ffffff; font: inherit; font-size: 15px;">
          <sc-if value="{{{{hasResults}}}}" hint-placeholder-val="{{{{false}}}}">
            <div role="listbox" aria-label="Guests" style="position: absolute; left: 0; right: 0; top: calc(100% + 4px); z-index: 30; max-height: 300px; overflow-y: auto; background: #110906; border: 1px solid rgba(254,203,122,0.35); box-shadow: 0 18px 40px rgba(0,0,0,0.5);">
              <sc-for list="{{{{results}}}}" as="r" hint-placeholder-count="3">
                <button type="button" onClick="{{{{r.go}}}}" style="display: flex; align-items: center; justify-content: space-between; gap: 12px; width: 100%; min-height: 48px; padding: 0 16px; background: transparent; border: 0; border-bottom: 1px solid {LINE}; border-radius: 0; color: #ffffff; font: inherit; font-size: 15px; text-align: left; cursor: pointer;"><span>{{{{r.name}}}}</span><span style="font-size: 13px; color: #c9b8a6;">{{{{r.label}}}}</span></button>
              </sc-for>
            </div>
          </sc-if>
        </div>
        <button type="button" onClick="{{{{prev}}}}" aria-label="Previous link" style="display: grid; place-items: center; flex: none; width: 48px; height: 48px; padding: 0; background: transparent; border: 1px solid rgba(254,203,122,0.55); border-radius: 0; color: #fecb7a; cursor: pointer;"><svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="square"><path d="M15 5l-7 7 7 7"></path></svg></button>
        <button type="button" onClick="{{{{next}}}}" aria-label="Next link" style="display: grid; place-items: center; flex: none; width: 48px; height: 48px; padding: 0; background: #fecb7a; border: 1px solid #fecb7a; border-radius: 0; color: #000000; cursor: pointer;"><svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="square"><path d="M9 5l7 7-7 7"></path></svg></button>
      </div>
    </div>

    <div style="position: relative; border-top: 1px solid {LINE}; border-bottom: 1px solid {LINE};">
      <ol ref="{{{{stripRef}}}}" aria-label="Guests in order" class="chain-strip" style="list-style: none; margin: 0; padding: 22px 48px; display: flex; align-items: flex-start; overflow-x: auto; scroll-behavior: smooth; scrollbar-width: none;">
        <sc-for list="{{{{nodes}}}}" as="n" hint-placeholder-count="10">
          <li style="display: flex; align-items: flex-start; flex: none;">
            <button type="button" onClick="{{{{n.pick}}}}" aria-pressed="{{{{n.pressed}}}}" aria-label="{{{{n.aria}}}}" style="display: flex; flex-direction: column; align-items: center; gap: 8px; width: 72px; padding: 0; background: transparent; border: 0; border-radius: 0; color: #ffffff; font: inherit; cursor: pointer;">
              <span style="{{{{n.boxStyle}}}}">{{{{n.initials}}}}</span>
              <span style="{{{{n.nameStyle}}}}">{{{{n.first}}}}</span>
            </button>
            <sc-if value="{{{{n.hasNext}}}}" hint-placeholder-val="{{{{true}}}}">
              <span aria-hidden="true" style="{{{{n.lineStyle}}}}"></span>
            </sc-if>
          </li>
        </sc-for>
      </ol>
      <div aria-hidden="true" style="position: absolute; left: 0; top: 0; bottom: 0; width: 56px; background: linear-gradient(90deg, #080403 20%, rgba(8,4,3,0) 100%); pointer-events: none;"></div>
      <div aria-hidden="true" style="position: absolute; right: 0; top: 0; bottom: 0; width: 56px; background: linear-gradient(270deg, #080403 20%, rgba(8,4,3,0) 100%); pointer-events: none;"></div>
    </div>

    <section aria-live="polite" aria-label="Selected link" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 440px), 1fr)); gap: 20px;">
      <div style="position: relative; overflow: hidden; box-sizing: border-box; min-height: 100%; padding: clamp(24px, 3.4vw, 48px); background: #110906; border: 1px solid rgba(254,203,122,0.25); display: flex; flex-direction: column; justify-content: space-between; gap: 32px;">
        <div aria-hidden="true" style="position: absolute; inset: 0; background: linear-gradient(180deg, rgba(0,0,0,0) 45%, rgba(159,137,69,0.1) 72%, rgba(223,191,100,0.28) 100%); pointer-events: none;"></div>
        <div style="position: relative; display: flex; flex-wrap: wrap; align-items: center; gap: 12px 16px;">
          <span style="display: flex; align-items: center; gap: 10px;"><span style="display: grid; place-items: center; width: 40px; height: 40px; border: 1px solid rgba(254,203,122,0.5); color: #fecb7a; {MONO} font-size: 12px; font-weight: 800;">{{{{sel.fromIni}}}}</span><span style="display: flex; flex-direction: column;"><span style="font-size: 12px; color: #c9b8a6;">Asked by</span><span style="font-weight: 600;">{{{{sel.from}}}}</span></span></span>
          <span aria-hidden="true" style="color: #fecb7a; font-size: 20px;">→</span>
          <span style="display: flex; align-items: center; gap: 10px;"><span style="display: grid; place-items: center; width: 40px; height: 40px; background: #fecb7a; color: #000000; {MONO} font-size: 12px; font-weight: 800;">{{{{sel.toIni}}}}</span><span style="display: flex; flex-direction: column;"><span style="font-size: 12px; color: #c9b8a6;">For</span><span style="font-weight: 600;">{{{{sel.to}}}}</span></span></span>
        </div>
        <div style="position: relative; display: flex; flex-direction: column; gap: 12px;">
          <p style="margin: 0; {MONO} font-size: 11px; font-weight: 800; letter-spacing: 0.12em; color: #fecb7a;">{{{{sel.kind}}}}</p>
          <p style="margin: 0; {MONO} font-size: clamp(22px, 2.4vw, 36px); font-weight: 800; line-height: 1.16; text-wrap: balance;"><span style="color: #fecb7a;">{{{{sel.openQ}}}}</span>{{{{sel.text}}}}<span style="color: #fecb7a;">{{{{sel.closeQ}}}}</span></p>
        </div>
        <sc-if value="{{{{sel.hasAsk}}}}" hint-placeholder-val="{{{{false}}}}">
          <a href="{{{{sel.askUrl}}}}" style="position: relative; align-self: flex-start; font-size: 14px;">Watch {{{{sel.fromFirst}}}} ask it at {{{{sel.askTime}}}}</a>
        </sc-if>
      </div>

      <div style="display: flex; flex-direction: column; gap: 10px; min-width: 0;">
        <sc-if value="{{{{sel.hasAnswer}}}}" hint-placeholder-val="{{{{true}}}}">
          <a href="{{{{sel.answerUrl}}}}" aria-label="{{{{sel.playAria}}}}" style="position: relative; display: block; width: 100%; aspect-ratio: 16 / 9; overflow: hidden; background: #000000; border: 1px solid rgba(254,203,122,0.25);">
            <img src="{{{{sel.thumb}}}}" alt="" style="position: absolute; inset: 0; width: 100%; height: 100%; max-width: none; object-fit: cover;">
            <span aria-hidden="true" style="position: absolute; inset: 0; background: rgba(8,4,3,0.3);"></span>
            <span aria-hidden="true" style="position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); display: grid; place-items: center; width: 80px; height: 80px; background: #fecb7a;"><svg width="28" height="28" viewBox="0 0 18 18"><path d="M5 2.5 L15.5 9 L5 15.5 Z" fill="#000000"></path></svg></span>
            <span style="position: absolute; left: 0; right: 0; bottom: 0; display: flex; align-items: center; gap: 12px; padding: 12px 16px; background: linear-gradient(180deg, rgba(8,4,3,0) 0%, rgba(8,4,3,0.9) 100%); color: #ffffff; font-size: 14px;"><span style="padding: 3px 8px; background: #fecb7a; color: #000000; font-weight: 700; font-variant-numeric: tabular-nums;">{{{{sel.time}}}}</span><span>{{{{sel.answerCaption}}}}</span></span>
          </a>
        </sc-if>
        <sc-if value="{{{{sel.open}}}}" hint-placeholder-val="{{{{false}}}}">
          <div style="display: flex; flex-direction: column; justify-content: center; gap: 12px; width: 100%; aspect-ratio: 16 / 9; box-sizing: border-box; padding: 32px; border: 2px dashed #fecb7a; background: #0e0705;">
            <span style="{MONO} font-size: 14px; font-weight: 800; color: #fecb7a;">STILL OPEN</span>
            <span style="color: #e8ddd1; max-width: 460px;">{{{{sel.openText}}}}</span>
          </div>
        </sc-if>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
          <button type="button" onClick="{{{{prev}}}}" style="{{{{ctx.prevStyle}}}}"><span style="font-size: 12px; color: #c9b8a6;">← {{{{ctx.prevLabel}}}}</span><span style="font-size: 14px; font-weight: 600; line-height: 1.35;">{{{{ctx.prevText}}}}</span></button>
          <button type="button" onClick="{{{{next}}}}" style="{{{{ctx.nextStyle}}}}"><span style="font-size: 12px; color: #c9b8a6;">{{{{ctx.nextLabel}}}} →</span><span style="font-size: 14px; font-weight: 600; line-height: 1.35;">{{{{ctx.nextText}}}}</span></button>
        </div>
      </div>
    </section>

    <details class="chain-all" style="border-top: 1px solid {LINE}; padding-top: 8px;">
      <summary style="display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 56px; cursor: pointer; list-style: none; {MONO} font-size: 13px; font-weight: 800; letter-spacing: 0.06em;"><span>BROWSE ALL {{{{nav.total}}}} QUESTIONS</span><span aria-hidden="true" style="color: #fecb7a; font-size: 22px; line-height: 1;">+</span></summary>
      <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 300px), 1fr)); gap: 8px; padding: 8px 0 16px;">
        <sc-for list="{{{{links}}}}" as="l" hint-placeholder-count="6">
          <button type="button" onClick="{{{{l.pick}}}}" aria-pressed="{{{{l.pressed}}}}" style="{{{{l.cardStyle}}}}"><span style="{MONO} font-size: 10px; font-weight: 800; letter-spacing: 0.08em; opacity: 0.8;">{{{{l.num}}}} · {{{{l.fromShort}}}} → {{{{l.toShort}}}}</span><span style="font-size: 14px; font-weight: 600; line-height: 1.35; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">{{{{l.text}}}}</span></button>
        </sc-for>
      </div>
    </details>
  </main>'''

i = src.index('<main'); j = src.index('</main>') + len('</main>')
out = src[:i] + main + src[j:]
out = out.replace('<title>The Chain</title>', '<title>The Chain · proposal</title>')
out = out.replace("</style>\n</helmet>", ".chain-strip::-webkit-scrollbar{display:none}\ndetails.chain-all summary::-webkit-details-marker{display:none}\ndetails.chain-all[open] summary span:last-child{transform:rotate(45deg)}\ndetails.chain-all summary span:last-child{transition:transform .3s ease}\n</style>\n</helmet>", 1)
out = out.replace("data-props='{\"$preview\":{\"width\":1440,\"height\":2000}}'", "data-props='{\"$preview\":{\"width\":1440,\"height\":1500}}'")
out = out.replace('this.state = { picked: 9 };', "this.state = { picked: 10, q: '' };\n    this.strip = null;")

# logic: replace from 'const picked = this.state.picked;' to end of renderVals return
k = out.index('    const picked = this.state.picked;')
e = out.index('\n  }\n}\n</script>')
logic = r'''    const picked = this.state.picked;
    const mono = "font-family: 'PP Monument Extended', 'Arial Black', sans-serif; font-weight: 800;";
    const total = qs.length;
    const go = (i) => { const n = Math.max(0, Math.min(total - 1, i)); this.setState({ picked: n, q: '' }); };
    const nodes = guests.map((g, i) => {
      const isNext = i === guests.length - 1;
      const active = i === picked || i === picked + 1;
      let box = 'display: grid; place-items: center; width: 52px; height: 52px; box-sizing: border-box; font-size: 13px; transition: background-color .3s ease, color .3s ease, border-color .3s ease; ' + mono;
      if (isNext) box += ' border: 2px dashed #fecb7a; color: #fecb7a; font-size: 20px;';
      else if (active) box += ' background: #fecb7a; color: #000000; border: 1px solid #fecb7a;';
      else box += ' border: 1px solid rgba(254,203,122,0.4); color: #c9b8a6;';
      const lineActive = i === picked;
      const openLine = i === guests.length - 2;
      let line = 'display: block; flex: none; width: 28px; height: 0; margin-top: 26px;';
      line += openLine ? ' border-top: 2px dashed rgba(254,203,122,0.8);' : (lineActive ? ' border-top: 3px solid #fecb7a;' : ' border-top: 2px solid rgba(254,203,122,0.3);');
      return {
        ...g,
        first: isNext ? 'Next' : g.name.split(' ')[0],
        boxStyle: box,
        nameStyle: 'font-size: 12px; line-height: 1.2; text-align: center; color: ' + (active ? '#fecb7a' : '#c9b8a6') + '; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 72px;',
        lineStyle: line,
        hasNext: !isNext,
        pressed: active ? 'true' : 'false',
        aria: isNext ? 'Show the question still open' : g.name,
        pick: () => go(Math.max(0, i - 1))
      };
    });
    const links = qs.map((x, i) => {
      const sel = i === picked;
      const open = i === total - 1;
      let card = 'display: flex; flex-direction: column; gap: 6px; width: 100%; min-height: 44px; box-sizing: border-box; padding: 14px 16px; text-align: left; border-radius: 0; cursor: pointer; font: inherit;';
      card += sel ? ' background: #fecb7a; color: #000000; border: 1px solid #fecb7a;' : ' background: #0e0705; color: #ffffff; border: 1px solid rgba(254,203,122,0.18);';
      if (open && !sel) card += ' border-style: dashed; border-color: rgba(254,203,122,0.6);';
      return { ...x, num: String(i + 1).padStart(2, '0'), fromShort: guests[i].initials, toShort: guests[i + 1].initials, pressed: sel ? 'true' : 'false', cardStyle: card, pick: () => { go(i); } };
    });
    const s = qs[picked];
    const isOpen = picked === total - 1;
    const from = guests[picked], to = guests[picked + 1];
    const isQ = s.kind === 'QUESTION';
    const q = (this.state.q || '').trim().toLowerCase();
    const results = q ? guests.map((g, i) => ({ g, i })).filter((r) => r.g.vid && r.g.name.toLowerCase().indexOf(q) >= 0).slice(0, 8).map((r) => ({ name: r.g.name, label: r.g.label, go: () => go(Math.max(0, r.i - 1)) })) : [];
    const ctxStyle = (on) => 'display: flex; flex-direction: column; gap: 6px; min-width: 0; box-sizing: border-box; padding: 14px 16px; text-align: left; background: #0e0705; color: #ffffff; border: 1px solid rgba(254,203,122,0.18); border-radius: 0; font: inherit; cursor: ' + (on ? 'pointer' : 'default') + '; opacity: ' + (on ? '1' : '0.35') + ';';
    const pq = qs[picked - 1], nq = qs[picked + 1];
    return { motionRef: this._motionRef || (this._motionRef = (el) => { if (el) { this._motionEl = el; btrMotion(el); } else { btrMotionStop(this._motionEl); } }), lp: this.props.lp ?? '',
      nodes, links, results,
      hasResults: results.length > 0,
      q: this.state.q,
      onQ: (e) => this.setState({ q: e.target.value }),
      prev: () => go(picked - 1),
      next: () => go(picked + 1),
      stripRef: (el) => { this.strip = el; },
      nav: { pos: picked + 1, total, from: from.name, to: to.name },
      ctx: {
        prevStyle: ctxStyle(!!pq), nextStyle: ctxStyle(!!nq),
        prevLabel: pq ? 'Previous · ' + guests[picked - 1].initials + ' → ' + guests[picked].initials : 'Start of the chain',
        prevText: pq ? pq.text : 'Kiera Brunton asked the first question.',
        nextLabel: nq ? 'Next · ' + guests[picked + 1].initials + ' → ' + guests[picked + 2].initials : 'End of the chain',
        nextText: nq ? nq.text : 'The next guest is coming soon.'
      },
      sel: {
        text: s.text, kind: s.kind, openQ: isQ ? '“' : '', closeQ: isQ ? '”' : '',
        from: from.name, to: to.name, fromIni: from.initials, toIni: to.initials, fromFirst: from.name.split(' ')[0],
        hasAsk: !!s.ask, askUrl: s.ask ? yt(from.vid, s.ask) : '', askTime: s.ask ? fmt(s.ask) : '',
        hasAnswer: !isOpen && !s.pending,
        answerUrl: isOpen || s.pending ? '' : yt(to.vid, s.ans),
        thumb: to.vid ? '/_blob/' + thumbs[to.vid] : '',
        time: s.ans ? fmt(s.ans) : '',
        answerCaption: 'Plays from the moment ' + to.name.split(' ')[0] + ' hears it',
        playAria: 'Play ' + to.name + '’s answer from ' + (s.ans ? fmt(s.ans) : 'the start'),
        open: isOpen || !!s.pending,
        openText: s.pending ? 'Oti hears Leila’s question in part 2 of her episode, out next week.' : 'Oti records her question for the next guest in part 2. It goes to the guest after her.'
      }
    };'''
out = out[:k] + logic + out[e:]
# center selected node in the strip
cm = '  renderVals() {'
center = '''  componentDidMount() { this.centerStrip(false); }
  componentDidUpdate(prevProps, prevState) { if (prevState.picked !== this.state.picked) this.centerStrip(true); }
  centerStrip(smooth) {
    const s = this.strip; if (!s) return;
    const li = s.children[Math.min(this.state.picked + 1, s.children.length - 1)];
    if (!li) return;
    const x = li.offsetLeft - s.clientWidth / 2 + li.offsetWidth / 2;
    try { s.scrollTo({ left: Math.max(0, x), behavior: smooth ? 'smooth' : 'auto' }); } catch (e) { s.scrollLeft = Math.max(0, x); }
  }
'''
assert out.count(cm) == 1
out = out.replace(cm, center + cm)
open(D + '/Chain-v2.dc.html', 'w').write(out)
print('ok', len(out))
