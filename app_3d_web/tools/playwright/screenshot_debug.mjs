import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.setViewportSize({ width: 1600, height: 900 });

// Capture ALL console messages
const logs = [];
page.on('console', msg => logs.push(`[${msg.type()}] ${msg.text()}`));

await page.goto('http://localhost:5173/', { waitUntil: 'networkidle', timeout: 15000 });
await page.locator('button.btn-compare').click();
await page.waitForTimeout(8000);

// Inject D_rest debug into the page
const restDirs = await page.evaluate(() => {
  // Can't directly access Three.js internals from here, but we can read from 3D API
  return fetch('/api/expert-pose3d').then(r => r.json()).then(d => {
    const f0 = d.frames[0];
    const f64 = d.frames[64]; // frame at ~8s (8fps * 8s = 64)
    // hip→knee directions in Three.js space (y, z, x mapping)
    const dir3JS = (p, c) => {
      const dx = c[1]-p[1], dy = c[2]-p[2], dz = c[0]-p[0];
      const len = Math.sqrt(dx*dx+dy*dy+dz*dz);
      return [dx/len, dy/len, dz/len];
    };
    return {
      frame0_lhip_knee: dir3JS(f0[11], f0[13]),
      frame0_rhip_knee: dir3JS(f0[12], f0[14]),
      frame64_lhip_knee: dir3JS(f64[11], f64[13]),
      frame64_rhip_knee: dir3JS(f64[12], f64[14]),
      frame0_lknee_ank:  dir3JS(f0[13], f0[15]),
      frame64_lknee_ank: dir3JS(f64[13], f64[15]),
    };
  });
});
console.log('=== Joint directions in Three.js space ===');
for (const [k,v] of Object.entries(restDirs)) {
  console.log(`  ${k}: [${v.map(n=>n.toFixed(3))}]`);
}

await browser.close();
