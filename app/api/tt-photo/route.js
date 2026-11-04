// TikTok photo carousels (bot `tiktok.photo_url`): TikTok's Content Posting API only pulls photos from a domain
// verified in the TikTok developer portal (this site). The bot points TikTok here and this route serves the slide:
//   ?id=<Google Drive file id>   (validated carousel slides in « BTR Posts », shared by link)
//   ?m=<path in btr-media>       (World Atlas slides, public repo loicviatte/btr-media)
// Only images are served (checked by their first bytes), PNG is turned into JPEG (TikTok takes JPEG / WEBP only).
export const runtime = 'nodejs';

const MEDIA = 'https://raw.githubusercontent.com/loicviatte/btr-media/main/';
const MAX = 20 * 1024 * 1024;

function kind(b) {
  if (b.length > 3 && b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff) return 'jpeg';
  if (b.length > 8 && b[0] === 0x89 && b[1] === 0x50 && b[2] === 0x4e && b[3] === 0x47) return 'png';
  if (b.length > 12 && b.toString('ascii', 0, 4) === 'RIFF' && b.toString('ascii', 8, 12) === 'WEBP') return 'webp';
  return null;
}

function source(params) {
  const id = params.get('id');
  const m = params.get('m');
  if (id && /^[A-Za-z0-9_-]{20,100}$/.test(id)) {
    return `https://drive.usercontent.google.com/download?id=${id}&export=download&confirm=t`;
  }
  if (m && /^[A-Za-z0-9._\/-]+\.(png|jpe?g|webp)$/i.test(m) && !m.includes('..') && !m.startsWith('/')) {
    return MEDIA + m.split('/').map(encodeURIComponent).join('/');
  }
  return null;
}

export async function GET(req) {
  const url = source(new URL(req.url).searchParams);
  if (!url) return new Response('bad request', { status: 400 });
  let r;
  try {
    r = await fetch(url, { redirect: 'follow', cache: 'no-store' });
  } catch {
    return new Response('upstream error', { status: 502 });
  }
  if (!r.ok) return new Response('not found', { status: r.status === 404 ? 404 : 502 });
  const len = parseInt(r.headers.get('content-length') || '0', 10);
  if (len > MAX) return new Response('too large', { status: 413 });
  let buf = Buffer.from(await r.arrayBuffer());
  if (buf.length > MAX) return new Response('too large', { status: 413 });
  let type = kind(buf);
  if (!type) return new Response('not an image', { status: 415 });
  if (type === 'png') {
    try {
      const sharp = (await import('sharp')).default;
      buf = await sharp(buf).flatten({ background: '#000000' }).jpeg({ quality: 92, mozjpeg: true }).toBuffer();
      type = 'jpeg';
    } catch {
      return new Response('png conversion failed', { status: 500 });
    }
  }
  return new Response(buf, {
    headers: {
      'Content-Type': `image/${type}`,
      'Content-Length': String(buf.length),
      'Cache-Control': 'public, max-age=86400, s-maxage=86400',
    },
  });
}
