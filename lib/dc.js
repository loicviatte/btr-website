// Tiny runtime that lets the compiled Claude Design pages run as React class components.
import React from 'react';
import ASSETS from './assets.generated.json';
import ROUTES from './routes.generated.json';

export class DCLogic extends React.Component {
  renderVals() {
    return {};
  }
}

const cache = new Map();
const camel = (s) => s.replace(/-([a-z])/g, (_, c) => c.toUpperCase());

// "a: b; c-d: e" -> { a: 'b', cD: 'e' }
export function css(str) {
  if (str == null) return undefined;
  if (typeof str === 'object') return str;
  const hit = cache.get(str);
  if (hit) return hit;
  const o = {};
  let depth = 0;
  let q = null;
  let cur = '';
  const decls = [];
  for (const ch of String(str)) {
    if (q) { cur += ch; if (ch === q) q = null; continue; }
    if (ch === '"' || ch === "'") { q = ch; cur += ch; continue; }
    if (ch === '(') depth++;
    if (ch === ')') depth--;
    if (ch === ';' && depth === 0) { decls.push(cur); cur = ''; continue; }
    cur += ch;
  }
  decls.push(cur);
  for (const d of decls) {
    const i = d.indexOf(':');
    if (i < 0) continue;
    const k = d.slice(0, i).trim();
    const v = d.slice(i + 1).trim();
    if (!k || !v) continue;
    const key = k.startsWith('--') ? k : k.startsWith('-webkit-') ? 'Webkit' + camel(k.slice(8)).replace(/^./, (c) => c.toUpperCase()) : camel(k);
    o[key] = v;
  }
  if (cache.size > 5000) cache.clear();
  cache.set(str, o);
  return o;
}

// Rewrites canvas URLs: "Episodes.dc.html" -> "/episodes", "/_blob/<id>" -> "/assets/<id>.<ext>"
export function dcUrl(u) {
  if (typeof u !== 'string' || !u) return u || undefined;
  if (u.startsWith('/_blob/')) {
    const id = u.slice(7, 39);
    return ASSETS[id] || u;
  }
  const m = u.match(/(?:^|\/)((?:Tablet-|Phone-)?([A-Za-z0-9_-]+)\.dc\.html)(#.*)?$/);
  if (m && !/^https?:/.test(u)) {
    const file = m[2] + '.dc.html';
    return (ROUTES[file] || '/') + (m[3] || '');
  }
  return u;
}

// External links open in a new tab.
export function dcExt(u) {
  return typeof u === 'string' && /^https?:\/\//.test(u) ? { target: '_blank', rel: 'noopener noreferrer' } : {};
}
