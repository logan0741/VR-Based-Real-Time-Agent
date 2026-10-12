import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.setViewportSize({ width: 1600, height: 900 });

await page.goto('http://localhost:5173/', { waitUntil: 'networkidle', timeout: 15000 });
await page.locator('button.btn-compare').click();
await page.waitForTimeout(2000);

// Inject console override before FBX loads to capture V2 rest data
const result = await page.evaluate(() => {
  return fetch('/api/expert-pose3d').then(r => r.json()).then(d => {
    // Check frames 70-90 for outliers
    const dir3JS = (p, c) => {
      const dx = c[1]-p[1], dy = c[2]-p[2], dz = c[0]-p[0];
      const len = Math.sqrt(dx*dx+dy*dy+dz*dz);
      return [+(dx/len).toFixed(3), +(dy/len).toFixed(3), +(dz/len).toFixed(3)];
    };
    const results = {};
    for (let i = 70; i <= 90; i += 5) {
      const f = d.frames[i];
      results[`f${i}_lhip_knee`] = dir3JS(f[11], f[13]);
      results[`f${i}_rhip_knee`] = dir3JS(f[12], f[14]);
    }
    // Also check extremes
    const lhipY = d.frames.map((f,i) => ({ i, y: (f[13][2] - f[11][2]) })); // knee_z - hip_z
    lhipY.sort((a,b) => a.y - b.y);
    results.most_bent = lhipY[0];
    results.most_straight = lhipY[lhipY.length-1];
    return results;
  });
});

for (const [k, v] of Object.entries(result)) {
  console.log(`  ${k}:`, JSON.stringify(v));
}

await browser.close();
