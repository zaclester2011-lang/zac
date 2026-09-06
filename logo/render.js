const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const [svg, out, scale] = process.argv.slice(2);
  const html = `<style>html,body{margin:0;padding:0}svg{display:block}</style>` + fs.readFileSync(svg, 'utf8');
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: Number(scale) });
  await p.setContent(html);
  await p.screenshot({ path: out, clip: { x: 0, y: 0, width: 1600, height: 1000 } });
  await b.close();
})();
