import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.setViewportSize({ width: 1400, height: 800 });
const errs = [];
page.on('pageerror', e => errs.push(e.message));

await page.goto('http://localhost:5173/', { waitUntil: 'networkidle', timeout: 30000 });
const btns = await page.$$('button');
for (const b of btns) {
  const t = await b.textContent();
  if (t && t.includes('비교')) { await b.click(); break; }
}
await page.waitForTimeout(4000);
await page.screenshot({ path: 'C:/Project/VR-Based-Real-Time-Agent/screenshot_osctest_4s.png' });
await page.waitForTimeout(2000);
await page.screenshot({ path: 'C:/Project/VR-Based-Real-Time-Agent/screenshot_osctest_6s.png' });
if (errs.length) console.log('Errors:', errs[0]);
else console.log('No errors');
await browser.close();
