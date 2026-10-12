import { chromium } from 'playwright';

// Test which coordinate mapping makes the squat look right
const browser = await chromium.launch({ headless: false }); // visible window
const page = await browser.newPage();
await page.setViewportSize({ width: 800, height: 600 });

const result = await page.evaluate(() => {
  return fetch('/api/expert-pose3d').then(r => r.json()).then(d => {
    // frame 222 = deepest squat, frame 0 = standing
    const f0  = d.frames[0];
    const f222 = d.frames[222];

    // Verify which mapping places lhip LEFT of rhip (correct for frontal view)
    const mappings = {
      original:  pt => [pt[1], pt[2], pt[0]],        // (lateral, height, depth)
      rotCW90:   pt => [-pt[0], pt[2], pt[1]],        // 90° CW around Y
      rotCCW90:  pt => [pt[0], pt[2], -pt[1]],        // 90° CCW around Y
      rot180:    pt => [-pt[1], pt[2], -pt[0]],       // 180° around Y
    };
    const dir = (p, c, m) => {
      const [px,py,pz] = m(p); const [cx,cy,cz] = m(c);
      const dx=cx-px, dy=cy-py, dz=cz-pz;
      const len = Math.sqrt(dx*dx+dy*dy+dz*dz);
      return [+(dx/len).toFixed(3), +(dy/len).toFixed(3), +(dz/len).toFixed(3)];
    };
    const res = {};
    for (const [name, m] of Object.entries(mappings)) {
      const lhip0  = m(f0[11]),  rhip0  = m(f0[12]);
      const lhip22 = m(f222[11]), rhip22 = m(f222[12]);
      res[name] = {
        // At standing: lhip should be LEFT of rhip (lhip.x < rhip.x for frontal)
        stand_lhip_x: +lhip0[0].toFixed(2),
        stand_rhip_x: +rhip0[0].toFixed(2),
        lhip_isLeft: lhip0[0] < rhip0[0],
        // Hip→knee direction at standing (should be ~downward)
        stand_dir: dir(f0[11], f0[13], m),
        // Hip→knee direction at squat (should show bending)
        squat_dir: dir(f222[11], f222[13], m),
      };
    }
    return res;
  });
});

for (const [mapping, v] of Object.entries(result)) {
  console.log(`\n[${mapping}]`);
  console.log(`  lhip LEFT of rhip: ${v.lhip_isLeft} (lhip.x=${v.stand_lhip_x}, rhip.x=${v.stand_rhip_x})`);
  console.log(`  Standing hip→knee: [${v.stand_dir}]`);
  console.log(`  Squat hip→knee:    [${v.squat_dir}]`);
}

await browser.close();
