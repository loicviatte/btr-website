export const metadata = { title: 'Terms · Break The Routine' };

const mono = { fontFamily: "'PP Monument Extended', 'Arial Black', sans-serif", fontWeight: 800 };
const h2 = { ...mono, margin: '28px 0 0', fontSize: 18 };
const p = { margin: 0, color: '#e8ddd1', lineHeight: 1.6 };

export default function Terms() {
  return (
    <main style={{ background: '#080403', color: '#ffffff', minHeight: '100vh', boxSizing: 'border-box', padding: '72px 20px 96px' }}>
      <div style={{ maxWidth: 720, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 14 }}>
        <a href="/" style={{ ...mono, fontSize: 12, letterSpacing: '0.12em', color: '#fecb7a', textDecoration: 'none' }}>← BREAK THE ROUTINE</a>
        <h1 style={{ ...mono, margin: '12px 0 0', fontSize: 'clamp(28px, 4vw, 44px)', lineHeight: 1.08 }}>Terms</h1>
        <p style={{ ...p, color: '#c9b8a6' }}>Last updated 30 October 2026.</p>

        <h2 style={h2}>The website</h2>
        <p style={p}>breaktheroutinepodcast.com is the home of Break The Routine, a DanceSport podcast hosted by Marius Iepure, a Dance United &amp; Oti Marius Dance Studio production. You may read, watch and share its pages for personal, non-commercial use. Episodes, transcripts, photos, designs and texts belong to Break The Routine or to their owners and may not be reused without permission. Questions sent through our forms may be read on the show.</p>

        <h2 style={h2}>BTR Studio</h2>
        <p style={p}>BTR Studio is the private production tool of the Break The Routine team. It prepares short clips of our own episodes and, with the team’s explicit approval for each post, publishes them on the podcast’s own accounts (YouTube, Instagram, TikTok) through the official APIs of those platforms. It is not offered to the public and acts only on accounts the team owns and has connected itself. Before anything is published, the team member reviews the clip, the caption, the audience (privacy level) and the interaction settings, and confirms. Access can be revoked at any time from each platform’s settings, which stops all publishing.</p>
        <p style={p}>Content published through BTR Studio must follow each platform’s own terms and community guidelines, including TikTok’s Terms of Service, Community Guidelines and Music Usage Confirmation.</p>

        <h2 style={h2}>No warranty</h2>
        <p style={p}>The site and BTR Studio are provided as they are. We do our best to keep information accurate but can’t guarantee it.</p>

        <h2 style={h2}>Contact</h2>
        <p style={p}>breaktheroutine@protonmail.com. See also our <a href="/privacy" style={{ color: '#fecb7a' }}>privacy page</a>.</p>
      </div>
    </main>
  );
}
