// Until launch (SITE_LIVE unset) search engines are asked not to crawl the site.
export default function robots() {
  const live = process.env.SITE_LIVE === '1';
  const base = (process.env.SITE_URL || 'https://www.breaktheroutinepodcast.com').replace(/\/$/, '');
  return live
    ? { rules: { userAgent: '*', allow: '/', disallow: '/ask' }, sitemap: base + '/sitemap.xml' }
    : { rules: { userAgent: '*', disallow: '/' } };
}
