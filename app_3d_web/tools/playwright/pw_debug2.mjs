import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.setViewportSize({ width: 1400, height: 800 });

const errors = [];
page.on('console', msg => {
  if (msg.type() === 'error') errors.push(msg.text());
});

await page.goto('http://localhost:5173/', { waitUntil: 'networkidle', timeout: 30000 });

const btns = await page.$$('button');
for (const b of btns) {
  const t = await b.textContent();
  if (t && t.includes('비교')) { await b.click(); break; }
}

await page.waitForTimeout(5000);

const v2dbg = errors.filter(e => e.includes('V2-DBG'));
console.log('V2 debug logs:', v2dbg.join('\n'));

await page.screenshot({ path: 'C:/Project/VR-Based-Real-Time-Agent/screenshot_debug.png' });
await browser.close();
