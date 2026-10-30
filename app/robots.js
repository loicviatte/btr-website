// Live: search engines may crawl everything but /ask. Set SITE_LIVE=0 in Vercel to hide the site again.
export default function robots() {
  const live = process.env.SITE_LIVE !== '0';
  const base = (process.env.SITE_URL || 'https://www.breaktheroutinepodcast.com').replace(/\/$/, '');
  return live
    ? { rules: { userAgent: '*', allow: '/', disallow: ['/ask', '/tiktok'] }, sitemap: base + '/sitemap.xml' }
    : { rules: { userAgent: '*', disallow: '/' } };
}
