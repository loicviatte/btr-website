export const metadata = { title: 'Privacy · Break The Routine' };

const mono = { fontFamily: "'PP Monument Extended', 'Arial Black', sans-serif", fontWeight: 800 };
const h2 = { ...mono, margin: '28px 0 0', fontSize: 18 };
const p = { margin: 0, color: '#e8ddd1', lineHeight: 1.6 };

export default function Privacy() {
  return (
    <main style={{ background: '#080403', color: '#ffffff', minHeight: '100vh', boxSizing: 'border-box', padding: '72px 20px 96px' }}>
      <div style={{ maxWidth: 720, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 14 }}>
        <a href="/" style={{ ...mono, fontSize: 12, letterSpacing: '0.12em', color: '#fecb7a', textDecoration: 'none' }}>← BREAK THE ROUTINE</a>
        <h1 style={{ ...mono, margin: '12px 0 0', fontSize: 'clamp(28px, 4vw, 44px)', lineHeight: 1.08 }}>Privacy</h1>
        <p style={{ ...p, color: '#c9b8a6' }}>Last updated 26 October 2026.</p>

        <h2 style={h2}>Who we are</h2>
        <p style={p}>Break The Routine is a DanceSport podcast hosted by Marius Iepure, a Dance United &amp; Oti Marius Dance Studio production. This page explains what happens to your data on breaktheroutinepodcast.com. Contact: breaktheroutine@protonmail.com.</p>

        <h2 style={h2}>What we collect</h2>
        <p style={p}>Only what you send us. If you use the “Ask the next guest” form, we receive your name, your Instagram handle if you give it, your question and whether Marius may say your name on the show. We keep these in a private Google Sheet so the team can pick questions for upcoming episodes. We don’t sell or share them, and we delete them on request.</p>
        <p style={p}>When you search the episodes, your search words may be sent to Anthropic (the company behind Claude) to rank the results by meaning. They are not stored by us and are not linked to you.</p>

        <h2 style={h2}>Cookies and tracking</h2>
        <p style={p}>The site itself sets no advertising or analytics cookies. It remembers in your browser, for the current visit only, that you have seen the intro animation.</p>
        <p style={p}>Videos play through YouTube (youtube-nocookie.com) and reels through Instagram. When you press play, those services apply their own privacy policies.</p>

        <h2 style={h2}>Hosting and our own YouTube data</h2>
        <p style={p}>The site is hosted by Vercel. To publish new episode pages, we read our own YouTube channel’s video details and captions through the YouTube API. We don’t access anyone else’s YouTube account. Our use of YouTube data follows the YouTube Terms of Service and the Google Privacy Policy.</p>

        <h2 style={h2}>Your rights</h2>
        <p style={p}>You can ask us to see, correct or delete what you sent us at any time: write to breaktheroutine@protonmail.com.</p>
      </div>
    </main>
  );
}
