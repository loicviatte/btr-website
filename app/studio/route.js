// breaktheroutinepodcast.com/studio (?c=yt|sp|ig|tt|site…) -> Oti Marius Dance Studio.
// The click is counted by the InBetween site (/go/studio -> Supabase `link_clicks`),
// server to server, so the visitor goes straight to the studio site.
export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const TARGET = 'https://otimabusedancestudio.com/';
const COUNTER = 'https://www.useinbetween.com/go/studio';

export async function GET(req) {
  const c = (new URL(req.url).searchParams.get('c') || '').toLowerCase();
  const qs = /^[a-z0-9]{1,12}$/.test(c) ? `?c=${c}` : '';
  try {
    await fetch(COUNTER + qs, {
      redirect: 'manual',
      cache: 'no-store',
      headers: { 'user-agent': 'btr-website/studio-link' },
      signal: AbortSignal.timeout(1500),
    });
  } catch (e) {
    // Counting is optional: never block the visitor.
  }
  return Response.redirect(TARGET, 307);
}
