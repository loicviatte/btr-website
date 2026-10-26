'use client';
// Plays "moments" in place instead of leaving the site:
//  - YouTube links with a timecode (&t=…): chain answers, World Atlas draws, chapters, transcript, search results
//  - Instagram reels
// Plain links to an episode (no timecode) keep opening YouTube in a new tab.
import { useEffect, useRef, useState } from 'react';

function parse(href) {
  let u;
  try { u = new URL(href, window.location.href); } catch (e) { return null; }
  const host = u.hostname.replace(/^www\./, '').replace(/^m\./, '');
  if (host === 'instagram.com') {
    const m = u.pathname.match(/^\/(reel|p)\/([A-Za-z0-9_-]+)/);
    if (m) return { type: 'ig', id: m[2], href: u.href };
  }
  if (host === 'youtube.com' && u.pathname === '/watch') {
    const id = u.searchParams.get('v');
    const t = u.searchParams.get('t');
    if (id && t) return { type: 'yt', id, start: parseInt(t, 10) || 0, href: u.href };
  }
  if (host === 'youtu.be') {
    const t = u.searchParams.get('t');
    if (t) return { type: 'yt', id: u.pathname.slice(1), start: parseInt(t, 10) || 0, href: u.href };
  }
  return null;
}

export default function MediaLightbox() {
  const [media, setMedia] = useState(null);
  const [shown, setShown] = useState(false);
  const closeRef = useRef(null);
  const lastFocus = useRef(null);

  useEffect(() => {
    const onClick = (e) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const a = e.target.closest && e.target.closest('a[href]');
      if (!a || a.closest('[data-no-embed]')) return;
      const m = parse(a.getAttribute('href'));
      if (!m) return;
      e.preventDefault();
      lastFocus.current = a;
      setMedia(m);
      requestAnimationFrame(() => requestAnimationFrame(() => setShown(true)));
    };
    document.addEventListener('click', onClick, true);
    return () => document.removeEventListener('click', onClick, true);
  }, []);

  useEffect(() => {
    if (!media) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') close(); };
    document.addEventListener('keydown', onKey);
    const prev = document.documentElement.style.overflow;
    document.documentElement.style.overflow = 'hidden';
    setTimeout(() => closeRef.current && closeRef.current.focus(), 50);
    return () => { document.removeEventListener('keydown', onKey); document.documentElement.style.overflow = prev; };
  }, [media]);

  function close() {
    setShown(false);
    setTimeout(() => { setMedia(null); if (lastFocus.current) lastFocus.current.focus(); }, 280);
  }

  if (!media) return null;
  const src = media.type === 'yt'
    ? `https://www.youtube-nocookie.com/embed/${media.id}?start=${media.start}&autoplay=1&rel=0&modestbranding=1&playsinline=1`
    : `https://www.instagram.com/reel/${media.id}/embed/`;

  return (
    <div className={'btr-lb' + (shown ? ' btr-lb-on' : '')} role="dialog" aria-modal="true" aria-label={media.type === 'yt' ? 'Episode player' : 'Instagram reel'} onClick={(e) => { if (e.target === e.currentTarget) close(); }}>
      <div className={'btr-lb-box ' + (media.type === 'yt' ? 'btr-lb-yt' : 'btr-lb-ig')}>
        <div className="btr-lb-frame">
          <iframe
            src={src}
            title={media.type === 'yt' ? 'Break The Routine on YouTube' : 'Break The Routine reel on Instagram'}
            allow="autoplay; encrypted-media; picture-in-picture; fullscreen; clipboard-write"
            allowFullScreen
            loading="eager"
          />
        </div>
        <div className="btr-lb-bar">
          <a href={media.href} target="_blank" rel="noopener noreferrer" data-no-embed="">
            {media.type === 'yt' ? 'Open on YouTube ↗' : 'Open on Instagram ↗'}
          </a>
          <button ref={closeRef} type="button" onClick={close} aria-label="Close player">
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="square"><path d="M4 4l12 12M16 4L4 16" /></svg>
          </button>
        </div>
      </div>
    </div>
  );
}
