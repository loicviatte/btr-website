export const metadata = { title: 'Page not found · Break The Routine' };

export default function NotFound() {
  const mono = { fontFamily: "'PP Monument Extended', 'Arial Black', sans-serif", fontWeight: 800 };
  return (
    <main style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', boxSizing: 'border-box', padding: '48px 20px', background: '#080403', color: '#ffffff' }}>
      <div style={{ maxWidth: 640, display: 'flex', flexDirection: 'column', gap: 20 }}>
        <p style={{ ...mono, margin: 0, fontSize: 12, letterSpacing: '0.12em', color: '#fecb7a' }}>404</p>
        <h1 style={{ ...mono, margin: 0, fontSize: 'clamp(30px, 5vw, 56px)', lineHeight: 1.05 }}>This page broke the routine.</h1>
        <p style={{ margin: 0, color: '#c9b8a6', fontSize: 18 }}>It doesn’t exist, or it moved. The episodes are still here.</p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
          <a href="/" style={{ ...mono, display: 'inline-flex', alignItems: 'center', minHeight: 52, padding: '0 24px', background: '#fecb7a', color: '#000000', fontSize: 13, letterSpacing: '0.04em', textDecoration: 'none' }}>HOME</a>
          <a href="/episodes" style={{ ...mono, display: 'inline-flex', alignItems: 'center', minHeight: 52, padding: '0 24px', border: '1px solid rgba(254,203,122,0.55)', color: '#ffffff', fontSize: 13, letterSpacing: '0.04em', textDecoration: 'none' }}>ALL EPISODES</a>
        </div>
      </div>
    </main>
  );
}
