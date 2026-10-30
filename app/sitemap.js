// Pages Google should know about (the Ask page stays out: it is only shared from Instagram).
import fs from 'node:fs';
import path from 'node:path';

export default function sitemap() {
  const base = (process.env.SITE_URL || 'https://www.breaktheroutinepodcast.com').replace(/\/$/, '');
  const eps = fs.readdirSync(path.join(process.cwd(), 'app', 'episodes'), { withFileTypes: true }).filter((d) => d.isDirectory()).map((d) => '/episodes/' + d.name);
  const now = new Date();
  return ['', '/episodes', '/chain', '/atlas', '/search', '/about', '/privacy', '/terms', ...eps].map((p) => ({ url: base + p, lastModified: now, changeFrequency: p.startsWith('/episodes/') ? 'monthly' : 'weekly', priority: p === '' ? 1 : 0.7 }));
}
