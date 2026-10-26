// Until launch (SITE_LIVE unset) search engines are asked not to crawl the site.
export default function robots() {
  const live = process.env.SITE_LIVE === '1';
  return { rules: live ? { userAgent: '*', allow: '/' } : { userAgent: '*', disallow: '/' } };
}
