// Wrap original raster artwork with a progressive four-second reveal.
// Static image remains visible when animation is unsupported.
import { readFile, writeFile } from 'node:fs/promises';
const root = new URL('../', import.meta.url);
const png = await readFile(new URL('assets/eval-skills-banner.png', root));
if (png.subarray(0, 8).toString('hex') !== '89504e470d0a1a0a') throw new Error('Expected PNG');
const width = png.readUInt32BE(16), height = png.readUInt32BE(20);
if (width !== height * 3) throw new Error(`Expected 3:1 artwork, got ${width}x${height}`);
const radius = Math.ceil(Math.hypot(width / 2, height / 2) / .75);
const stars = [[.09,.12],[.23,.07],[.44,.11],[.65,.06],[.81,.14],[.93,.09]];
const twinkles = stars.map(([x,y], i) => `<circle class="twinkle" cx="${x*width}" cy="${y*height}" r="${width/1600}" fill="#fff4cd" opacity="0"><animate attributeName="opacity" values="0;0.7;0" begin="${4+i*.35}s" dur="${3.5+i*.4}s" repeatCount="indefinite" /></circle>`).join('\n');
const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-labelledby="title desc">
<title id="title">Eval Skills — an illuminated celestial atlas</title>
<desc id="desc">Romantic pointillist artwork, revealed gently from its center over four seconds, with subtle star twinkles.</desc>
<style>@media (prefers-reduced-motion: reduce) { .art { mask: none !important; } .twinkle { display: none !important; } }</style>
<defs>
 <radialGradient id="soft"><stop offset="0.75" stop-color="white"/><stop offset="1" stop-color="black"/></radialGradient>
 <mask id="reveal" maskUnits="userSpaceOnUse" x="0" y="0" width="${width}" height="${height}" style="mask-type:luminance">
  <rect width="${width}" height="${height}" fill="black"/>
  <circle cx="${width/2}" cy="${height/2}" r="${radius}" fill="url(#soft)"><animate attributeName="r" from="0" to="${radius}" dur="4s" fill="freeze" calcMode="spline" keyTimes="0;1" keySplines="0.25 0.1 0.25 1"/></circle>
 </mask>
</defs>
<g class="art" mask="url(#reveal)"><image width="${width}" height="${height}" href="data:image/png;base64,${png.toString('base64')}"/></g>
${twinkles}
</svg>\n`;
await writeFile(new URL('assets/eval-skills-banner-radial-4s.svg', root), svg);
console.log(`Generated ${width}x${height} SVG banner`);
