import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        pg = await b.new_page(viewport={'width': 1280, 'height': 900})
        await pg.goto('http://localhost:5173', wait_until='networkidle', timeout=15000)
        btns = await pg.locator('button').all()
        for btn in btns:
            txt = await btn.text_content()
            if txt and 'Express' in txt:
                await btn.click()
                break
        await pg.wait_for_timeout(16000)
        await pg.screenshot(path='screenshots/final_bottom.png')
        # scroll to top of messages div
        await pg.evaluate("document.querySelector('.overflow-y-auto').scrollTop = 0")
        await pg.wait_for_timeout(400)
        await pg.screenshot(path='screenshots/final_top.png')
        print('done')
        await b.close()

asyncio.run(main())
