'use client';
import { useEffect, useState } from 'react';

const mono = { fontFamily: "'PP Monument Extended', 'Arial Black', sans-serif", fontWeight: 800 };

export default function Code() {
  const [q, setQ] = useState(null);
  const [copied, setCopied] = useState(false);
  useEffect(() => { setQ(new URLSearchParams(window.location.search)); }, []);
  const code = q?.get('code') || '';
  const err = q?.get('error_description') || q?.get('error') || '';
  const text = code ? `tiktok ${code}` : '';
  return (
    <main style={{ background: '#080403', color: '#fff', minHeight: '100vh', boxSizing: 'border-box', padding: '72px 20px', display: 'flex', justifyContent: 'center' }}>
      <div style={{ maxWidth: 620, width: '100%', display: 'flex', flexDirection: 'column', gap: 18 }}>
        <p style={{ ...mono, margin: 0, fontSize: 12, letterSpacing: '0.12em', color: '#fecb7a' }}>BTR STUDIO · TIKTOK</p>
        {q === null ? null : code ? (
          <>
            <h1 style={{ ...mono, margin: 0, fontSize: 30, lineHeight: 1.1 }}>Almost done</h1>
            <p style={{ margin: 0, color: '#e8ddd1', lineHeight: 1.6 }}>Copy this message and paste it into the BTR Studio bot on Telegram. It works once, for a few minutes.</p>
            <code style={{ display: 'block', wordBreak: 'break-all', background: '#1a1210', border: '1px solid #3a2a20', borderRadius: 10, padding: 16, fontSize: 14 }}>{text}</code>
            <button onClick={() => { navigator.clipboard?.writeText(text).then(() => setCopied(true)); }}
              style={{ ...mono, alignSelf: 'flex-start', background: '#fcdf9a', color: '#080403', border: 0, borderRadius: 999, padding: '12px 22px', fontSize: 13, cursor: 'pointer' }}>
              {copied ? 'Copied' : 'Copy'}
            </button>
          </>
        ) : (
          <>
            <h1 style={{ ...mono, margin: 0, fontSize: 30, lineHeight: 1.1 }}>No code</h1>
            <p style={{ margin: 0, color: '#e8ddd1', lineHeight: 1.6 }}>{err ? `TikTok said: ${err}` : 'Open this page from the TikTok link sent by the bot.'}</p>
          </>
        )}
      </div>
    </main>
  );
}
