// Smoke test after adding an episode. Needs `npm run build` first.
//   node tools/auto/smoke.js <slug> "<Guest Name>"
// Starts the built site on port 3311, opens every page on desktop and phone, and fails (exit 1) on a
// page error, a non-200 page, a broken image, horizontal overflow, or a guest missing from the pages that
// must list them.
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const [slug, name] = process.argv.slice(2);
if (!slug || !name) { console.error('usage: node tools/auto/smoke.js <slug> "<Guest Name>"'); process.exit(2); }
const ROOT = path.join(__dirname, '..', '..');
const eps = fs.readdirSync(path.join(ROOT, 'app', 'episodes'), { withFileTypes: true }).filter((d) => d.isDirectory()).map((d) => '/episodes/' + d.name);
const routes = ['/', '/episodes', '/chain', '/atlas', '/search', '/about', ...eps];
const mustList = { '/episodes': name, '/chain': name.split(' ')[0], ['/episodes/' + slug]: name.toUpperCase() };

(async () => {
  const srv = spawn('npx', ['next', 'start', '-p', '3311'], { cwd: ROOT, stdio: 'ignore', detached: true });
  const base = 'http://localhost:3311';
  for (let i = 0; i < 60; i++) { try { const r = await fetch(base + '/'); if (r.ok) break; } catch (e) {} await new Promise((r) => setTimeout(r, 500)); }
  const b = await chromium.launch();
  const issues = [];
  for (const vp of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    const ctx = await b.newContext({ viewport: vp });
    await ctx.addInitScript(() => { try { sessionStorage.setItem('btr-intro', '1'); } catch (e) {} });
    for (const r of routes) {
      const p = await ctx.newPage(); const errs = [];
      p.on('pageerror', (e) => errs.push(String(e).slice(0, 200)));
      const resp = await p.goto(base + r, { waitUntil: 'load' }).catch(() => null);
      await p.waitForTimeout(500);
      const info = await p.evaluate(() => ({
        overflow: document.documentElement.scrollWidth - window.innerWidth,
        broken: Array.from(document.images).filter((i) => i.complete && i.naturalWidth === 0 && !i.src.startsWith('data:') && !/ytimg|instagram/.test(i.src)).map((i) => i.src).slice(0, 3),
        text: document.body.innerText,
      }));
      const tag = (vp.width < 500 ? 'phone ' : 'desktop ') + r;
      if (!resp || resp.status() !== 200) issues.push(tag + ': status ' + (resp && resp.status()));
      if (errs.length) issues.push(tag + ': ' + errs.join(' | '));
      if (info.overflow > 1) issues.push(tag + ': horizontal overflow ' + info.overflow + 'px');
      if (info.broken.length) issues.push(tag + ': broken images ' + info.broken.join(', '));
      if (mustList[r] && !info.text.includes(mustList[r])) issues.push(tag + ': "' + mustList[r] + '" not on the page');
      await p.close();
    }
    await ctx.close();
  }
  await b.close();
  try { process.kill(-srv.pid); } catch (e) {}
  if (issues.length) { console.log('SMOKE TEST FAILED\n' + issues.join('\n')); process.exit(1); }
  console.log('Smoke test OK: ' + routes.length + ' pages × 2 screens');
})();
