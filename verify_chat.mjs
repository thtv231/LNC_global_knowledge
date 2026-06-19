import { chromium } from 'playwright';
import { writeFileSync } from 'fs';

const URL = 'https://lnc-chatbot-v1.vercel.app';
const SCREENSHOTS = 'C:\\graph_knowledge\\screenshots';
import { mkdirSync } from 'fs';
try { mkdirSync(SCREENSHOTS, { recursive: true }); } catch {}

const browser = await chromium.launch({
  channel: 'chrome',
  headless: false,
  args: ['--no-sandbox', '--disable-setuid-sandbox'],
});

const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
const page = await ctx.newPage();

// Capture console errors
page.on('console', msg => { if (msg.type() === 'error') console.log('CONSOLE ERR:', msg.text()); });
page.on('pageerror', err => console.log('PAGE ERR:', err.message));

console.log('1. Opening', URL);
await page.goto(URL, { waitUntil: 'networkidle', timeout: 30000 });
await page.screenshot({ path: `${SCREENSHOTS}\\01_initial.png`, fullPage: false });
console.log('   Screenshot: 01_initial.png');

// Print page title + check visible text
const title = await page.title();
console.log('   Page title:', title);
const bodyText = await page.locator('body').innerText().catch(() => '(no body text)');
console.log('   Body preview:', bodyText.slice(0, 200));

// Find input/textarea for chat
const inputSel = 'textarea, input[type="text"], input[placeholder], [contenteditable="true"]';
const inputs = await page.locator(inputSel).all();
console.log(`\n2. Found ${inputs.length} input(s)`);

let chatInput = null;
for (const inp of inputs) {
  const vis = await inp.isVisible();
  const ph = await inp.getAttribute('placeholder').catch(() => '');
  console.log(`   - visible=${vis} placeholder="${ph}"`);
  if (vis) chatInput = inp;
}

if (!chatInput) {
  await page.screenshot({ path: `${SCREENSHOTS}\\02_no_input.png` });
  console.log('ERROR: No visible chat input found');
  await browser.close();
  process.exit(1);
}

console.log('\n3. Typing test message...');
await chatInput.click();
await chatInput.fill('Xin chào, tôi muốn hỏi về visa du lịch Canada');
await page.screenshot({ path: `${SCREENSHOTS}\\02_typed.png` });

// Submit: try Enter or find a send button
const sendBtn = page.locator('button[type="submit"], button:has-text("Gửi"), button:has-text("Send"), button[aria-label*="send" i]').first();
const hasSend = await sendBtn.isVisible().catch(() => false);
if (hasSend) {
  console.log('   Clicking send button...');
  await sendBtn.click();
} else {
  console.log('   Pressing Enter to send...');
  await chatInput.press('Enter');
}

await page.screenshot({ path: `${SCREENSHOTS}\\03_sent.png` });
console.log('   Message sent. Waiting for response (up to 45s)...');

// Wait for a response to appear — look for assistant/bot message
try {
  await page.waitForFunction(() => {
    const els = document.querySelectorAll('[class*="message"], [class*="chat"], [class*="assistant"], [class*="bot"], [class*="response"], [class*="answer"]');
    for (const el of els) {
      if (el.textContent && el.textContent.length > 50) return true;
    }
    return false;
  }, { timeout: 45000 });
  console.log('   Response appeared!');
} catch {
  console.log('   Timeout waiting for message selector — checking page content anyway');
}

await page.screenshot({ path: `${SCREENSHOTS}\\04_response.png`, fullPage: true });
const finalText = await page.locator('body').innerText().catch(() => '');
console.log('\n4. Final page text (first 800 chars):\n', finalText.slice(0, 800));

// Check for error messages
const hasError = finalText.toLowerCase().includes('error') || finalText.toLowerCase().includes('lỗi') || finalText.toLowerCase().includes('failed');
console.log('\n5. Has error text:', hasError);

await browser.close();
console.log('\nDone. Screenshots saved to', SCREENSHOTS);
