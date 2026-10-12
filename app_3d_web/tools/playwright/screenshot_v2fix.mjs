import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.setViewportSize({ width: 1600, height: 900 });

// Capture browser console for debug
page.on('console', msg => {
  if (msg.text().includes('[V2]')) console.log('BROWSER:', msg.text());
});

await page.goto('http://localhost:5173/', { waitUntil: 'networkidle', timeout: 15000 });
await page.locator('button.btn-compare').click();

// Wait for FBX load + rest-pose computation + several animation frames
await page.waitForTimeout(10000);
await page.screenshot({ path: 'C:/Users/logan/AppData/Local/Temp/screen_v2fix_a.png' });
console.log('frame A (10s)');

await page.waitForTimeout(5000);
await page.screenshot({ path: 'C:/Users/logan/AppData/Local/Temp/screen_v2fix_b.png' });
console.log('frame B (15s)');

await browser.close();
