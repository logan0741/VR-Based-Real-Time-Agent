import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.setViewportSize({ width: 1600, height: 900 });

await page.goto('http://localhost:5173/', { waitUntil: 'networkidle', timeout: 15000 });
await page.locator('button.btn-compare').click();

// Wait longer for animation + FBX to fully load
await page.waitForTimeout(8000);
await page.screenshot({ path: 'C:/Users/logan/AppData/Local/Temp/screen_compare2.png' });
console.log('frame at 8s');

await page.waitForTimeout(3000);
await page.screenshot({ path: 'C:/Users/logan/AppData/Local/Temp/screen_compare3.png' });
console.log('frame at 11s');

await browser.close();
