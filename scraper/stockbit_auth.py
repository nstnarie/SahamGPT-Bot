"""
Stockbit Auto-Login via Playwright v3
========================================
With diagnostic screenshots and exhaustive token capture methods.
"""

import json
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)


def get_stockbit_token(
    username: str = None,
    password: str = None,
    headless: bool = True,
    timeout_ms: int = 30000,
) -> Optional[str]:
    from playwright.sync_api import sync_playwright

    # Try importing stealth
    stealth_fn = None
    try:
        from playwright_stealth import stealth_sync
        stealth_fn = stealth_sync
    except ImportError:
        logger.warning("stealth_sync not available, continuing without stealth")

    username = username or os.getenv("STOCKBIT_USERNAME", "")
    password = password or os.getenv("STOCKBIT_PASSWORD", "")

    if not username or not password:
        logger.error("Set STOCKBIT_USERNAME and STOCKBIT_PASSWORD")
        return None

    token = None
    captured = {"token": None}

    # Track ALL responses for debugging
    all_responses = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=headless,
                args=["--disable-blink-features=AutomationControlled",
                      "--no-sandbox", "--disable-dev-shm-usage"]
            )

            context = browser.new_context(
                viewport={"width": 1366, "height": 768},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
                locale="en-US",
            )

            page = context.new_page()

            if stealth_fn:
                stealth_fn(page)

            # ── Intercept ALL network traffic ──
            def on_response(response):
                url = response.url
                status = response.status
                all_responses.append(f"{status} {url[:100]}")

                # Capture token from ANY exodus API response
                if "exodus.stockbit.com" in url and status == 200:
                    try:
                        body = response.json()
                        # Try multiple possible token locations
                        for path in [
                            lambda b: b.get("data", {}).get("access_token"),
                            lambda b: b.get("data", {}).get("token"),
                            lambda b: b.get("access_token"),
                            lambda b: b.get("token"),
                        ]:
                            t = path(body)
                            if t and isinstance(t, str) and len(t) > 50:
                                captured["token"] = t
                                logger.info(f"TOKEN CAPTURED from response: {url[:80]}")
                                return
                    except Exception:
                        pass

            def on_request(request):
                auth = request.headers.get("authorization", "")
                if auth.startswith("Bearer ey") and not captured["token"]:
                    captured["token"] = auth[7:].strip()
                    logger.info(f"TOKEN CAPTURED from request header: {request.url[:80]}")

            page.on("response", on_response)
            page.on("request", on_request)

            # ── Step 1: Go to login page ──
            logger.info("Step 1: Opening login page...")
            page.goto("https://stockbit.com/login", wait_until="networkidle")
            time.sleep(3)
            page.screenshot(path="/tmp/sb_01_login_page.png")
            logger.info(f"  Current URL: {page.url}")

            # ── Step 2: Fill email ──
            logger.info("Step 2: Filling email...")
            # Try multiple selectors
            email_filled = False
            for selector in [
                'input[name="username"]',
                'input[type="email"]',
                'input[type="text"]',
                'input[placeholder*="email" i]',
                'input[placeholder*="user" i]',
                'input[placeholder*="Email" i]',
            ]:
                try:
                    el = page.locator(selector).first
                    if el.is_visible(timeout=2000):
                        el.click()
                        time.sleep(0.3)
                        el.fill(username)
                        email_filled = True
                        logger.info(f"  Email filled using: {selector}")
                        break
                except Exception:
                    continue

            if not email_filled:
                logger.error("  Could not find email input field!")
                page.screenshot(path="/tmp/sb_02_no_email_field.png")
                browser.close()
                return None

            time.sleep(0.5)

            # ── Step 3: Fill password ──
            logger.info("Step 3: Filling password...")
            pwd_input = page.locator('input[type="password"]').first
            pwd_input.click()
            time.sleep(0.3)
            pwd_input.fill(password)
            time.sleep(1)
            page.screenshot(path="/tmp/sb_03_form_filled.png")

            # ── Step 4: Click login ──
            logger.info("Step 4: Clicking login button...")
            login_clicked = False
            for selector in [
                'button[type="submit"]',
                'button:has-text("Login")',
                'button:has-text("Masuk")',
                'button:has-text("Sign In")',
                'button:has-text("Log In")',
            ]:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible(timeout=2000):
                        btn.click()
                        login_clicked = True
                        logger.info(f"  Clicked: {selector}")
                        break
                except Exception:
                    continue

            if not login_clicked:
                logger.error("  Could not find login button!")
                page.screenshot(path="/tmp/sb_04_no_button.png")
                browser.close()
                return None

            # ── Step 5: Wait for response ──
            logger.info("Step 5: Waiting for login response (35s)...")
            # Wait longer and check periodically
            for i in range(7):
                time.sleep(5)
                if captured["token"]:
                    logger.info(f"  Token captured after {(i+1)*5}s!")
                    break
                logger.info(f"  ...{(i+1)*5}s elapsed, URL: {page.url[:60]}")

            page.screenshot(path="/tmp/sb_05_after_login.png")
            logger.info(f"  URL after login: {page.url}")

            # ── Step 6: If no token yet, try navigating to stock page ──
            if not captured["token"]:
                logger.info("Step 6: Navigating to BBCA page to trigger API calls...")
                page.goto("https://stockbit.com/symbol/BBCA/chartbit", wait_until="networkidle")
                time.sleep(5)
                page.screenshot(path="/tmp/sb_06_bbca_page.png")

            # ── Step 7: Try cookies ──
            if not captured["token"]:
                logger.info("Step 7: Checking cookies...")
                cookies = context.cookies()
                cookie_names = [c["name"] for c in cookies]
                logger.info(f"  Cookie names: {cookie_names}")
                for cookie in cookies:
                    if "token" in cookie["name"].lower() or "access" in cookie["name"].lower() or "auth" in cookie["name"].lower():
                        logger.info(f"  Found potential token cookie: {cookie['name']} = {cookie['value'][:30]}...")
                        if len(cookie["value"]) > 50:
                            captured["token"] = cookie["value"]
                            logger.info(f"  TOKEN CAPTURED from cookie: {cookie['name']}")
                            break

            # ── Step 8: Try localStorage ──
            if not captured["token"]:
                logger.info("Step 8: Checking localStorage...")
                try:
                    ls_keys = page.evaluate("() => Object.keys(localStorage)")
                    logger.info(f"  localStorage keys: {ls_keys}")
                    for key in ls_keys:
                        if "token" in key.lower() or "access" in key.lower() or "auth" in key.lower() or "jwt" in key.lower():
                            val = page.evaluate(f"() => localStorage.getItem('{key}')")
                            if val and len(str(val)) > 50:
                                captured["token"] = str(val)
                                logger.info(f"  TOKEN CAPTURED from localStorage: {key}")
                                break
                except Exception as e:
                    logger.warning(f"  localStorage check failed: {e}")

            # ── Step 9: Try sessionStorage ──
            if not captured["token"]:
                logger.info("Step 9: Checking sessionStorage...")
                try:
                    ss_keys = page.evaluate("() => Object.keys(sessionStorage)")
                    logger.info(f"  sessionStorage keys: {ss_keys}")
                    for key in ss_keys:
                        val = page.evaluate(f"() => sessionStorage.getItem('{key}')")
                        if val and isinstance(val, str) and val.startswith("eyJ"):
                            captured["token"] = val
                            logger.info(f"  TOKEN CAPTURED from sessionStorage: {key}")
                            break
                except Exception as e:
                    logger.warning(f"  sessionStorage check failed: {e}")

            # ── Debug: Log all API responses we saw ──
            if not captured["token"]:
                logger.error("FAILED to capture token. Network responses seen:")
                for resp in all_responses[-30:]:
                    logger.error(f"  {resp}")

            token = captured["token"]
            browser.close()

    except Exception as e:
        logger.error(f"Playwright error: {type(e).__name__}: {e}")
        return None

    if token:
        logger.info(f"SUCCESS — Token length: {len(token)}")
        return token
    else:
        logger.error("FAILED — No token captured from any source")
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    token = get_stockbit_token()
    if token:
        print(f"\nToken: {token[:50]}...")
    else:
        print("\nFailed. Check logs above.")
