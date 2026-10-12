import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.setViewportSize({ width: 1600, height: 900 });

await page.goto('http://localhost:5173/', { waitUntil: 'networkidle', timeout: 15000 });
await page.screenshot({ path: './screen_home.png' });
console.log('Home captured');

const compareBtn = page.locator('button.btn-compare');
await compareBtn.click();
await page.waitForTimeout(4000);
await page.screenshot({ path: './screen_compare.png' });
console.log('Compare screen captured');

await browser.close();
