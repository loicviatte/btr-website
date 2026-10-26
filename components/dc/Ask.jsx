'use client';
// GENERATED from design/Ask.dc.html by tools/compile.mjs. Edit the design file, then run npm run compile.
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
    this.state = { name: '', ig: '', q: '', ok: true, sent: false, sending: false, error: '', hp: '' };
  }
  renderVals() {
    const s = this.state;
    const count = (s.q || '').length;
    return { motionRef: this._motionRef || (this._motionRef = (el) => { if (el) { this._motionEl = el; btrMotion(el); } else { btrMotionStop(this._motionEl); } }), lp: this.props.lp ?? '',
      name: s.name,
      ig: s.ig,
      q: s.q,
      ok: s.ok,
      count,
      countColor: count > 250 ? '#fecb7a' : '#c9b8a6',
      showForm: !s.sent,
      sent: s.sent,
      onName: (e) => this.setState({ name: e.target.value }),
      onIg: (e) => this.setState({ ig: e.target.value }),
      onQ: (e) => this.setState({ q: e.target.value }),
      onOk: (e) => this.setState({ ok: e.target.checked }),
      sending: s.sending,
      btnText: s.sending ? 'SENDING…' : 'SEND MY QUESTION',
      hasError: !!s.error,
      error: s.error,
      hp: s.hp,
      onHp: (e) => this.setState({ hp: e.target.value }),
      send: (e) => {
        if (e && e.preventDefault) e.preventDefault();
        if (s.sending || !s.name.trim() || !s.q.trim()) return;
        const api = typeof window !== 'undefined' && window.__btrAskApi;
        if (!api) { this.setState({ sent: true }); return; }
        this.setState({ sending: true, error: '' });
        fetch(api, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ name: s.name, ig: s.ig, q: s.q, ok: s.ok, website: s.hp }) })
          .then((r) => r.json().catch(() => ({})).then((j) => ({ ok: r.ok, j })))
          .then(({ ok, j }) => {
            if (ok) this.setState({ sending: false, sent: true });
            else this.setState({ sending: false, error: (j && j.error) || 'Your question could not be sent. Please try again, or send it to us on Instagram @breaktheroutinepodcast.' });
          })
          .catch(() => this.setState({ sending: false, error: 'No connection. Please try again in a moment.' }));
      },
      again: () => this.setState({ q: '', sent: false, error: '' })
    };
  }
}

Component.prototype.render = function render() {
  const v = this.renderVals() || {};
  return (<>{" "}{" "}<div ref={v.motionRef} style={{"background":"#080403","color":"#ffffff","fontFamily":"'Archivo', 'Helvetica Neue', Arial, sans-serif","fontStretch":"108%","fontSize":"17px","lineHeight":"1.55"}}>{" "}<header style={{"position":"sticky","top":"0","zIndex":"50","background":"rgba(8,4,3,0.92)","WebkitBackdropFilter":"blur(12px)","backdropFilter":"blur(12px)","borderBottom":"1px solid rgba(254,203,122,0.16)"}}>{" "}<nav aria-label="Main" style={{"maxWidth":"1440px","margin":"0 auto","boxSizing":"border-box","padding":"16px clamp(16px, 4vw, 56px)","display":"flex","flexWrap":"wrap","alignItems":"center","justifyContent":"space-between","gap":"12px 32px"}}>{" "}<a {...dcExt(`${(v.lp) ?? ''}Main.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Main.dc.html`)} aria-label="Break The Routine, home" style={{"display":"block","lineHeight":"0"}}><img src={dcUrl("/_blob/745152d7135187f4378802fc563253b5")} alt="BTR, The Dancesport Podcast" style={{"width":"104px","height":"auto","display":"block"}} /></a>{" "}<div className="btr-links" style={{"display":"flex","flexWrap":"wrap","alignItems":"center","gap":"0 26px","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"12px","fontWeight":"800","letterSpacing":"0.06em","textTransform":"uppercase"}}>{" "}<a {...dcExt(`${(v.lp) ?? ''}Episodes.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Episodes.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"14px 0"}}>{"Episodes"}</a>{" "}<a {...dcExt(`${(v.lp) ?? ''}Chain.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Chain.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"14px 0"}}>{"The Chain"}</a>{" "}<a {...dcExt(`${(v.lp) ?? ''}Atlas.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Atlas.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"14px 0"}}>{"World Atlas"}</a>{" "}<a {...dcExt(`${(v.lp) ?? ''}Search.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Search.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"14px 0"}}>{"Search"}</a>{" "}<a {...dcExt(`${(v.lp) ?? ''}About.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}About.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"14px 0"}}>{"About"}</a>{" "}</div>{" "}<a className="btr-sub" {...dcExt("https://www.youtube.com/@BreakTheRoutinePodcast")} href={dcUrl("https://www.youtube.com/@BreakTheRoutinePodcast")} style={{"display":"inline-flex","alignItems":"center","minHeight":"44px","boxSizing":"border-box","padding":"0 18px","background":"#fecb7a","color":"#000000","textDecoration":"none","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"12px","fontWeight":"800","letterSpacing":"0.04em","textTransform":"uppercase"}}>{"Subscribe"}</a>{" "}<details className="btr-burger" style={{"position":"static"}}>{" "}<summary className="btr-burger-btn" aria-label="Menu" style={{"display":"grid","placeItems":"center","width":"48px","height":"48px","boxSizing":"border-box","border":"1px solid rgba(254,203,122,0.55)","color":"#fecb7a","cursor":"pointer"}}>{" "}<svg className="btr-burger-open" aria-hidden="true" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square"><path d="M2 5h16M2 10h16M2 15h16"></path></svg>{" "}<svg className="btr-burger-close" aria-hidden="true" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square"><path d="M4 4l12 12M16 4L4 16"></path></svg>{" "}</summary>{" "}<div style={{"position":"absolute","left":"0","right":"0","top":"100%","boxSizing":"border-box","padding":"8px clamp(16px, 4vw, 56px) 24px","background":"#080403","borderBottom":"1px solid rgba(254,203,122,0.3)","display":"flex","flexDirection":"column"}}>{" "}<a {...dcExt(`${(v.lp) ?? ''}Episodes.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Episodes.dc.html`)} style={{"display":"block","padding":"16px 0","borderBottom":"1px solid rgba(254,203,122,0.16)","color":"#ffffff","textDecoration":"none","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"15px","fontWeight":"800","letterSpacing":"0.06em","textTransform":"uppercase"}}>{"Episodes"}</a>{" "}<a {...dcExt(`${(v.lp) ?? ''}Chain.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Chain.dc.html`)} style={{"display":"block","padding":"16px 0","borderBottom":"1px solid rgba(254,203,122,0.16)","color":"#ffffff","textDecoration":"none","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"15px","fontWeight":"800","letterSpacing":"0.06em","textTransform":"uppercase"}}>{"The Chain"}</a>{" "}<a {...dcExt(`${(v.lp) ?? ''}Atlas.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Atlas.dc.html`)} style={{"display":"block","padding":"16px 0","borderBottom":"1px solid rgba(254,203,122,0.16)","color":"#ffffff","textDecoration":"none","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"15px","fontWeight":"800","letterSpacing":"0.06em","textTransform":"uppercase"}}>{"World Atlas"}</a>{" "}<a {...dcExt(`${(v.lp) ?? ''}Search.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Search.dc.html`)} style={{"display":"block","padding":"16px 0","borderBottom":"1px solid rgba(254,203,122,0.16)","color":"#ffffff","textDecoration":"none","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"15px","fontWeight":"800","letterSpacing":"0.06em","textTransform":"uppercase"}}>{"Search"}</a>{" "}<a {...dcExt(`${(v.lp) ?? ''}About.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}About.dc.html`)} style={{"display":"block","padding":"16px 0","borderBottom":"1px solid rgba(254,203,122,0.16)","color":"#ffffff","textDecoration":"none","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"15px","fontWeight":"800","letterSpacing":"0.06em","textTransform":"uppercase"}}>{"About"}</a>{" "}<a {...dcExt("https://www.youtube.com/@BreakTheRoutinePodcast")} href={dcUrl("https://www.youtube.com/@BreakTheRoutinePodcast")} style={{"display":"inline-flex","alignSelf":"flex-start","alignItems":"center","minHeight":"48px","marginTop":"20px","padding":"0 20px","background":"#fecb7a","color":"#000000","textDecoration":"none","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"12px","fontWeight":"800","letterSpacing":"0.04em","textTransform":"uppercase"}}>{"Subscribe on YouTube"}</a>{" "}</div>{" "}</details>{" "}</nav>{" "}</header>{" "}<main style={{"maxWidth":"1440px","margin":"0 auto","boxSizing":"border-box","padding":"64px clamp(16px, 4vw, 56px) 104px","display":"flex","flexWrap":"wrap","gap":"56px 72px","alignItems":"flex-start"}}>{" "}<div style={{"flex":"999 1 560px","minWidth":"0","display":"flex","flexDirection":"column","gap":"36px"}}>{" "}<div style={{"display":"flex","flexDirection":"column","gap":"16px"}}>{" "}<p style={{"margin":"0","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"12px","fontWeight":"800","letterSpacing":"0.12em","color":"#fecb7a"}}>{"ASK THE NEXT GUEST"}</p>{" "}<h1 style={{"margin":"0","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"clamp(30px, 4.2vw, 60px)","fontWeight":"800","lineHeight":"1.02","textWrap":"balance"}}>{"Your question, on the next episode"}</h1>{" "}<p style={{"margin":"0","maxWidth":"600px","color":"#c9b8a6"}}>{"You won't know who the guest is until Tuesday. Marius picks one question from the audience for every episode and reads your name on air."}</p>{" "}</div>{" "}{v.showForm ? (<>{" "}<form onSubmit={v.send} style={{"display":"flex","flexDirection":"column","gap":"22px","padding":"clamp(24px, 3vw, 40px)","background":"#0e0705","border":"1px solid rgba(254,203,122,0.22)"}}>{" "}<div style={{"display":"flex","flexWrap":"wrap","gap":"22px"}}>{" "}<div style={{"flex":"1 1 240px","minWidth":"0","display":"flex","flexDirection":"column","gap":"6px"}}>{" "}<label htmlFor="askname" style={{"fontSize":"15px","fontWeight":"600"}}>{"Your name"}</label>{" "}<input id="askname" type="text" value={v.name} onChange={v.onName} required={true} autoComplete="name" placeholder="First name and surname" style={{"minHeight":"50px","boxSizing":"border-box","padding":"0 14px","background":"#080403","border":"1px solid rgba(254,203,122,0.35)","borderRadius":"0","color":"#ffffff","font":"inherit","fontSize":"16px"}} />{" "}</div>{" "}<div style={{"flex":"1 1 240px","minWidth":"0","display":"flex","flexDirection":"column","gap":"6px"}}>{" "}<label htmlFor="askig" style={{"fontSize":"15px","fontWeight":"600"}}>{"Instagram "}<span style={{"fontWeight":"400","color":"#c9b8a6"}}>{"(optional)"}</span></label>{" "}<input id="askig" type="text" value={v.ig} onChange={v.onIg} placeholder="@yourhandle" style={{"minHeight":"50px","boxSizing":"border-box","padding":"0 14px","background":"#080403","border":"1px solid rgba(254,203,122,0.35)","borderRadius":"0","color":"#ffffff","font":"inherit","fontSize":"16px"}} />{" "}</div>{" "}</div>{" "}<div style={{"display":"flex","flexDirection":"column","gap":"6px"}}>{" "}<div style={{"display":"flex","justifyContent":"space-between","gap":"12px"}}>{" "}<label htmlFor="askq" style={{"fontSize":"15px","fontWeight":"600"}}>{"Your question"}</label>{" "}<span style={css(`font-size: 14px; font-variant-numeric: tabular-nums; color: ${(v.countColor) ?? ''};`)}>{v.count}{" / 280"}</span>{" "}</div>{" "}<textarea id="askq" rows="4" maxLength="280" value={v.q} onChange={v.onQ} required={true} placeholder="Something you have always wanted to ask a judge, a champion or a coach" style={{"boxSizing":"border-box","padding":"14px","background":"#080403","border":"1px solid rgba(254,203,122,0.35)","borderRadius":"0","color":"#ffffff","font":"inherit","fontSize":"17px","lineHeight":"1.5","resize":"vertical"}} />{" "}</div>{" "}<div style={{"display":"flex","alignItems":"flex-start","gap":"12px"}}>{" "}<input id="askok" type="checkbox" checked={v.ok} onChange={v.onOk} style={{"width":"22px","height":"22px","margin":"2px 0 0","accentColor":"#fecb7a","flex":"none"}} />{" "}<label htmlFor="askok" style={{"fontSize":"15px","color":"#e8ddd1"}}>{"Marius can say my name and my handle on the show"}</label>{" "}</div>{" "}<input type="text" name="website" tabIndex="-1" autoComplete="off" aria-hidden="true" value={v.hp} onChange={v.onHp} style={{"position":"absolute","left":"-9999px","width":"1px","height":"1px","opacity":"0"}} />{" "}{v.hasError ? (<>{" "}<p role="alert" style={{"margin":"0","padding":"12px 14px","border":"1px solid #fecb7a","color":"#fecb7a","fontSize":"15px"}}>{v.error}</p>{" "}</>) : null}{" "}<button type="submit" disabled={v.sending} style={{"alignSelf":"flex-start","minHeight":"52px","padding":"0 26px","background":"#fecb7a","border":"0","borderRadius":"0","color":"#000000","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"13px","fontWeight":"800","letterSpacing":"0.04em","cursor":"pointer"}}>{v.btnText}</button>{" "}</form>{" "}</>) : null}{" "}{v.sent ? (<>{" "}<div aria-live="polite" style={{"display":"flex","flexDirection":"column","gap":"16px","padding":"clamp(24px, 3vw, 40px)","background":"#fecb7a","color":"#000000"}}>{" "}<p style={{"margin":"0","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"12px","fontWeight":"800","letterSpacing":"0.12em"}}>{"QUESTION RECEIVED"}</p>{" "}<p style={{"margin":"0","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"clamp(20px, 2vw, 28px)","fontWeight":"800","lineHeight":"1.2"}}>{"“"}{v.q}{"”"}</p>{" "}<p style={{"margin":"0"}}>{"Thanks "}{v.name}{". If Marius picks it, you'll hear your name in the episode. Watch Tuesday's release."}</p>{" "}<button type="button" onClick={v.again} style={{"alignSelf":"flex-start","minHeight":"48px","padding":"0 22px","background":"#080403","border":"0","borderRadius":"0","color":"#ffffff","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"12px","fontWeight":"800","letterSpacing":"0.04em","cursor":"pointer"}}>{"ASK ANOTHER"}</button>{" "}</div>{" "}</>) : null}{" "}</div>{" "}<aside aria-label="Marius on set" style={{"flex":"1 1 380px","minWidth":"0","display":"flex","flexDirection":"column","gap":"24px"}}>{" "}<div style={{"position":"relative","aspectRatio":"4 / 3","maxWidth":"100%","overflow":"hidden"}}>{" "}<img src={dcUrl("/_blob/9d82d474bebf50fec8071ef445720e4f")} alt="Marius Iepure reading from the show tablet on set" style={{"position":"absolute","inset":"0","width":"100%","height":"100%","objectFit":"cover","objectPosition":"65% center"}} />{" "}<div aria-hidden="true" style={{"position":"absolute","inset":"0","background":"linear-gradient(180deg, rgba(0,0,0,0) 40%, rgba(199,171,88,0.4) 80%, rgba(223,191,100,0.8) 100%)"}}></div>{" "}<p style={{"position":"absolute","left":"20px","right":"20px","bottom":"18px","margin":"0","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"15px","fontWeight":"800","lineHeight":"1.25"}}>{"Read out on air, every episode"}</p>{" "}</div>{" "}</aside>{" "}</main>{" "}<footer style={{"background":"#080403"}}>{" "}<div style={{"maxWidth":"1440px","margin":"0 auto","boxSizing":"border-box","padding":"72px clamp(16px, 4vw, 56px) 40px","display":"flex","flexDirection":"column","gap":"56px"}}>{" "}<div style={{"display":"flex","flexWrap":"wrap","gap":"40px 72px","justifyContent":"space-between"}}>{" "}<img src={dcUrl("/_blob/11f81f408479a20d47ba1e740c14afea")} alt="Break the Routine" style={{"width":"min(360px, 100%)","height":"auto","alignSelf":"flex-start"}} />{" "}<div style={{"display":"flex","flexWrap":"wrap","gap":"32px 72px"}}>{" "}<div style={{"display":"flex","flexDirection":"column","gap":"2px"}}>{" "}<p style={{"margin":"0 0 8px","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"11px","fontWeight":"800","letterSpacing":"0.12em","color":"#fecb7a"}}>{"LISTEN"}</p>{" "}<a {...dcExt("https://www.youtube.com/@BreakTheRoutinePodcast")} href={dcUrl("https://www.youtube.com/@BreakTheRoutinePodcast")} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"YouTube"}</a>{" "}<a {...dcExt("https://open.spotify.com/playlist/75ezrU9QqXelJ7TwSuAT6f")} href={dcUrl("https://open.spotify.com/playlist/75ezrU9QqXelJ7TwSuAT6f")} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"Spotify playlist"}</a>{" "}<a {...dcExt("https://podcasts.apple.com/us/podcast/break-the-routine/id6789345225")} href={dcUrl("https://podcasts.apple.com/us/podcast/break-the-routine/id6789345225")} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"Apple Podcasts"}</a>{" "}<a {...dcExt("https://www.instagram.com/breaktheroutinepodcast/")} href={dcUrl("https://www.instagram.com/breaktheroutinepodcast/")} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"Instagram"}</a>{" "}<a {...dcExt("https://www.tiktok.com/@breaktheroutinepodcast")} href={dcUrl("https://www.tiktok.com/@breaktheroutinepodcast")} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"TikTok"}</a>{" "}</div>{" "}<div style={{"display":"flex","flexDirection":"column","gap":"2px"}}>{" "}<p style={{"margin":"0 0 8px","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"11px","fontWeight":"800","letterSpacing":"0.12em","color":"#fecb7a"}}>{"THE SHOW"}</p>{" "}<a {...dcExt(`${(v.lp) ?? ''}Episodes.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Episodes.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"Episodes"}</a>{" "}<a {...dcExt(`${(v.lp) ?? ''}Chain.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Chain.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"The Chain"}</a>{" "}<a {...dcExt(`${(v.lp) ?? ''}Atlas.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Atlas.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"World Atlas"}</a>{" "}<a {...dcExt(`${(v.lp) ?? ''}Search.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}Search.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"Search"}</a>{" "}</div>{" "}<div style={{"display":"flex","flexDirection":"column","gap":"2px"}}>{" "}<p style={{"margin":"0 0 8px","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"11px","fontWeight":"800","letterSpacing":"0.12em","color":"#fecb7a"}}>{"WORK WITH US"}</p>{" "}<a {...dcExt(`${(v.lp) ?? ''}About.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}About.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"Be a guest"}</a>{" "}<a {...dcExt(`${(v.lp) ?? ''}About.dc.html`)} href={dcUrl(`${(v.lp) ?? ''}About.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"Partners"}</a>{" "}<p style={{"margin":"0","padding":"6px 0","color":"#c9b8a6"}}>{"breaktheroutine@protonmail.com"}</p>{" "}</div>{" "}</div>{" "}</div>{" "}<p style={{"margin":"0","paddingTop":"24px","borderTop":"1px solid rgba(254,203,122,0.16)","fontSize":"14px","color":"#a8998b"}}>{"A Dance United & Oti Marius Dance Studio Production · © 2026 Break The Routine"}</p>{" "}</div>{" "}</footer>{" "}</div>{" "}</>);
};

export default Component;
