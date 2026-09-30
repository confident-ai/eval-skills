# Repository artwork

Original evaluation-themed romantic pointillism, generated with the built-in image-generation tool. The Confident Trace and Confident Actions repository banners are style references, not copied compositions.

The visual family uses luminous gold against violet/blue, celestial scenery, and visible painted dots. This banner uses an exact 3:1 panorama. Final PNG dimensions: **2172 × 724 pixels**, exactly matching Confident Trace.

Concept: a celestial atlas in a quiet observatory garden, where small scattered lights resolve into understandable patterns. No embedded title or marketing text.

Generation prompt:

> Create an original panoramic repository banner in romantic pointillism, exact 3:1 aspect ratio, ideally 2172 by 724 pixels. An open celestial atlas on an old stone observatory terrace overlooks a vast violet-blue night landscape. Fine golden constellation paths connect scattered points into legible patterns above the atlas, evoking careful observation, discovery, and evaluation. The scene should feel luminous and contemplative, with visible painted dots, rich violet/indigo and warm gold, atmospheric depth, and a restrained magical glow. Match the visual family of the supplied Confident Trace and Confident Actions references while creating a distinct composition. No text, logos, borders, watermarks, graphs, or UI elements. Keep the central scene readable at GitHub README width. Render a finished wide image, not a mockup.

The PNG is the static fallback. `scripts/create-banner.mjs` embeds it in an SVG with a four-second radial reveal and subtle twinkles. Reduced-motion users see the complete static image. If animation is unsupported, the default mask radius leaves the image visible.

```bash
node scripts/create-banner.mjs
```

Verify the SVG in a browser at README widths, including `prefers-reduced-motion: reduce`, and inspect the final static PNG. Do not keep alternate generations or preview screenshots in the repository.
