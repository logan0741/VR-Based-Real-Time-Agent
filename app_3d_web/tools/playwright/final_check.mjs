import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.setViewportSize({ width: 1400, height: 750 });

// Capture console logs
const logs = [];
page.on('console', msg => {
  if (msg.type() === 'error' || msg.type() === 'warning') {
    logs.push(`[${msg.type()}] ${msg.text()}`);
  }
});

await page.goto('http://localhost:8000/app/', { waitUntil: 'networkidle', timeout: 20000 });
await page.waitForSelector('button', { timeout: 8000 });

for (const btn of await page.locator('button').all()) {
  if ((await btn.textContent())?.includes('스쿼트')) { await btn.click(); break; }
}
await page.waitForTimeout(1500);
for (const btn of await page.locator('button').all()) {
  const t = await btn.textContent();
  if (t && (t.includes('비교') || t.includes('렌더'))) { await btn.click(); break; }
}

// Wait for initial load
await page.waitForTimeout(2000);
await page.screenshot({ path: 'v2_check_0s.png' });

await page.waitForTimeout(1000);
await page.screenshot({ path: 'v2_check_3s.png' });
await page.waitForTimeout(4000);
await page.screenshot({ path: 'v2_check_7s.png' });
await page.waitForTimeout(4000);
await page.screenshot({ path: 'v2_check_11s.png' });

await browser.close();
console.log('\n=== V2 Debug Logs ===');
for (const l of logs) console.log(l);
console.log('===================\n완료');
