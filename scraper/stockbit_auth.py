"""
Stockbit Auto-Login via Playwright
======================================
Uses a real headless browser to log into Stockbit, bypassing reCAPTCHA v3.

reCAPTCHA v3 is score-based (no puzzle). It watches browser behavior to decide
if the user is human. Playwright with stealth plugin looks like a real browser,
so reCAPTCHA v3 gives it a high score and lets the login through.

Usage:
    token = get_stockbit_token("your_email", "your_password")
    # token is the Bearer JWT, valid for ~24 hours

Required packages:
    pip install playwright playwright-stealth
    playwright install chromium

In GitHub Actions, add to your workflow:
    - name: Install Playwright
      run: |
        pip install playwright playwright-stealth
        playwright install chromium --with-deps
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
    """
    Log into Stockbit using a real browser and extract the JWT token.

    Args:
        username: Stockbit email (or STOCKBIT_USERNAME env var)
        password: Stockbit password (or STOCKBIT_PASSWORD env var)
        headless: Run browser without visible window
        timeout_ms: Max time to wait for login (milliseconds)

    Returns:
        JWT token string (without "Bearer " prefix), or None on failure.
    """
    from playwright.sync_api import sync_playwright

    # Handle different playwright-stealth versions
    stealth_available = False
    stealth_sync_fn = None
    try:
        # Old API (playwright-stealth2, tf-playwright-stealth)
        from playwright_stealth import stealth_sync as _stealth_sync
        stealth_sync_fn = _stealth_sync
        stealth_available = True
    except ImportError:
        try:
            # New API (playwright-stealth >= 2.0)
            from playwright_stealth import Stealth
            stealth_available = True
        except ImportError:
            stealth_available = False

    username = username or os.getenv("STOCKBIT_USERNAME", "")
    password = password or os.getenv("STOCKBIT_PASSWORD", "")

    if not username or not password:
        logger.error("Set STOCKBIT_USERNAME and STOCKBIT_PASSWORD env vars")
        return None

    token = None

    try:
        with sync_playwright() as p:
            # Launch real Chromium browser
            browser = p.chromium.launch(
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ]
            )

            context = browser.new_context(
                viewport={"width": 1366, "height": 768},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/145.0.0.0 Safari/537.36"
                ),
                locale="en-US",
            )

            page = context.new_page()

            # Apply stealth to avoid bot detection
            if stealth_available:
                if stealth_sync_fn:
                    # Old API: stealth_sync(page)
                    stealth_sync_fn(page)
                else:
                    # New API: Stealth class
                    try:
                        stealth = Stealth()
                        stealth.apply_stealth_sync(context)
                    except Exception as e:
                        logger.warning(f"Stealth apply failed: {e}. Continuing without stealth.")
            else:
                logger.warning("No stealth plugin available. Bot detection may trigger.")

            # Capture the auth token from API responses
            captured_token = {"value": None}

            def handle_response(response):
                """Intercept API responses to capture the JWT token."""
                url = response.url
                # The login response contains the token
                if "login" in url and response.status == 200:
                    try:
                        body = response.json()
                        t = body.get("data", {}).get("access_token", "")
                        if not t:
                            t = body.get("data", {}).get("token", "")
                        if t:
                            captured_token["value"] = t
                            logger.info("Captured auth token from login response")
                    except Exception:
                        pass

            def handle_request(request):
                """Intercept outgoing requests to capture auth header."""
                auth = request.headers.get("authorization", "")
                if auth.startswith("Bearer ey") and not captured_token["value"]:
                    captured_token["value"] = auth.replace("Bearer ", "")
                    logger.info("Captured auth token from request header")

            page.on("response", handle_response)
            page.on("request", handle_request)

            # Navigate to Stockbit login page
            logger.info("Opening Stockbit login page...")
            page.goto("https://stockbit.com/login", wait_until="networkidle")
            time.sleep(2)  # Let reCAPTCHA v3 initialize

            # Find and fill the email field
            logger.info("Filling login form...")
            email_input = page.locator('input[type="text"], input[type="email"], input[name="username"], input[placeholder*="email" i], input[placeholder*="user" i]').first
            email_input.wait_for(timeout=timeout_ms)
            email_input.click()
            time.sleep(0.5)
            email_input.fill(username)
            time.sleep(0.5)

            # Find and fill the password field
            password_input = page.locator('input[type="password"]').first
            password_input.click()
            time.sleep(0.5)
            password_input.fill(password)
            time.sleep(1)  # Let reCAPTCHA v3 observe "human" behavior

            # Click the login button
            logger.info("Clicking login...")
            login_button = page.locator('button[type="submit"], button:has-text("Login"), button:has-text("Masuk"), button:has-text("Sign In")').first
            login_button.click()

            # Wait for navigation or token capture
            logger.info("Waiting for login response...")
            try:
                page.wait_for_url("**/home**", timeout=timeout_ms)
                logger.info("Login successful — redirected to home")
            except Exception:
                # Might not redirect, but token could still be captured
                time.sleep(5)

            # If token wasn't captured from login response, try to get it
            # from subsequent API calls by navigating to a stock page
            if not captured_token["value"]:
                logger.info("Token not captured from login, trying stock page...")
                page.goto("https://stockbit.com/symbol/BBCA", wait_until="networkidle")
                time.sleep(3)

            # Also try to extract from cookies or localStorage
            if not captured_token["value"]:
                try:
                    cookies = context.cookies()
                    for cookie in cookies:
                        if cookie["name"] in ("access_token", "token", "sb_token"):
                            captured_token["value"] = cookie["value"]
                            logger.info(f"Captured token from cookie: {cookie['name']}")
                            break
                except Exception:
                    pass

            if not captured_token["value"]:
                try:
                    ls_token = page.evaluate("""
                        () => {
                            return localStorage.getItem('access_token') 
                                || localStorage.getItem('token')
                                || localStorage.getItem('sb_access_token')
                                || '';
                        }
                    """)
                    if ls_token:
                        captured_token["value"] = ls_token
                        logger.info("Captured token from localStorage")
                except Exception:
                    pass

            token = captured_token["value"]
            browser.close()

    except Exception as e:
        logger.error(f"Playwright login error: {e}")
        return None

    if token:
        logger.info(f"Token obtained successfully (length: {len(token)})")
        # Verify it looks like a JWT
        if token.startswith("eyJ"):
            return token
        else:
            logger.warning(f"Token doesn't look like a JWT: {token[:20]}...")
            return token
    else:
        logger.error("Failed to capture auth token. Login may have failed.")
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    token = get_stockbit_token()
    if token:
        print(f"\nToken (first 50 chars): {token[:50]}...")
        print(f"Token length: {len(token)}")
        print("\nFull token (copy this to STOCKBIT_TOKEN if needed):")
        print(token)
    else:
        print("\nFailed to get token. Check your credentials.")
