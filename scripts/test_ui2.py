import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1280, 'height': 900})
        await page.goto('http://localhost:5173', wait_until='networkidle', timeout=15000)

        # Send message
        txt = page.locator('input[placeholder]')
        await txt.fill('Toi la Bac si lam sang, lam sao chung minh cong viec co tam quan trong quoc gia voi My?')
        await txt.press('Enter')

        # Wait for streaming to finish — watch for content in AI bubble to stop changing
        print('Waiting for response...')
        prev_content = ''
        stable_count = 0
        for _ in range(120):  # up to 120s
            await asyncio.sleep(1)
            try:
                content = await page.inner_text('.msg-bubble:last-child')
                if content and content == prev_content and 'Đang' not in content:
                    stable_count += 1
                    if stable_count >= 2:
                        break
                else:
                    stable_count = 0
                prev_content = content
            except Exception:
                pass

        await asyncio.sleep(0.5)
        await page.screenshot(path='screenshots/ui_final.png', full_page=True)
        print('Final screenshot saved')
        print('Content preview:', prev_content[:200])
        await browser.close()

asyncio.run(main())
