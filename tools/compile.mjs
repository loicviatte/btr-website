// Compiles the Claude Design canvas pages (design/*.dc.html) into React components
// and Next.js routes. Run: npm run compile  (then npm run build)
//
// design/<Name>.dc.html  ->  components/dc/<Name>.jsx
// Routes: Main -> /, Episodes -> /episodes, Episode-<slug> -> /episodes/<slug>, Chain -> /chain, ...
import fs from 'node:fs';
import path from 'node:path';
import { parseDocument } from 'htmlparser2';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const DESIGN = path.join(ROOT, 'design');
const OUT = path.join(ROOT, 'components', 'dc');
const APP = path.join(ROOT, 'app');
const ASSETS = path.join(ROOT, 'public', 'assets');

const SKIP = new Set(['Intro']); // canvas-only preview boards

export const ROUTES = {
  Main: '/', Episodes: '/episodes', Chain: '/chain', Atlas: '/atlas', Search: '/search', About: '/about', Ask: '/ask', Intro: '/',
};
const routeOf = (name) => ROUTES[name] ?? (name.startsWith('Episode-') ? '/episodes/' + name.slice(8) : '/' + name.toLowerCase());

const VOID = new Set(['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr']);
const ATTR_MAP = {
  class: 'className', for: 'htmlFor', tabindex: 'tabIndex', autocomplete: 'autoComplete', maxlength: 'maxLength',
  minlength: 'minLength', readonly: 'readOnly', playsinline: 'playsInline', autoplay: 'autoPlay', srcset: 'srcSet',
  crossorigin: 'crossOrigin', referrerpolicy: 'referrerPolicy', enterkeyhint: 'enterKeyHint', inputmode: 'inputMode',
  'xlink:href': 'xlinkHref', 'xml:space': 'xmlSpace', colspan: 'colSpan', rowspan: 'rowSpan', datetime: 'dateTime',
  spellcheck: 'spellCheck', contenteditable: 'contentEditable', frameborder: 'frameBorder', allowfullscreen: 'allowFullScreen',
};
const BOOL = new Set(['required', 'disabled', 'checked', 'muted', 'loop', 'autoplay', 'playsinline', 'open', 'hidden', 'readonly', 'multiple', 'selected', 'controls', 'novalidate', 'allowfullscreen']);
const camel = (s) => s.replace(/-([a-z])/g, (_, c) => c.toUpperCase());

function attrName(name) {
  if (ATTR_MAP[name]) return ATTR_MAP[name];
  if (name.startsWith('aria-') || name.startsWith('data-')) return name;
  if (name.includes('-')) return camel(name); // svg presentation attrs, etc.
  return name;
}

const HOLE = /\{\{\s*([^}]+?)\s*\}\}/g;
function resolvePath(p, scope) {
  p = p.trim();
  if (/^(true|false|null|undefined)$/.test(p) || /^-?\d+(\.\d+)?$/.test(p)) return p;
  if (/^'.*'$|^".*"$/.test(p)) return JSON.stringify(p.slice(1, -1));
  const parts = p.split('.');
  const head = parts[0];
  const base = scope.has(head) ? head : 'v.' + head;
  return parts.length === 1 ? base : base + parts.slice(1).map((k) => '?.' + k).join('');
}
// a string with holes -> JS expression
function interp(str, scope) {
  const holes = [...str.matchAll(HOLE)];
  if (!holes.length) return JSON.stringify(str);
  if (holes.length === 1 && holes[0][0] === str) return resolvePath(holes[0][1], scope);
  let out = '`';
  let last = 0;
  for (const m of holes) {
    out += str.slice(last, m.index).replace(/[`\\$]/g, (c) => '\\' + c);
    out += '${' + `(${resolvePath(m[1], scope)}) ?? ''` + '}';
    last = m.index + m[0].length;
  }
  out += str.slice(last).replace(/[`\\$]/g, (c) => '\\' + c) + '`';
  return out;
}

function styleToObject(s) {
  const o = {};
  // split on ; not inside parentheses or quotes
  let depth = 0, q = null, cur = '';
  const decls = [];
  for (const ch of s) {
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
    const val = d.slice(i + 1).trim();
    if (!k || !val) continue;
    const key = k.startsWith('--') ? k : k.startsWith('-webkit-') ? 'Webkit' + camel(k.slice(8)).replace(/^./, (c) => c.toUpperCase()) : camel(k);
    o[key] = val;
  }
  return o;
}

const usedImports = new Set();
let helmetCss = [];
let helmetLinks = [];

function attrsToJsx(el, scope) {
  const out = [];
  for (const [rawName, rawVal] of Object.entries(el.attribs || {})) {
    const name = rawName;
    if (name.startsWith('hint-')) continue;
    const jsxName = attrName(name.toLowerCase() === name ? name : name); // keep camel (onClick, viewBox)
    const val = rawVal ?? '';
    if (name === 'style') {
      if (HOLE.test(val)) { HOLE.lastIndex = 0; out.push(`style={css(${interp(val, scope)})}`); }
      else out.push(`style={${JSON.stringify(styleToObject(val))}}`);
      HOLE.lastIndex = 0;
      continue;
    }
    if (val === '' && BOOL.has(name.toLowerCase())) { out.push(`${attrName(name.toLowerCase())}={true}`); continue; }
    let expr = interp(val, scope);
    if (name === 'href' || name === 'src' || name === 'poster') expr = `dcUrl(${expr})`;
    const n = ATTR_MAP[name.toLowerCase()] ?? jsxName;
    // controlled inputs keep value/checked; textarea value too
    if (/^[a-z]/.test(n) && expr.startsWith('"')) out.push(`${n}=${expr}`);
    else out.push(`${n}={${expr}}`);
  }
  return out.join(' ');
}

function textToJsx(t, scope) {
  if (!t) return '';
  if (/^\s+$/.test(t)) return /\n/.test(t) ? '{" "}' : '{" "}';
  const holes = [...t.matchAll(HOLE)];
  if (!holes.length) return `{${JSON.stringify(t.replace(/\s+/g, ' '))}}`;
  let out = '';
  let last = 0;
  for (const m of holes) {
    const lit = t.slice(last, m.index).replace(/\s+/g, ' ');
    if (lit) out += `{${JSON.stringify(lit)}}`;
    out += `{${resolvePath(m[1], scope)}}`;
    last = m.index + m[0].length;
  }
  const tail = t.slice(last).replace(/\s+/g, ' ');
  if (tail) out += `{${JSON.stringify(tail)}}`;
  return out;
}

function nodeToJsx(node, scope, depth = 0) {
  if (node.type === 'text') return textToJsx(node.data, scope);
  if (node.type === 'comment' || node.type === 'directive') return '';
  if (node.type === 'script' || node.type === 'style') {
    if (node.type === 'style') helmetCss.push(node.children.map((c) => c.data).join(''));
    return '';
  }
  if (node.type !== 'tag') return '';
  const tag = node.name;
  const kids = () => (node.children || []).map((c) => nodeToJsx(c, scope, depth + 1)).join('');
  if (tag === 'helmet') {
    for (const c of node.children || []) {
      if (c.type === 'style') helmetCss.push(c.children.map((x) => x.data).join(''));
      if (c.type === 'tag' && c.name === 'link') helmetLinks.push(c.attribs.href);
    }
    return '';
  }
  if (tag === 'x-dc') return kids();
  if (tag === 'sc-for') {
    const list = (node.attribs.list || '').replace(HOLE, (_, p) => p).trim();
    const as = node.attribs.as || 'item';
    const inner = new Set(scope); inner.add(as); inner.add('$index');
    const body = (node.children || []).map((c) => nodeToJsx(c, inner, depth + 1)).join('');
    return `{(${resolvePath(list, scope)} || []).map((${as}, $index) => (<React.Fragment key={$index}>${body}</React.Fragment>))}`;
  }
  if (tag === 'sc-if') {
    const val = (node.attribs.value || '').replace(HOLE, (_, p) => p).trim();
    return `{${resolvePath(val, scope)} ? (<>${kids()}</>) : null}`;
  }
  if (tag === 'dc-import') {
    const comp = node.attribs.name;
    usedImports.add(comp);
    const props = Object.entries(node.attribs)
      .filter(([k]) => k !== 'name' && !k.startsWith('hint-'))
      .map(([k, v]) => `${camel(k)}={${interp(v, scope)}}`).join(' ');
    return `<${safeIdent(comp)} ${props} />`;
  }
  const a = attrsToJsx(node, scope);
  if (VOID.has(tag)) return `<${tag}${a ? ' ' + a : ''} />`;
  if (tag === 'textarea') return `<textarea${a ? ' ' + a : ''} />`;
  const inner = kids();
  return `<${tag}${a ? ' ' + a : ''}>${inner}</${tag}>`;
}

const safeIdent = (name) => 'C_' + name.replace(/[^A-Za-z0-9_]/g, '_');

function compileFile(file) {
  const name = path.basename(file, '.dc.html');
  const src = fs.readFileSync(file, 'utf8');
  const doc = parseDocument(src, { lowerCaseAttributeNames: false, lowerCaseTags: true, recognizeSelfClosing: false, decodeEntities: true });
  const find = (n, pred) => { if (pred(n)) return n; for (const c of n.children || []) { const r = find(c, pred); if (r) return r; } return null; };
  const xdc = find(doc, (n) => n.type === 'tag' && n.name === 'x-dc');
  const script = find(doc, (n) => n.type === 'script' && n.attribs && n.attribs.type === 'text/x-dc');
  const code = script ? script.children.map((c) => c.data).join('') : 'class Component extends DCLogic { renderVals() { return {}; } }';
  usedImports.clear();
  const jsx = nodeToJsx(xdc, new Set());
  const imports = [...usedImports].map((c) => `import ${safeIdent(c)} from './${c}';`).join('\n');
  const out = `'use client';
// GENERATED from design/${name}.dc.html by tools/compile.mjs. Edit the design file, then run npm run compile.
import React from 'react';
import { DCLogic, css, dcUrl } from '../../lib/dc';
${imports}

${code.trim()}

Component.prototype.render = function render() {
  const v = this.renderVals() || {};
  return (<>${jsx}</>);
};

export default Component;
`;
  fs.writeFileSync(path.join(OUT, name + '.jsx'), out);
  return name;
}

// ---------- main
fs.mkdirSync(OUT, { recursive: true });
const files = fs.readdirSync(DESIGN).filter((f) => f.endsWith('.dc.html'));
const names = [];
for (const f of files) {
  const n = path.basename(f, '.dc.html');
  if (SKIP.has(n)) continue;
  names.push(compileFile(path.join(DESIGN, f)));
}

// asset map: /_blob/<id> -> /assets/<id>.<ext>
const assets = fs.existsSync(ASSETS) ? fs.readdirSync(ASSETS) : [];
const map = {};
for (const a of assets) { const m = a.match(/^([0-9a-f]{32})\.(\w+)$/); if (m) map[m[1]] = '/assets/' + a; }
const missing = new Set();
const fixBlobs = (s) => s.replace(/\/_blob\/([0-9a-f]{32})/g, (m0, id) => { if (map[id]) return map[id]; missing.add(id); return m0; });

// global css: dedupe helmet css blocks line by line
const seen = new Set();
const cssLines = [];
for (const block of helmetCss) {
  for (const line of block.split('\n')) {
    const l = line.trim();
    if (!l || seen.has(l)) continue;
    seen.add(l); cssLines.push(l);
  }
}
fs.writeFileSync(path.join(APP, 'dc.generated.css'), '/* GENERATED by tools/compile.mjs from the design files */\n' + fixBlobs(cssLines.join('\n')) + '\n');
fs.writeFileSync(path.join(ROOT, 'lib', 'fonts.generated.json'), JSON.stringify([...new Set(helmetLinks)], null, 1));

// routes
const META = {
  Main: 'Break The Routine · The DanceSport Podcast',
  Episodes: 'Episodes · Break The Routine', Chain: 'The Chain · Break The Routine', Atlas: 'World Atlas · Break The Routine',
  Search: 'Search every episode · Break The Routine', About: 'About · Break The Routine', Ask: 'Ask the next guest · Break The Routine',
};
for (const n of names) {
  const r = routeOf(n);
  const dir = path.join(APP, ...r.split('/').filter(Boolean));
  fs.mkdirSync(dir, { recursive: true });
  let title = META[n];
  if (!title && n.startsWith('Episode-')) {
    const guest = n.slice(8).split('-').map((w) => w[0].toUpperCase() + w.slice(1)).join(' ');
    title = `${guest} · Break The Routine`;
  }
  fs.writeFileSync(path.join(dir, 'page.jsx'), `// GENERATED by tools/compile.mjs
import Page from '${path.relative(dir, path.join(OUT, n)).split(path.sep).join('/')}';

export const metadata = { title: ${JSON.stringify(title)} };

export default function Route() {
  return <Page />;
}
`);
}

// scan all design sources for asset ids we do not have
for (const f of files) fixBlobs(fs.readFileSync(path.join(DESIGN, f), 'utf8'));
for (const f of files) { const t = fs.readFileSync(path.join(DESIGN, f), 'utf8'); for (const m of t.matchAll(/['"]([0-9a-f]{32})['"]/g)) if (!map[m[1]]) missing.add(m[1]); }
fs.writeFileSync(path.join(ROOT, 'lib', 'missing-assets.generated.json'), JSON.stringify([...missing], null, 1));
fs.writeFileSync(path.join(ROOT, 'lib', 'assets.generated.json'), JSON.stringify(map, null, 1));
const routes = {};
for (const n of [...names, 'Intro']) routes[n + '.dc.html'] = routeOf(n);
fs.writeFileSync(path.join(ROOT, 'lib', 'routes.generated.json'), JSON.stringify(routes, null, 1));
console.log('compiled', names.length, 'pages;', Object.keys(map).length, 'assets mapped');
