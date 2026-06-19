import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1280, 'height': 900})
        await page.goto('http://localhost:5173', wait_until='networkidle', timeout=15000)

        # Fill text input (not file input)
        txt = page.locator('input[placeholder]')
        await txt.fill('Toi la Bac si lam sang, lam sao chung minh cong viec co tam quan trong quoc gia voi My?')
        await page.screenshot(path='screenshots/ui_input.png')

        # Send message
        await txt.press('Enter')
        await asyncio.sleep(2)
        await page.screenshot(path='screenshots/ui_sending.png')

        # Wait for streaming status text
        try:
            await page.wait_for_selector('text=Đang', timeout=8000)
            await page.screenshot(path='screenshots/ui_streaming.png')
            print('Streaming started')
        except Exception as e:
            print(f'No streaming status: {e}')
            await page.screenshot(path='screenshots/ui_no_stream.png')

        # Wait for final response (90s)
        try:
            await page.wait_for_function(
                "document.querySelectorAll('.msg-bubble').length >= 2",
                timeout=90000
            )
            await asyncio.sleep(1)
            await page.screenshot(path='screenshots/ui_response.png')
            print('Response received')
        except Exception as e:
            print(f'Timeout waiting: {e}')
            await page.screenshot(path='screenshots/ui_timeout.png')

        await browser.close()

asyncio.run(main())
