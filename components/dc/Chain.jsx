'use client';
// GENERATED from design/Chain.dc.html by tools/compile.mjs. Edit the design file, then run npm run compile.
import React from 'react';
import { DCLogic, css, dcUrl, dcExt } from '../../lib/dc';


function btrMotion(root) {
  if (!root || root.__btrMotion) return;
  root.__btrMotion = true;
  const doc = root.ownerDocument, win = doc.defaultView;
  if (!win || !('IntersectionObserver' in win)) return;
  const reduce = win.matchMedia && win.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const gold = 'rgb(254, 203, 122)';
  root.querySelectorAll('a, button, summary').forEach((el) => {
    if (el.closest('header') && !el.closest('details')) { if (getComputedStyle(el).backgroundColor !== gold) return; }
    const cs = getComputedStyle(el);
    if (cs.position === 'absolute' && !el.closest('main')) return;
    if (cs.backgroundColor === gold) el.dataset.btn = 'gold';
    else if (parseFloat(cs.borderTopWidth) > 0 && cs.borderTopStyle === 'solid' && parseFloat(cs.minHeight) >= 40 && cs.display.indexOf('flex') >= 0) el.dataset.btn = 'line';
  });
  root.querySelectorAll('main a img').forEach((img) => {
    const p = img.parentElement;
    if (p && getComputedStyle(p).overflow === 'hidden') img.dataset.zoom = '1';
  });
  const header = root.querySelector('header');
  const mainEl = root.querySelector('main');
  if (header && mainEl && mainEl.firstElementChild) {
    const hh = header.offsetHeight || 80;
    const t = Array.from({ length: 21 }, (_, i) => i / 20);
    const hio = new win.IntersectionObserver((es) => { es.forEach((e) => { header.dataset.scrolled = e.boundingClientRect.top < hh - 4 ? '1' : '0'; }); }, { threshold: t });
    hio.observe(mainEl.firstElementChild);
    root.__btrHio = hio;
  }
  if (reduce) return;
  const SEL = 'main h1, main h2, main h3, main p, main img, main li, main article, main figure, main blockquote, main video, footer img, footer p';
  const SKIP = '.atl-map, .atl-track, [role="dialog"], .btr-intro, header, details, form, [aria-live], button';
  const all = Array.from(root.querySelectorAll(SEL)).filter((el) => {
    if (el.closest(SKIP)) return false;
    const cs = getComputedStyle(el);
    if ((cs.position === 'absolute' || cs.position === 'fixed') && el.tagName !== 'IMG') return false;
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    return true;
  });
  const set = new Set(all);
  const targets = all.filter((el) => { let a = el.parentElement; while (a && a !== root) { if (set.has(a)) return false; a = a.parentElement; } return true; });
  const start = () => {
    targets.forEach((el) => { el.dataset.rv = '0'; });
    let queue = [], timer = null;
    const flush = () => {
      queue.sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top || a.getBoundingClientRect().left - b.getBoundingClientRect().left);
      queue.forEach((el, i) => { el.style.setProperty('--rvd', Math.min(i * 70, 560) + 'ms'); el.dataset.rv = '1'; });
      queue = []; timer = null;
    };
    const io = new win.IntersectionObserver((es) => {
      es.forEach((e) => { if (e.isIntersecting) { queue.push(e.target); io.unobserve(e.target); } });
      if (queue.length && !timer) timer = win.setTimeout(flush, 30);
    }, { rootMargin: '0px', threshold: 0.06 });
    targets.forEach((el) => io.observe(el));
    root.__btrIo = io;
  };
  const intro = () => { const b = root.querySelector('.btr-intro'); return b && b.offsetParent !== null && getComputedStyle(b).display !== 'none'; };
  if (!intro()) { start(); return; }
  const wait = win.setInterval(() => { if (!intro()) { win.clearInterval(wait); start(); } }, 120);
  root.__btrWait = wait;
}
function btrMotionStop(root) {
  if (!root) return;
  if (root.__btrIo) root.__btrIo.disconnect();
  if (root.__btrHio) root.__btrHio.disconnect();
  if (root.__btrWait) root.ownerDocument.defaultView.clearInterval(root.__btrWait);
  root.__btrMotion = false;
}
class Component extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { picked: 10, q: '', canL: false, canR: false };
    this.strip = null;
  }
  componentDidMount() {
    this.centerStrip(false);
    this.edges();
    this._onResize = () => this.edges();
    try { window.addEventListener('resize', this._onResize); } catch (e) {}
    setTimeout(() => this.edges(), 400);
  }
  componentWillUnmount() { try { window.removeEventListener('resize', this._onResize); } catch (e) {} }
  edges() {
    const s = this.strip; if (!s) return;
    const canL = s.scrollLeft > 8, canR = s.scrollLeft + s.clientWidth < s.scrollWidth - 8;
    if (canL !== this.state.canL || canR !== this.state.canR) this.setState({ canL, canR });
  }
  nudge(dir) {
    const s = this.strip; if (!s) return;
    const dx = dir * Math.max(160, s.clientWidth * 0.7);
    try { s.scrollBy({ left: dx, behavior: 'smooth' }); } catch (e) { s.scrollLeft += dx; }
  }
  componentDidUpdate(prevProps, prevState) { if (prevState.picked !== this.state.picked) this.centerStrip(true); }
  centerStrip(smooth) {
    const s = this.strip; if (!s) return;
    const li = s.children[Math.min(this.state.picked + 1, s.children.length - 1)];
    if (!li) return;
    const x = li.offsetLeft - s.clientWidth / 2 + li.offsetWidth / 2;
    try { s.scrollTo({ left: Math.max(0, x), behavior: smooth ? 'smooth' : 'auto' }); } catch (e) { s.scrollLeft = Math.max(0, x); }
  }
  renderVals() {
    const guests = [
      { name: 'Kiera Brunton', initials: 'KB', label: '13 Jul', vid: 'ktcEnjS1SF4' },
      { name: 'Michael Shelton', initials: 'MS', label: '20 Jul', vid: '6SKeUQM4E1k' },
      { name: 'Jaime Dieguez', initials: 'JD', label: '28 Jul', vid: 'bIJ-LJsgLbE' },
      { name: 'Nicole Cutler', initials: 'NC', label: '4 Aug', vid: '-wx7h1S8eQ8' },
      { name: 'James Wilson', initials: 'JW', label: '11 Aug', vid: 'r3ZKwpj9J5U' },
      { name: 'Anthony Rutherford', initials: 'AR', label: '18 Aug', vid: '8tsAnwQanY0' },
      { name: 'Phemelo Mabuse', initials: 'PH', label: '25 Aug', vid: 'aW03-xv1Iyc' },
      { name: 'Ian Waite', initials: 'IW', label: '1 Sep', vid: 'c8xICOkFwEI' },
      { name: 'Oskar Odiakosa', initials: 'OO', label: '8 & 15 Sep', vid: 'o3Daq6WSuzs' },
      { name: 'Peter Nash', initials: 'PN', label: '24 & 30 Sep', vid: 'gmLzaixhDqo' },
      { name: 'Peter Maxwell', initials: 'PM', label: '6 Oct', vid: 'SFl--dzjGvE' },
      { name: 'Leila Stewart', initials: 'LS', label: '14 Oct', vid: 'yO0vuX-Ygpc' },
      { name: 'Oti Mabuse', initials: 'OM', label: '22 Oct', vid: 'pi1IhRO8v4w' },
      { name: 'Next guest', initials: '?', label: 'Coming soon', vid: '' }
    ];
    const qs = [
      { text: 'What made you fall in love with dance?', kind: 'QUESTION', ask: 2998, ans: 3960 },
      { text: 'If you could ask any composer, living or dead, to write some music for you to dance to, who would it be and why?', kind: 'QUESTION', ask: 4040, ans: 4600 },
      { text: 'If you could design the competitive world, how would you do it?', kind: 'QUESTION', ask: 4820, ans: 8051 },
      { text: 'Do you think it would be a good idea to have AI judges?', kind: 'QUESTION', ask: null, ans: 6080 },
      { text: 'Which dance would you add to the ballroom category, and which to the Latin, that hasn’t been acknowledged yet? And why?', kind: 'QUESTION', ask: 6300, ans: 6420 },
      { text: 'If you could change three things about your journey in dance, what would they be?', kind: 'QUESTION', ask: 6634, ans: 5300 },
      { text: 'What emphasis should coaches, teachers and the sport itself put on recovery and the physical strain on the body?', kind: 'QUESTION', ask: null, ans: 4125 },
      { text: 'If you’re a coach or a dance teacher, what is the most important thing you want from your pupil?', kind: 'QUESTION', ask: null, ans: 3577 },
      { text: 'What are the priorities that make a good dance culture in the UK? Pick three things we should focus on.', kind: 'QUESTION', ask: null, ans: 2151 },
      { text: 'What can we all do to improve our dance world? Just the one thing.', kind: 'QUESTION', ask: null, ans: 4990 },
      { text: 'Do we take ballroom and Latin dancing too seriously, or not seriously enough?', kind: 'QUESTION', ask: null, ans: 6040 },
      { text: 'Leila’s question for Oti', kind: 'IN OTI’S PART 2', ask: null, ans: null, pending: true },
      { text: 'Oti’s question for the next guest', kind: 'COMING IN PART 2', ask: null, ans: null }
    ];
    const thumbs = {
      'ktcEnjS1SF4': 'f50ede373b1848443c2e35c4a49fbc4b', '6SKeUQM4E1k': '09c68242801f4b282a3331acd5a342fd', 'bIJ-LJsgLbE': '497a5e87cb63153785580ffe42072102',
      '-wx7h1S8eQ8': '62bea6b1946b2ce7570d19f8db90e02c', 'r3ZKwpj9J5U': 'a7b5d5f61d5830023b2850ae7d54663e', '8tsAnwQanY0': 'bd668a798a2b7ef1ef1f2012744c7a8f',
      'aW03-xv1Iyc': '17ff73d440c3699a9cd0f1dbb6c14d99', 'c8xICOkFwEI': 'fda5fad96e887160af9fa9a1fcf78002', 'o3Daq6WSuzs': '061d818947d1c0a6765d98577a1cb7bf',
      'gmLzaixhDqo': 'bcea0d26b5e611d1a856631033e7a45c', 'SFl--dzjGvE': '24eb7384bb059d4fdbde52ab2838ee99', 'yO0vuX-Ygpc': 'd6442b82364bfd30966d31b8267286d1',
      'pi1IhRO8v4w': '6704faaedd6251c16887bc9024d7381e'
    };
    const fmt = (s) => { const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60; return (h ? h + ':' + String(m).padStart(2, '0') : String(m).padStart(2, '0')) + ':' + String(x).padStart(2, '0'); };
    const yt = (vid, t) => 'https://www.youtube.com/watch?v=' + vid + (t ? '&t=' + t + 's' : '');
    const picked = this.state.picked;
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
      onStrip: () => this.edges(),
      canL: this.state.canL,
      canR: this.state.canR,
      scrollL: () => this.nudge(-1),
      scrollR: () => this.nudge(1),
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
    };
  }
}

Component.prototype.render = function render() {
  const v = this.renderVals() || {};
  return (<>{" "}{" "}<div ref={v.motionRef} style={{"background":"#080403","color":"#ffffff","fontFamily":"'Archivo', 'Helvetica Neue', Arial, sans-serif","fontStretch":"108%","fontSize":"17px","lineHeight":"1.55"}}>{" "}<header style={{"position":"sticky","top":"0","zIndex":"50","background":"rgba(8,4,3,0.92)","WebkitBackdropFilter":"blur(12px)","backdropFilter":"blur(12px)","borderBottom":"1px solid rgba(254,203,122,0.16)"}}>{" "}<nav aria-label="Main" style={{"maxWidth":"1440px","margin":"0 auto","boxSizing":"border-box","padding":"16px clamp(16px, 4vw, 56px)","display":"flex","flexWrap":"wrap","alignItems":"center","justifyContent":"space-between","gap":"12px 32px"}}>{" "}<a {...dcExt(`${(v.lp) ?? ''}Main.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Main.dc.html`)} aria-label="Break The Routine, home" style={{"display":"block","lineHeight":"0"}}><img className="btr-logo-w" src={dcUrl("/_blob/745152d7135187f4378802fc563253b5")} alt="BTR, The Dancesport Podcast" style={{"width":"104px","height":"auto","display":"block"}} /></a>{" "}<div className="btr-links" style={{"display":"flex","flexWrap":"wrap","alignItems":"center","gap":"0 26px","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"12px","fontWeight":"800","letterSpacing":"0.06em","textTransform":"uppercase"}}>{" "}<a {...dcExt(`${(v.lp) ?? ''}Episodes.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Episodes.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"14px 0"}}>{"Episodes"}</a>{" "}<a {...dcExt(`${(v.lp) ?? ''}Chain.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Chain.dc.html`)} aria-current="page" style={{"color":"#fecb7a","textDecoration":"none","padding":"14px 0","borderBottom":"2px solid #fecb7a"}}>{"The Chain"}</a>{" "}<a {...dcExt(`${(v.lp) ?? ''}Atlas.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Atlas.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"14px 0"}}>{"World Atlas"}</a>{" "}<a {...dcExt(`${(v.lp) ?? ''}Search.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Search.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"14px 0"}}>{"Search"}</a>{" "}<a {...dcExt(`${(v.lp) ?? ''}About.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}About.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"14px 0"}}>{"About"}</a>{" "}</div>{" "}<a className="btr-sub" {...dcExt("https://www.youtube.com/@BreakTheRoutinePodcast")} href={dcUrl("https://www.youtube.com/@BreakTheRoutinePodcast")} style={{"display":"inline-flex","alignItems":"center","minHeight":"44px","boxSizing":"border-box","padding":"0 18px","background":"#fecb7a","color":"#000000","textDecoration":"none","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"12px","fontWeight":"800","letterSpacing":"0.04em","textTransform":"uppercase"}}>{"Subscribe"}</a>{" "}<details className="btr-burger" style={{"position":"static"}}>{" "}<summary className="btr-burger-btn" aria-label="Menu" style={{"display":"grid","placeItems":"center","width":"48px","height":"48px","boxSizing":"border-box","border":"1px solid rgba(254,203,122,0.55)","color":"#fecb7a","cursor":"pointer"}}>{" "}<svg className="btr-burger-open" aria-hidden="true" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square"><path d="M2 5h16M2 10h16M2 15h16"></path></svg>{" "}<svg className="btr-burger-close" aria-hidden="true" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square"><path d="M4 4l12 12M16 4L4 16"></path></svg>{" "}</summary>{" "}<div style={{"position":"absolute","left":"0","right":"0","top":"100%","boxSizing":"border-box","padding":"8px clamp(16px, 4vw, 56px) 24px","background":"#080403","borderBottom":"1px solid rgba(254,203,122,0.3)","display":"flex","flexDirection":"column"}}>{" "}<a {...dcExt(`${(v.lp) ?? ''}Episodes.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Episodes.dc.html`)} style={{"display":"block","padding":"16px 0","borderBottom":"1px solid rgba(254,203,122,0.16)","color":"#ffffff","textDecoration":"none","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"15px","fontWeight":"800","letterSpacing":"0.06em","textTransform":"uppercase"}}>{"Episodes"}</a>{" "}<a {...dcExt(`${(v.lp) ?? ''}Chain.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Chain.dc.html`)} aria-current="page" style={{"display":"block","padding":"16px 0","borderBottom":"1px solid rgba(254,203,122,0.16)","color":"#fecb7a","textDecoration":"none","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"15px","fontWeight":"800","letterSpacing":"0.06em","textTransform":"uppercase"}}>{"The Chain"}</a>{" "}<a {...dcExt(`${(v.lp) ?? ''}Atlas.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Atlas.dc.html`)} style={{"display":"block","padding":"16px 0","borderBottom":"1px solid rgba(254,203,122,0.16)","color":"#ffffff","textDecoration":"none","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"15px","fontWeight":"800","letterSpacing":"0.06em","textTransform":"uppercase"}}>{"World Atlas"}</a>{" "}<a {...dcExt(`${(v.lp) ?? ''}Search.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Search.dc.html`)} style={{"display":"block","padding":"16px 0","borderBottom":"1px solid rgba(254,203,122,0.16)","color":"#ffffff","textDecoration":"none","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"15px","fontWeight":"800","letterSpacing":"0.06em","textTransform":"uppercase"}}>{"Search"}</a>{" "}<a {...dcExt(`${(v.lp) ?? ''}About.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}About.dc.html`)} style={{"display":"block","padding":"16px 0","borderBottom":"1px solid rgba(254,203,122,0.16)","color":"#ffffff","textDecoration":"none","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"15px","fontWeight":"800","letterSpacing":"0.06em","textTransform":"uppercase"}}>{"About"}</a>{" "}<a {...dcExt("https://www.youtube.com/@BreakTheRoutinePodcast")} href={dcUrl("https://www.youtube.com/@BreakTheRoutinePodcast")} style={{"display":"inline-flex","alignSelf":"flex-start","alignItems":"center","minHeight":"48px","marginTop":"20px","padding":"0 20px","background":"#fecb7a","color":"#000000","textDecoration":"none","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"12px","fontWeight":"800","letterSpacing":"0.04em","textTransform":"uppercase"}}>{"Subscribe on YouTube"}</a>{" "}</div>{" "}</details>{" "}</nav>{" "}</header>{" "}<main style={{"maxWidth":"1440px","margin":"0 auto","boxSizing":"border-box","padding":"48px clamp(16px, 4vw, 56px) 96px","display":"flex","flexDirection":"column","gap":"28px"}}>{" "}<div style={{"display":"flex","flexWrap":"wrap","gap":"16px 64px","alignItems":"flex-end","justifyContent":"space-between"}}>{" "}<div style={{"flex":"1 1 560px","minWidth":"0","display":"flex","flexDirection":"column","gap":"12px"}}>{" "}<p style={{"margin":"0","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"12px","fontWeight":"800","letterSpacing":"0.12em","color":"#fecb7a"}}>{"THE CHAIN"}</p>{" "}<h1 style={{"margin":"0","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"clamp(28px, 3.6vw, 52px)","fontWeight":"800","lineHeight":"1.04","textWrap":"balance"}}>{"One question, passed from guest to guest"}</h1>{" "}</div>{" "}<p style={{"margin":"0","flex":"0 1 420px","minWidth":"0","color":"#c9b8a6"}}>{"Every guest records a question for the next one, without knowing who it will be. Walk the chain link by link, or jump straight to a guest."}</p>{" "}</div>{" "}<div style={{"display":"flex","flexWrap":"wrap","alignItems":"center","justifyContent":"space-between","gap":"14px 24px","paddingTop":"8px"}}>{" "}<div style={{"display":"flex","alignItems":"baseline","gap":"14px","minWidth":"0","flexWrap":"wrap"}}>{" "}<span style={{"fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"12px","fontWeight":"800","letterSpacing":"0.12em","color":"#fecb7a","whiteSpace":"nowrap"}}>{"LINK "}{v.nav?.pos}{" / "}{v.nav?.total}</span>{" "}<span style={{"color":"#c9b8a6","fontSize":"15px"}}>{v.nav?.from}{" → "}{v.nav?.to}</span>{" "}</div>{" "}<div style={{"display":"flex","alignItems":"center","gap":"8px","flex":"0 1 auto"}}>{" "}<div style={{"position":"relative","flex":"1 1 220px","minWidth":"0"}}>{" "}<label htmlFor="chainq" style={{"position":"absolute","width":"1px","height":"1px","overflow":"hidden","clip":"rect(0 0 0 0)","whiteSpace":"nowrap"}}>{"Find a guest in the chain"}</label>{" "}<input id="chainq" type="search" value={v.q} onChange={v.onQ} placeholder="Find a guest" autoComplete="off" style={{"width":"100%","minWidth":"0","height":"48px","boxSizing":"border-box","padding":"0 16px","background":"#0e0705","border":"1px solid rgba(254,203,122,0.35)","borderRadius":"0","color":"#ffffff","font":"inherit","fontSize":"15px"}} />{" "}{v.hasResults ? (<>{" "}<div role="listbox" aria-label="Guests" style={{"position":"absolute","left":"0","right":"0","top":"calc(100% + 4px)","zIndex":"30","maxHeight":"300px","overflowY":"auto","background":"#110906","border":"1px solid rgba(254,203,122,0.35)","boxShadow":"0 18px 40px rgba(0,0,0,0.5)"}}>{" "}{(v.results || []).map((r, $index) => (<React.Fragment key={$index}>{" "}<button type="button" onClick={r?.go} style={{"display":"flex","alignItems":"center","justifyContent":"space-between","gap":"12px","width":"100%","minHeight":"48px","padding":"0 16px","background":"transparent","border":"0","borderBottom":"1px solid rgba(254,203,122,0.16)","borderRadius":"0","color":"#ffffff","font":"inherit","fontSize":"15px","textAlign":"left","cursor":"pointer"}}><span>{r?.name}</span><span style={{"fontSize":"13px","color":"#c9b8a6"}}>{r?.label}</span></button>{" "}</React.Fragment>))}{" "}</div>{" "}</>) : null}{" "}</div>{" "}<button type="button" onClick={v.prev} aria-label="Previous link" style={{"display":"grid","placeItems":"center","flex":"none","width":"48px","height":"48px","padding":"0","background":"transparent","border":"1px solid rgba(254,203,122,0.55)","borderRadius":"0","color":"#fecb7a","cursor":"pointer"}}><svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="square"><path d="M15 5l-7 7 7 7"></path></svg></button>{" "}<button type="button" onClick={v.next} aria-label="Next link" style={{"display":"grid","placeItems":"center","flex":"none","width":"48px","height":"48px","padding":"0","background":"#fecb7a","border":"1px solid #fecb7a","borderRadius":"0","color":"#000000","cursor":"pointer"}}><svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="square"><path d="M9 5l7 7-7 7"></path></svg></button>{" "}</div>{" "}</div>{" "}<div style={{"position":"relative","borderTop":"1px solid rgba(254,203,122,0.16)","borderBottom":"1px solid rgba(254,203,122,0.16)"}}>{" "}<ol ref={v.stripRef} aria-label="Guests in order" className="chain-strip" onScroll={v.onStrip} style={{"listStyle":"none","margin":"0","padding":"22px 48px","display":"flex","alignItems":"flex-start","overflowX":"auto","scrollBehavior":"smooth","scrollbarWidth":"none"}}>{" "}{(v.nodes || []).map((n, $index) => (<React.Fragment key={$index}>{" "}<li style={{"display":"flex","alignItems":"flex-start","flex":"none"}}>{" "}<button type="button" onClick={n?.pick} aria-pressed={n?.pressed} aria-label={n?.aria} style={{"display":"flex","flexDirection":"column","alignItems":"center","gap":"8px","width":"72px","padding":"0","background":"transparent","border":"0","borderRadius":"0","color":"#ffffff","font":"inherit","cursor":"pointer"}}>{" "}<span style={css(n?.boxStyle)}>{n?.initials}</span>{" "}<span style={css(n?.nameStyle)}>{n?.first}</span>{" "}</button>{" "}{n?.hasNext ? (<>{" "}<span aria-hidden="true" style={css(n?.lineStyle)}></span>{" "}</>) : null}{" "}</li>{" "}</React.Fragment>))}{" "}</ol>{" "}<div aria-hidden="true" style={{"position":"absolute","left":"0","top":"0","bottom":"0","width":"64px","background":"linear-gradient(90deg, #080403 35%, rgba(8,4,3,0) 100%)","pointerEvents":"none"}}></div>{" "}{v.canL ? (<>{" "}<div style={{"position":"absolute","left":"6px","top":"32px","pointerEvents":"none"}}><button type="button" tabIndex="-1" onClick={v.scrollL} aria-label="Scroll back through the guests" style={{"display":"grid","placeItems":"center","width":"36px","height":"36px","padding":"0","background":"#080403","border":"1px solid rgba(254,203,122,0.7)","borderRadius":"0","color":"#fecb7a","cursor":"pointer","pointerEvents":"auto","animation":"chArr .25s ease both"}}><svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="square"><path d="M15 5l-7 7 7 7"></path></svg></button></div>{" "}</>) : null}{" "}<div aria-hidden="true" style={{"position":"absolute","right":"0","top":"0","bottom":"0","width":"64px","background":"linear-gradient(270deg, #080403 35%, rgba(8,4,3,0) 100%)","pointerEvents":"none"}}></div>{" "}{v.canR ? (<>{" "}<div style={{"position":"absolute","right":"6px","top":"32px","pointerEvents":"none"}}><button type="button" tabIndex="-1" onClick={v.scrollR} aria-label="Scroll forward through the guests" style={{"display":"grid","placeItems":"center","width":"36px","height":"36px","padding":"0","background":"#080403","border":"1px solid rgba(254,203,122,0.7)","borderRadius":"0","color":"#fecb7a","cursor":"pointer","pointerEvents":"auto","animation":"chArr .25s ease both"}}><svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="square"><path d="M9 5l7 7-7 7"></path></svg></button></div>{" "}</>) : null}{" "}</div>{" "}<section aria-live="polite" aria-label="Selected link" style={{"display":"grid","gridTemplateColumns":"repeat(auto-fit, minmax(min(100%, 440px), 1fr))","gap":"20px"}}>{" "}<div style={{"position":"relative","overflow":"hidden","boxSizing":"border-box","minHeight":"100%","padding":"clamp(24px, 3.4vw, 48px)","background":"#110906","border":"1px solid rgba(254,203,122,0.25)","display":"flex","flexDirection":"column","justifyContent":"space-between","gap":"32px"}}>{" "}<div aria-hidden="true" style={{"position":"absolute","inset":"0","background":"linear-gradient(180deg, rgba(0,0,0,0) 45%, rgba(159,137,69,0.1) 72%, rgba(223,191,100,0.28) 100%)","pointerEvents":"none"}}></div>{" "}<div style={{"position":"relative","display":"flex","flexWrap":"wrap","alignItems":"center","gap":"12px 16px"}}>{" "}<span style={{"display":"flex","alignItems":"center","gap":"10px"}}><span style={{"display":"grid","placeItems":"center","width":"40px","height":"40px","border":"1px solid rgba(254,203,122,0.5)","color":"#fecb7a","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"12px","fontWeight":"800"}}>{v.sel?.fromIni}</span><span style={{"display":"flex","flexDirection":"column"}}><span style={{"fontSize":"12px","color":"#c9b8a6"}}>{"Asked by"}</span><span style={{"fontWeight":"600"}}>{v.sel?.from}</span></span></span>{" "}<span aria-hidden="true" style={{"color":"#fecb7a","fontSize":"20px"}}>{"→"}</span>{" "}<span style={{"display":"flex","alignItems":"center","gap":"10px"}}><span style={{"display":"grid","placeItems":"center","width":"40px","height":"40px","background":"#fecb7a","color":"#000000","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"12px","fontWeight":"800"}}>{v.sel?.toIni}</span><span style={{"display":"flex","flexDirection":"column"}}><span style={{"fontSize":"12px","color":"#c9b8a6"}}>{"For"}</span><span style={{"fontWeight":"600"}}>{v.sel?.to}</span></span></span>{" "}</div>{" "}<div style={{"position":"relative","display":"flex","flexDirection":"column","gap":"12px"}}>{" "}<p style={{"margin":"0","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"11px","fontWeight":"800","letterSpacing":"0.12em","color":"#fecb7a"}}>{v.sel?.kind}</p>{" "}<p style={{"margin":"0","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"clamp(22px, 2.4vw, 36px)","fontWeight":"800","lineHeight":"1.16","textWrap":"balance"}}><span style={{"color":"#fecb7a"}}>{v.sel?.openQ}</span>{v.sel?.text}<span style={{"color":"#fecb7a"}}>{v.sel?.closeQ}</span></p>{" "}</div>{" "}</div>{" "}<div style={{"display":"flex","flexDirection":"column","gap":"10px","minWidth":"0"}}>{" "}{v.sel?.hasAnswer ? (<>{" "}<a {...dcExt(v.sel?.answerUrl)} href={dcUrl(v.sel?.answerUrl)} aria-label={v.sel?.playAria} style={{"position":"relative","display":"block","width":"100%","aspectRatio":"16 / 9","overflow":"hidden","background":"#000000","border":"1px solid rgba(254,203,122,0.25)"}}>{" "}<img src={dcUrl(v.sel?.thumb)} alt="" style={{"position":"absolute","inset":"0","width":"100%","height":"100%","maxWidth":"none","objectFit":"cover"}} />{" "}<span aria-hidden="true" style={{"position":"absolute","inset":"0","background":"rgba(8,4,3,0.3)"}}></span>{" "}<span aria-hidden="true" style={{"position":"absolute","left":"50%","top":"50%","transform":"translate(-50%, -50%)","display":"grid","placeItems":"center","width":"80px","height":"80px","background":"#fecb7a"}}><svg width="28" height="28" viewBox="0 0 18 18"><path d="M5 2.5 L15.5 9 L5 15.5 Z" fill="#000000"></path></svg></span>{" "}<span style={{"position":"absolute","left":"0","right":"0","bottom":"0","display":"flex","alignItems":"center","gap":"12px","padding":"12px 16px","background":"linear-gradient(180deg, rgba(8,4,3,0) 0%, rgba(8,4,3,0.9) 100%)","color":"#ffffff","fontSize":"14px"}}><span style={{"padding":"3px 8px","background":"#fecb7a","color":"#000000","fontWeight":"700","fontVariantNumeric":"tabular-nums"}}>{v.sel?.time}</span><span>{v.sel?.answerCaption}</span></span>{" "}</a>{" "}</>) : null}{" "}{v.sel?.open ? (<>{" "}<div style={{"display":"flex","flexDirection":"column","justifyContent":"center","gap":"12px","width":"100%","aspectRatio":"16 / 9","boxSizing":"border-box","padding":"32px","border":"2px dashed #fecb7a","background":"#0e0705"}}>{" "}<span style={{"fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"14px","fontWeight":"800","color":"#fecb7a"}}>{"STILL OPEN"}</span>{" "}<span style={{"color":"#e8ddd1","maxWidth":"460px"}}>{v.sel?.openText}</span>{" "}</div>{" "}</>) : null}{" "}<div style={{"display":"grid","gridTemplateColumns":"1fr 1fr","gap":"10px"}}>{" "}<button type="button" onClick={v.prev} style={css(v.ctx?.prevStyle)}><span style={{"fontSize":"12px","color":"#c9b8a6"}}>{"← "}{v.ctx?.prevLabel}</span><span style={{"fontSize":"14px","fontWeight":"600","lineHeight":"1.35"}}>{v.ctx?.prevText}</span></button>{" "}<button type="button" onClick={v.next} style={css(v.ctx?.nextStyle)}><span style={{"fontSize":"12px","color":"#c9b8a6"}}>{v.ctx?.nextLabel}{" →"}</span><span style={{"fontSize":"14px","fontWeight":"600","lineHeight":"1.35"}}>{v.ctx?.nextText}</span></button>{" "}</div>{" "}</div>{" "}</section>{" "}<details className="chain-all" style={{"borderTop":"1px solid rgba(254,203,122,0.16)","paddingTop":"8px"}}>{" "}<summary style={{"display":"flex","alignItems":"center","justifyContent":"space-between","gap":"12px","minHeight":"56px","cursor":"pointer","listStyle":"none","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"13px","fontWeight":"800","letterSpacing":"0.06em"}}><span>{"BROWSE ALL "}{v.nav?.total}{" QUESTIONS"}</span><span aria-hidden="true" style={{"color":"#fecb7a","fontSize":"22px","lineHeight":"1"}}>{"+"}</span></summary>{" "}<div style={{"display":"grid","gridTemplateColumns":"repeat(auto-fill, minmax(min(100%, 300px), 1fr))","gap":"8px","padding":"8px 0 16px"}}>{" "}{(v.links || []).map((l, $index) => (<React.Fragment key={$index}>{" "}<button type="button" onClick={l?.pick} aria-pressed={l?.pressed} style={css(l?.cardStyle)}><span style={{"fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"10px","fontWeight":"800","letterSpacing":"0.08em","opacity":"0.8"}}>{l?.num}{" · "}{l?.fromShort}{" → "}{l?.toShort}</span><span style={{"fontSize":"14px","fontWeight":"600","lineHeight":"1.35","display":"-webkit-box","WebkitLineClamp":"2","WebkitBoxOrient":"vertical","overflow":"hidden"}}>{l?.text}</span></button>{" "}</React.Fragment>))}{" "}</div>{" "}</details>{" "}</main>{" "}<footer style={{"background":"#080403"}}>{" "}<div style={{"maxWidth":"1440px","margin":"0 auto","boxSizing":"border-box","padding":"72px clamp(16px, 4vw, 56px) 40px","display":"flex","flexDirection":"column","gap":"56px"}}>{" "}<div style={{"display":"flex","flexWrap":"wrap","gap":"40px 72px","justifyContent":"space-between"}}>{" "}<img src={dcUrl("/_blob/11f81f408479a20d47ba1e740c14afea")} alt="Break the Routine" style={{"width":"min(360px, 100%)","height":"auto","alignSelf":"flex-start"}} />{" "}<div style={{"display":"flex","flexWrap":"wrap","gap":"32px 72px"}}>{" "}<div style={{"display":"flex","flexDirection":"column","gap":"2px"}}>{" "}<p style={{"margin":"0 0 8px","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"11px","fontWeight":"800","letterSpacing":"0.12em","color":"#fecb7a"}}>{"LISTEN"}</p>{" "}<a {...dcExt("https://www.youtube.com/@BreakTheRoutinePodcast")} href={dcUrl("https://www.youtube.com/@BreakTheRoutinePodcast")} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"YouTube"}</a>{" "}<a {...dcExt("https://open.spotify.com/playlist/75ezrU9QqXelJ7TwSuAT6f")} href={dcUrl("https://open.spotify.com/playlist/75ezrU9QqXelJ7TwSuAT6f")} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"Spotify playlist"}</a>{" "}<a {...dcExt("https://podcasts.apple.com/us/podcast/break-the-routine/id6789345225")} href={dcUrl("https://podcasts.apple.com/us/podcast/break-the-routine/id6789345225")} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"Apple Podcasts"}</a>{" "}<a {...dcExt("https://www.instagram.com/breaktheroutinepodcast/")} href={dcUrl("https://www.instagram.com/breaktheroutinepodcast/")} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"Instagram"}</a>{" "}<a {...dcExt("https://www.tiktok.com/@breaktheroutinepodcast")} href={dcUrl("https://www.tiktok.com/@breaktheroutinepodcast")} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"TikTok"}</a>{" "}</div>{" "}<div style={{"display":"flex","flexDirection":"column","gap":"2px"}}>{" "}<p style={{"margin":"0 0 8px","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"11px","fontWeight":"800","letterSpacing":"0.12em","color":"#fecb7a"}}>{"THE SHOW"}</p>{" "}<a {...dcExt(`${(v.lp) ?? ''}Episodes.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Episodes.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"Episodes"}</a>{" "}<a {...dcExt(`${(v.lp) ?? ''}Chain.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Chain.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"The Chain"}</a>{" "}<a {...dcExt(`${(v.lp) ?? ''}Atlas.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Atlas.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"World Atlas"}</a>{" "}<a {...dcExt(`${(v.lp) ?? ''}Search.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Search.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"Search"}</a>{" "}</div>{" "}<div style={{"display":"flex","flexDirection":"column","gap":"2px"}}>{" "}<p style={{"margin":"0 0 8px","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"11px","fontWeight":"800","letterSpacing":"0.12em","color":"#fecb7a"}}>{"WORK WITH US"}</p>{" "}<a {...dcExt(`${(v.lp) ?? ''}About.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}About.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"Be a guest"}</a>{" "}<a {...dcExt(`${(v.lp) ?? ''}About.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}About.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"Partners"}</a>{" "}<p style={{"margin":"0","padding":"6px 0","color":"#c9b8a6"}}>{"breaktheroutine@protonmail.com"}</p>{" "}</div>{" "}</div>{" "}</div>{" "}<p style={{"margin":"0","paddingTop":"24px","borderTop":"1px solid rgba(254,203,122,0.16)","fontSize":"14px","color":"#a8998b"}}>{"A Dance United & Oti Marius Dance Studio Production · © 2026 Break The Routine"}</p>{" "}</div>{" "}</footer>{" "}</div>{" "}</>);
};

export default Component;
