// "Ask the next guest" form → Google Sheet (+ email) through a Google Apps Script web app.
// Vercel env: ASK_WEBHOOK_URL (the Apps Script /exec URL) and ASK_SECRET (same value as in the script).
export const runtime = 'nodejs';

const recent = new Map();

export async function POST(req) {
  let b;
  try { b = await req.json(); } catch (e) { return Response.json({ error: 'Invalid request.' }, { status: 400 }); }
  // bots fill the hidden "website" field: pretend it worked
  if (b.website) return Response.json({ ok: true });
  const name = String(b.name || '').trim().slice(0, 80);
  const ig = String(b.ig || '').trim().slice(0, 40);
  const q = String(b.q || '').trim().slice(0, 280);
  if (!name || !q) return Response.json({ error: 'Please add your name and your question.' }, { status: 400 });

  const ip = (req.headers.get('x-forwarded-for') || '').split(',')[0].trim() || 'anon';
  const now = Date.now();
  const list = (recent.get(ip) || []).filter((t) => now - t < 10 * 60e3);
  if (list.length >= 5) return Response.json({ error: 'You have sent several questions already. Please try again a bit later.' }, { status: 429 });
  list.push(now); recent.set(ip, list);
  if (recent.size > 5000) recent.clear();

  const url = process.env.ASK_WEBHOOK_URL;
  if (!url) return Response.json({ error: 'The question box is not connected yet. Please send your question to us on Instagram @breaktheroutinepodcast.' }, { status: 503 });
  try {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'text/plain;charset=utf-8' },
      body: JSON.stringify({ secret: process.env.ASK_SECRET || '', name, ig, q, ok: !!b.ok, page: req.headers.get('referer') || '' }),
      redirect: 'follow',
      signal: AbortSignal.timeout(15000),
    });
    const t = await r.text();
    if (!r.ok || !/"ok"\s*:\s*true/.test(t)) throw new Error('webhook ' + r.status);
    return Response.json({ ok: true });
  } catch (e) {
    return Response.json({ error: 'Your question could not be sent. Please try again, or send it to us on Instagram @breaktheroutinepodcast.' }, { status: 502 });
  }
}
