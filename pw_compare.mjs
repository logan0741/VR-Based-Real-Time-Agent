import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.setViewportSize({ width: 1400, height: 800 });
await page.goto('http://localhost:5173/', { waitUntil: 'networkidle', timeout: 30000 });

// Find compare button
const btns = await page.$$('button');
for (const b of btns) {
  const t = await b.textContent();
  if (t && t.includes('비교')) {
    await b.click();
    console.log('Clicked:', t.trim());
    break;
  }
}

await page.waitForTimeout(7000);
await page.screenshot({ path: 'C:/Project/VR-Based-Real-Time-Agent/screenshot_compare_after_click.png' });
console.log('Screenshot saved');
await browser.close();
