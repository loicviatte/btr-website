// node tools/auto/country_shape.mjs "Peru" [no]
// Prints the World Atlas entries for one country, in the same projection as the site's map
// (Natural Earth 1, fitted to 1000 px wide, Antarctica excluded, top at 0 → 1000 × 444):
//   atlas: { no, d, x, y, b }  -> push into MAP in design/Atlas.dc.html (and its row in raw[])
//   home:  { d, left, top }    -> extra <path> in svg.m-atlas-shapes + pin <span> in design/Main.dc.html
// With a 4th argument (a file path) it also writes the gold country silhouette used by the Atlas carousel cover
// (900 px wide SVG, like public/assets/228b0d79….svg); add it with: python3 tools/auto/btr_auto.py thumb <file.svg>
import { readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { feature } from 'topojson-client';
import { geoPath, geoNaturalEarth1, geoMercator, geoCentroid, geoArea } from 'd3-geo';

const require = createRequire(import.meta.url);
const name = process.argv[2];
const no = process.argv[3] || '??';
if (!name) { console.error('usage: node tools/auto/country_shape.mjs "<country>" [no]'); process.exit(1); }
const load = (f) => JSON.parse(readFileSync(require.resolve('world-atlas/' + f)));
const topo = load('countries-50m.json');
const all = feature(topo, topo.objects.countries).features.filter((f) => f.properties.name !== 'Antarctica');
const fc = { type: 'FeatureCollection', features: all };
const proj = geoNaturalEarth1().fitWidth(1000, fc);
const path = geoPath(proj);
const [[, y0]] = path.bounds(fc);
proj.translate([proj.translate()[0], proj.translate()[1] - y0]);

const norm = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z]/g, '');
const ALIAS = { drc: 'demrepcongo', democraticrepublicofthecongo: 'demrepcongo', republicofthecongo: 'congo', ivorycoast: 'cotedivoire', czechrepublic: 'czechia', unitedstates: 'unitedstatesofamerica', usa: 'unitedstatesofamerica', uk: 'unitedkingdom', bosnia: 'bosniaandherz', bosniaandherzegovina: 'bosniaandherz', centralafricanrepublic: 'centralafricanrep', dominicanrepublic: 'dominicanrep', southsudan: 'ssudan', equatorialguinea: 'eqguinea', northmacedonia: 'macedonia', eswatini: 'eswatini', swaziland: 'eswatini', easttimor: 'timorleste', saotomeandprincipe: 'saotomeandprincipe' };
const want = ALIAS[norm(name)] || norm(name);
const f = all.find((x) => norm(x.properties.name) === want);
if (!f) {
  const close = all.map((x) => x.properties.name).filter((n) => norm(n).includes(want.slice(0, 4)));
  console.error('Not found: ' + name + (close.length ? '. Did you mean: ' + close.join(', ') : ''));
  process.exit(2);
}
const d1 = path(f).replace(/(\d+\.\d)\d+/g, '$1');
const b = path.bounds(f).flat().map((v) => +v.toFixed(1));
// pin: centroid of the largest polygon (so islands/exclaves don't pull it into the sea)
let main = f;
if (f.geometry.type === 'MultiPolygon') {
  const polys = f.geometry.coordinates.map((c) => ({ type: 'Feature', geometry: { type: 'Polygon', coordinates: c } }));
  main = polys.sort((a, c) => geoArea(c) - geoArea(a))[0];
}
const [lon, lat] = geoCentroid(main);
const [x, y] = proj([lon, lat]).map((v) => +v.toFixed(1));
// home map: integer coordinates, consecutive duplicates removed
const dInt = path(f).replace(/(-?\d+)\.\d+/g, '$1').replace(/L(-?\d+,-?\d+)(?=(L\1)+)/g, '');
if (process.argv[4]) {
  const m = geoMercator().fitSize([900, 900], f);
  const p2 = geoPath(m);
  const [[bx0, by0], [bx1, by1]] = p2.bounds(f);
  const vw = Math.ceil(bx1 - bx0), vh = Math.ceil(by1 - by0);
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${Math.floor(bx0)} ${Math.floor(by0)} ${vw} ${vh}" width="${vw}" height="${vh}"><path fill="#FECB7A" d="${p2(f).replace(/(\d+\.\d)\d+/g, '$1')}"/></svg>`;
  writeFileSync(process.argv[4], svg);
}
console.log(JSON.stringify({
  name: f.properties.name,
  lat: +lat.toFixed(1), lon: +lon.toFixed(1),
  atlas: { no, d: d1, x, y, b },
  home: { d: dInt, left: +(x / 10).toFixed(2), top: +(y / 444 * 100).toFixed(2) },
}));
