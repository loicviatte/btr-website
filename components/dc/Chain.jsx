'use client';
// GENERATED from design/Chain.dc.html by tools/compile.mjs. Edit the design file, then run npm run compile.
import React from 'react';
import { DCLogic, css, dcUrl } from '../../lib/dc';


class Component extends DCLogic {
  constructor(props) {
    super(props);
    this.state = { picked: 9 };
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
    const nodes = guests.map((g, i) => {
      const isNext = i === guests.length - 1;
      const active = i === picked || i === picked + 1;
      let box = 'display: grid; place-items: center; flex: none; width: 56px; height: 56px; box-sizing: border-box; font-size: 14px; ' + mono;
      if (isNext) box += ' border: 2px dashed #fecb7a; color: #fecb7a; font-size: 22px;';
      else if (active) box += ' background: #fecb7a; color: #000000;';
      else box += ' border: 1px solid rgba(254,203,122,0.4); color: #c9b8a6;';
      const lineActive = i === picked;
      const openLine = i === guests.length - 2;
      let line = 'display: block; width: 32px; height: 0; margin-right: 14px;';
      line += openLine ? ' border-top: 2px dashed rgba(254,203,122,0.8);' : (lineActive ? ' border-top: 3px solid #fecb7a;' : ' border-top: 2px solid rgba(254,203,122,0.35);');
      const target = Math.max(0, i - 1);
      return {
        ...g,
        boxStyle: box + ' transition: transform 120ms ease;',
        lineStyle: line,
        hasNext: !isNext,
        pressed: active ? 'true' : 'false',
        aria: i === 0 ? g.name + ': show the question she asked' : (isNext ? 'Show the question still open' : g.name + ': show the question they answered'),
        pick: () => this.setState({ picked: target })
      };
    });
    const links = qs.map((x, i) => {
      const sel = i === picked;
      const open = i === qs.length - 1;
      let card = 'display: flex; flex-direction: column; gap: 8px; width: 100%; min-height: 44px; box-sizing: border-box; padding: 18px 20px; text-align: left; border-radius: 0; cursor: pointer; font: inherit;';
      card += sel ? ' background: #fecb7a; color: #000000; border: 1px solid #fecb7a;' : ' background: #0e0705; color: #ffffff; border: 1px solid rgba(254,203,122,0.22);';
      if (open && !sel) card += ' border-style: dashed; border-color: rgba(254,203,122,0.7);';
      return {
        ...x,
        fromShort: guests[i].initials,
        toShort: guests[i + 1].initials,
        status: open ? 'OPEN' : (x.pending ? 'PART 2 SOON' : 'ANSWERED'),
        pressed: sel ? 'true' : 'false',
        cardStyle: card,
        pick: () => this.setState({ picked: i })
      };
    });
    const s = qs[picked];
    const isOpen = picked === qs.length - 1;
    const from = guests[picked], to = guests[picked + 1];
    const isQ = s.kind === 'QUESTION';
    return { lp: this.props.lp ?? '',
      nodes,
      links,
      sel: {
        text: s.text,
        kind: s.kind,
        openQ: isQ ? '“' : '',
        closeQ: isQ ? '”' : '',
        from: from.name,
        to: to.name,
        hasAnswer: !isOpen && !s.pending,
        answerUrl: isOpen || s.pending ? '' : yt(to.vid, s.ans),
        thumb: to.vid ? '/_blob/' + thumbs[to.vid] : '',
        time: s.ans ? fmt(s.ans) : '',
        toFirst: to.name.split(' ')[0],
        answerCaption: to.name + '’s answer',
        playAria: 'Play ' + to.name + '’s answer from ' + (s.ans ? fmt(s.ans) : 'the start'),
        open: isOpen || !!s.pending,
        openText: s.pending ? 'Oti hears Leila’s question in part 2 of her episode, out next week.' : 'Oti records her question for the next guest in part 2. It goes to the guest after her.'
      }
    };
  }
}

Component.prototype.render = function render() {
  const v = this.renderVals() || {};
  return (<>{" "}{" "}<div style={{"background":"#080403","color":"#ffffff","fontFamily":"'Archivo', 'Helvetica Neue', Arial, sans-serif","fontStretch":"108%","fontSize":"17px","lineHeight":"1.55"}}>{" "}<header style={{"position":"sticky","top":"0","zIndex":"50","background":"rgba(8,4,3,0.92)","WebkitBackdropFilter":"blur(12px)","backdropFilter":"blur(12px)","borderBottom":"1px solid rgba(254,203,122,0.16)"}}>{" "}<nav aria-label="Main" style={{"maxWidth":"1440px","margin":"0 auto","boxSizing":"border-box","padding":"16px clamp(16px, 4vw, 56px)","display":"flex","flexWrap":"wrap","alignItems":"center","justifyContent":"space-between","gap":"12px 32px"}}>{" "}<a href={dcUrl(`${(v.lp) ?? ''}Main.dc.html`)} aria-label="Break The Routine, home" style={{"display":"block","lineHeight":"0"}}><img src={dcUrl("/_blob/745152d7135187f4378802fc563253b5")} alt="BTR, The Dancesport Podcast" style={{"width":"104px","height":"auto","display":"block"}} /></a>{" "}<div className="btr-links" style={{"display":"flex","flexWrap":"wrap","alignItems":"center","gap":"0 26px","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"12px","fontWeight":"800","letterSpacing":"0.06em","textTransform":"uppercase"}}>{" "}<a href={dcUrl(`${(v.lp) ?? ''}Episodes.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"14px 0"}}>{"Episodes"}</a>{" "}<a href={dcUrl(`${(v.lp) ?? ''}Chain.dc.html`)} aria-current="page" style={{"color":"#fecb7a","textDecoration":"none","padding":"14px 0","borderBottom":"2px solid #fecb7a"}}>{"The Chain"}</a>{" "}<a href={dcUrl(`${(v.lp) ?? ''}Atlas.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"14px 0"}}>{"World Atlas"}</a>{" "}<a href={dcUrl(`${(v.lp) ?? ''}Search.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"14px 0"}}>{"Search"}</a>{" "}<a href={dcUrl(`${(v.lp) ?? ''}About.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"14px 0"}}>{"About"}</a>{" "}</div>{" "}<a className="btr-sub" href={dcUrl("https://www.youtube.com/@BreakTheRoutinePodcast")} style={{"display":"inline-flex","alignItems":"center","minHeight":"44px","boxSizing":"border-box","padding":"0 18px","background":"#fecb7a","color":"#000000","textDecoration":"none","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"12px","fontWeight":"800","letterSpacing":"0.04em","textTransform":"uppercase"}}>{"Subscribe"}</a>{" "}<details className="btr-burger" style={{"position":"static"}}>{" "}<summary className="btr-burger-btn" aria-label="Menu" style={{"display":"grid","placeItems":"center","width":"48px","height":"48px","boxSizing":"border-box","border":"1px solid rgba(254,203,122,0.55)","color":"#fecb7a","cursor":"pointer"}}>{" "}<svg className="btr-burger-open" aria-hidden="true" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square"><path d="M2 5h16M2 10h16M2 15h16"></path></svg>{" "}<svg className="btr-burger-close" aria-hidden="true" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square"><path d="M4 4l12 12M16 4L4 16"></path></svg>{" "}</summary>{" "}<div style={{"position":"absolute","left":"0","right":"0","top":"100%","boxSizing":"border-box","padding":"8px clamp(16px, 4vw, 56px) 24px","background":"#080403","borderBottom":"1px solid rgba(254,203,122,0.3)","display":"flex","flexDirection":"column"}}>{" "}<a href={dcUrl(`${(v.lp) ?? ''}Episodes.dc.html`)} style={{"display":"block","padding":"16px 0","borderBottom":"1px solid rgba(254,203,122,0.16)","color":"#ffffff","textDecoration":"none","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"15px","fontWeight":"800","letterSpacing":"0.06em","textTransform":"uppercase"}}>{"Episodes"}</a>{" "}<a href={dcUrl(`${(v.lp) ?? ''}Chain.dc.html`)} aria-current="page" style={{"display":"block","padding":"16px 0","borderBottom":"1px solid rgba(254,203,122,0.16)","color":"#fecb7a","textDecoration":"none","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"15px","fontWeight":"800","letterSpacing":"0.06em","textTransform":"uppercase"}}>{"The Chain"}</a>{" "}<a href={dcUrl(`${(v.lp) ?? ''}Atlas.dc.html`)} style={{"display":"block","padding":"16px 0","borderBottom":"1px solid rgba(254,203,122,0.16)","color":"#ffffff","textDecoration":"none","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"15px","fontWeight":"800","letterSpacing":"0.06em","textTransform":"uppercase"}}>{"World Atlas"}</a>{" "}<a href={dcUrl(`${(v.lp) ?? ''}Search.dc.html`)} style={{"display":"block","padding":"16px 0","borderBottom":"1px solid rgba(254,203,122,0.16)","color":"#ffffff","textDecoration":"none","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"15px","fontWeight":"800","letterSpacing":"0.06em","textTransform":"uppercase"}}>{"Search"}</a>{" "}<a href={dcUrl(`${(v.lp) ?? ''}About.dc.html`)} style={{"display":"block","padding":"16px 0","borderBottom":"1px solid rgba(254,203,122,0.16)","color":"#ffffff","textDecoration":"none","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"15px","fontWeight":"800","letterSpacing":"0.06em","textTransform":"uppercase"}}>{"About"}</a>{" "}<a href={dcUrl("https://www.youtube.com/@BreakTheRoutinePodcast")} style={{"display":"inline-flex","alignSelf":"flex-start","alignItems":"center","minHeight":"48px","marginTop":"20px","padding":"0 20px","background":"#fecb7a","color":"#000000","textDecoration":"none","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"12px","fontWeight":"800","letterSpacing":"0.04em","textTransform":"uppercase"}}>{"Subscribe on YouTube"}</a>{" "}</div>{" "}</details>{" "}</nav>{" "}</header>{" "}<main style={{"maxWidth":"1440px","margin":"0 auto","boxSizing":"border-box","padding":"64px clamp(16px, 4vw, 56px) 104px","display":"flex","flexDirection":"column","gap":"56px"}}>{" "}<div style={{"display":"flex","flexWrap":"wrap","gap":"24px 64px","alignItems":"flex-end","justifyContent":"space-between"}}>{" "}<div style={{"flex":"1 1 560px","minWidth":"0","display":"flex","flexDirection":"column","gap":"16px"}}>{" "}<p style={{"margin":"0","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"12px","fontWeight":"800","letterSpacing":"0.12em","color":"#fecb7a"}}>{"THE CHAIN"}</p>{" "}<h1 style={{"margin":"0","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"clamp(30px, 4.4vw, 64px)","fontWeight":"800","lineHeight":"1.02","textWrap":"balance"}}>{"One question, passed from guest to guest"}</h1>{" "}</div>{" "}<p style={{"margin":"0","flex":"0 1 420px","minWidth":"0","color":"#c9b8a6"}}>{"At the end of every episode the guest records a question for the next one, without knowing who it will be. Pick a guest or a question to watch the moment they hear it."}</p>{" "}</div>{" "}<ol className="btr-chain-row" aria-label="Guests in order" style={{"listStyle":"none","margin":"0","padding":"28px 0","display":"flex","flexWrap":"wrap","alignItems":"center","gap":"16px 0","borderTop":"1px solid rgba(254,203,122,0.16)","borderBottom":"1px solid rgba(254,203,122,0.16)"}}>{" "}{(v.nodes || []).map((n, $index) => (<React.Fragment key={$index}>{" "}<li style={{"display":"flex","alignItems":"center"}}>{" "}<button type="button" onClick={n?.pick} aria-pressed={n?.pressed} aria-label={n?.aria} style={{"display":"flex","alignItems":"center","gap":"12px","marginRight":"14px","padding":"0","background":"transparent","border":"0","borderRadius":"0","color":"#ffffff","font":"inherit","textAlign":"left","cursor":"pointer"}}>{" "}<span style={css(n?.boxStyle)}>{n?.initials}</span>{" "}<span style={{"display":"flex","flexDirection":"column","gap":"2px","minWidth":"0"}}>{" "}<span style={{"fontSize":"13px","color":"#c9b8a6"}}>{n?.label}</span>{" "}<span style={{"fontWeight":"600","fontSize":"15px","whiteSpace":"nowrap"}}>{n?.name}</span>{" "}</span>{" "}</button>{" "}{n?.hasNext ? (<>{" "}<span aria-hidden="true" style={css(n?.lineStyle)}></span>{" "}</>) : null}{" "}</li>{" "}</React.Fragment>))}{" "}</ol>{" "}<div style={{"display":"flex","flexWrap":"wrap","gap":"40px 56px","alignItems":"flex-start"}}>{" "}<div role="group" aria-label="Links in the chain" style={{"flex":"1 1 360px","minWidth":"0","display":"flex","flexDirection":"column","gap":"10px"}}>{" "}{(v.links || []).map((l, $index) => (<React.Fragment key={$index}>{" "}<button type="button" onClick={l?.pick} aria-pressed={l?.pressed} style={css(l?.cardStyle)}>{" "}<span style={{"display":"flex","justifyContent":"space-between","gap":"12px","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"11px","fontWeight":"800","letterSpacing":"0.08em"}}>{" "}<span>{l?.fromShort}{" → "}{l?.toShort}</span>{" "}<span>{l?.status}</span>{" "}</span>{" "}<span style={{"fontSize":"16px","lineHeight":"1.4","fontWeight":"600"}}>{l?.text}</span>{" "}</button>{" "}</React.Fragment>))}{" "}</div>{" "}<section aria-live="polite" aria-label="Selected link" style={{"flex":"999 1 600px","minWidth":"0","position":"relative","overflow":"hidden","boxSizing":"border-box","padding":"clamp(28px, 4vw, 56px)","background":"#110906","border":"1px solid rgba(254,203,122,0.25)","display":"flex","flexDirection":"column","gap":"32px"}}>{" "}<div aria-hidden="true" style={{"position":"absolute","inset":"0","background":"linear-gradient(180deg, rgba(0,0,0,0) 40%, rgba(159,137,69,0.12) 70%, rgba(223,191,100,0.32) 100%)","pointerEvents":"none"}}></div>{" "}<div style={{"position":"relative","display":"flex","flexWrap":"wrap","gap":"16px 40px"}}>{" "}<div style={{"display":"flex","flexDirection":"column","gap":"2px"}}>{" "}<span style={{"fontSize":"13px","color":"#c9b8a6"}}>{"Asked by"}</span>{" "}<span style={{"fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"18px","fontWeight":"800","color":"#fcdf9a"}}>{v.sel?.from}</span>{" "}</div>{" "}<div style={{"display":"flex","flexDirection":"column","gap":"2px"}}>{" "}<span style={{"fontSize":"13px","color":"#c9b8a6"}}>{"For"}</span>{" "}<span style={{"fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"18px","fontWeight":"800","color":"#fcdf9a"}}>{v.sel?.to}</span>{" "}</div>{" "}</div>{" "}<div style={{"position":"relative","display":"flex","flexDirection":"column","gap":"12px"}}>{" "}<p style={{"margin":"0","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"11px","fontWeight":"800","letterSpacing":"0.12em","color":"#fecb7a"}}>{v.sel?.kind}</p>{" "}<p style={{"margin":"0","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"clamp(24px, 2.8vw, 40px)","fontWeight":"800","lineHeight":"1.15","textWrap":"balance"}}><span style={{"color":"#fecb7a"}}>{v.sel?.openQ}</span>{v.sel?.text}<span style={{"color":"#fecb7a"}}>{v.sel?.closeQ}</span></p>{" "}</div>{" "}{v.sel?.hasAnswer ? (<>{" "}<div style={{"position":"relative","display":"flex","flexDirection":"column","gap":"10px"}}>{" "}<p style={{"margin":"0","fontSize":"14px","color":"#c9b8a6"}}>{v.sel?.answerCaption}</p>{" "}<a href={dcUrl(v.sel?.answerUrl)} aria-label={v.sel?.playAria} style={{"position":"relative","display":"block","width":"100%","maxWidth":"100%","aspectRatio":"16 / 9","overflow":"hidden","background":"#000000"}}>{" "}<img src={dcUrl(v.sel?.thumb)} alt="" style={{"position":"absolute","inset":"0","width":"100%","height":"100%","maxWidth":"none","objectFit":"cover"}} />{" "}<span aria-hidden="true" style={{"position":"absolute","inset":"0","background":"rgba(8,4,3,0.35)"}}></span>{" "}<span aria-hidden="true" style={{"position":"absolute","left":"50%","top":"50%","transform":"translate(-50%, -50%)","display":"grid","placeItems":"center","width":"84px","height":"84px","background":"#fecb7a"}}>{" "}<svg width="30" height="30" viewBox="0 0 18 18"><path d="M5 2.5 L15.5 9 L5 15.5 Z" fill="#000000"></path></svg>{" "}</span>{" "}<span style={{"position":"absolute","left":"0","right":"0","bottom":"0","display":"flex","alignItems":"center","gap":"12px","padding":"12px 16px","background":"linear-gradient(180deg, rgba(8,4,3,0) 0%, rgba(8,4,3,0.9) 100%)","color":"#ffffff","fontSize":"14px"}}>{" "}<span style={{"padding":"3px 8px","background":"#fecb7a","color":"#000000","fontWeight":"700","fontVariantNumeric":"tabular-nums"}}>{v.sel?.time}</span>{" "}<span>{"Plays from the moment "}{v.sel?.toFirst}{" hears the question"}</span>{" "}</span>{" "}</a>{" "}</div>{" "}</>) : null}{" "}{v.sel?.open ? (<>{" "}<div style={{"position":"relative","display":"flex","flexWrap":"wrap","alignItems":"center","gap":"16px 24px","padding":"20px 24px","border":"2px dashed #fecb7a"}}>{" "}<span style={{"fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"14px","fontWeight":"800","color":"#fecb7a"}}>{"STILL OPEN"}</span>{" "}<span style={{"flex":"1 1 260px","minWidth":"0","color":"#e8ddd1"}}>{v.sel?.openText}</span>{" "}</div>{" "}</>) : null}{" "}</section>{" "}</div>{" "}</main>{" "}<footer style={{"background":"#080403"}}>{" "}<div style={{"maxWidth":"1440px","margin":"0 auto","boxSizing":"border-box","padding":"72px clamp(16px, 4vw, 56px) 40px","display":"flex","flexDirection":"column","gap":"56px"}}>{" "}<div style={{"display":"flex","flexWrap":"wrap","gap":"40px 72px","justifyContent":"space-between"}}>{" "}<img src={dcUrl("/_blob/11f81f408479a20d47ba1e740c14afea")} alt="Break the Routine" style={{"width":"min(360px, 100%)","height":"auto","alignSelf":"flex-start"}} />{" "}<div style={{"display":"flex","flexWrap":"wrap","gap":"32px 72px"}}>{" "}<div style={{"display":"flex","flexDirection":"column","gap":"2px"}}>{" "}<p style={{"margin":"0 0 8px","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"11px","fontWeight":"800","letterSpacing":"0.12em","color":"#fecb7a"}}>{"LISTEN"}</p>{" "}<a href={dcUrl("https://www.youtube.com/@BreakTheRoutinePodcast")} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"YouTube"}</a>{" "}<a href={dcUrl("https://open.spotify.com/playlist/75ezrU9QqXelJ7TwSuAT6f")} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"Spotify playlist"}</a>{" "}<a href={dcUrl("https://podcasts.apple.com/us/podcast/break-the-routine/id6789345225")} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"Apple Podcasts"}</a>{" "}<a href={dcUrl("https://www.instagram.com/breaktheroutinepodcast/")} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"Instagram"}</a>{" "}<a href={dcUrl("https://www.tiktok.com/@breaktheroutinepodcast")} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"TikTok"}</a>{" "}</div>{" "}<div style={{"display":"flex","flexDirection":"column","gap":"2px"}}>{" "}<p style={{"margin":"0 0 8px","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"11px","fontWeight":"800","letterSpacing":"0.12em","color":"#fecb7a"}}>{"THE SHOW"}</p>{" "}<a href={dcUrl(`${(v.lp) ?? ''}Episodes.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"Episodes"}</a>{" "}<a href={dcUrl(`${(v.lp) ?? ''}Chain.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"The Chain"}</a>{" "}<a href={dcUrl(`${(v.lp) ?? ''}Atlas.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"World Atlas"}</a>{" "}<a href={dcUrl(`${(v.lp) ?? ''}Search.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"Search"}</a>{" "}</div>{" "}<div style={{"display":"flex","flexDirection":"column","gap":"2px"}}>{" "}<p style={{"margin":"0 0 8px","fontFamily":"'PP Monument Extended', 'Arial Black', sans-serif","fontSize":"11px","fontWeight":"800","letterSpacing":"0.12em","color":"#fecb7a"}}>{"WORK WITH US"}</p>{" "}<a href={dcUrl(`${(v.lp) ?? ''}About.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"Be a guest"}</a>{" "}<a href={dcUrl(`${(v.lp) ?? ''}About.dc.html`)} style={{"color":"#ffffff","textDecoration":"none","padding":"6px 0"}}>{"Partners"}</a>{" "}<p style={{"margin":"0","padding":"6px 0","color":"#c9b8a6"}}>{"breaktheroutine@protonmail.com"}</p>{" "}</div>{" "}</div>{" "}</div>{" "}<p style={{"margin":"0","paddingTop":"24px","borderTop":"1px solid rgba(254,203,122,0.16)","fontSize":"14px","color":"#a8998b"}}>{"A Dance United & Oti Marius Dance Studio Production · © 2026 Break The Routine"}</p>{" "}</div>{" "}</footer>{" "}</div>{" "}</>);
};

export default Component;
