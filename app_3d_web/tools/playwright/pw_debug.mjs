import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.setViewportSize({ width: 1400, height: 800 });

// Capture all console messages
const logs = [];
page.on('console', msg => logs.push(`[${msg.type()}] ${msg.text()}`));

await page.goto('http://localhost:5173/', { waitUntil: 'networkidle', timeout: 30000 });

// Click compare button
const btns = await page.$$('button');
for (const b of btns) {
  const t = await b.textContent();
  if (t && t.includes('비교')) {
    await b.click();
    break;
  }
}

// Wait 20 seconds (frame ~160 in 32s loop = deep squat)
await page.waitForTimeout(20000);
await page.screenshot({ path: 'C:/Project/VR-Based-Real-Time-Agent/screenshot_frame160.png' });

// Print console logs (look for V2 warnings)
const v2logs = logs.filter(l => l.includes('V2') || l.includes('bone') || l.includes('warn'));
console.log('V2 relevant logs:', v2logs.slice(0, 20).join('\n'));
console.log('Total logs:', logs.length);

await browser.close();
