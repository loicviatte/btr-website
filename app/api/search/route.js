// Optional "search by meaning": the page sends the question + its ~40 best keyword candidates,
// Claude reorders them by how well each passage actually answers the question.
// Only active when ANTHROPIC_API_KEY is set in Vercel; otherwise the page keeps its own ranking.
export const runtime = 'nodejs';

const cache = new Map();

export async function POST(req) {
  const key = process.env.ANTHROPIC_API_KEY;
  if (!key) return new Response(null, { status: 204 });
  let body;
  try { body = await req.json(); } catch (e) { return new Response(null, { status: 400 }); }
  const q = String(body.q || '').slice(0, 200).trim();
  const items = Array.isArray(body.items) ? body.items.slice(0, 40) : [];
  if (!q || !items.length) return Response.json({ ids: [] });
  const ck = q.toLowerCase() + '|' + items.map((i) => i.id).join(',');
  if (cache.has(ck)) return Response.json({ ids: cache.get(ck) });

  const list = items.map((it, n) => `[${n}] (${String(it.guest || '').slice(0, 60)}) ${String(it.text || '').slice(0, 700)}`).join('\n');
  const prompt = `A visitor searched a DanceSport podcast's transcripts for: "${q}"\n\nHere are candidate transcript passages:\n${list}\n\nReturn the numbers of the passages that genuinely talk about what the visitor is asking, best answer first. Leave out passages that only share a word but are about something else. Reply with JSON only, like {"order":[3,0,7]}.`;

  try {
    const r = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-api-key': key, 'anthropic-version': '2023-06-01' },
      body: JSON.stringify({ model: process.env.SEARCH_MODEL || 'claude-haiku-5-5', max_tokens: 300, messages: [{ role: 'user', content: prompt }] }),
      signal: AbortSignal.timeout(12000),
    });
    if (!r.ok) return new Response(null, { status: 204 });
    const j = await r.json();
    const text = (j.content || []).map((c) => c.text || '').join('');
    const m = text.match(/\{[\s\S]*\}/);
    const order = m ? JSON.parse(m[0]).order : [];
    const ids = (Array.isArray(order) ? order : []).filter((n) => Number.isInteger(n) && items[n]).map((n) => items[n].id);
    if (cache.size > 500) cache.clear();
    cache.set(ck, ids);
    return Response.json({ ids });
  } catch (e) {
    return new Response(null, { status: 204 });
  }
}
