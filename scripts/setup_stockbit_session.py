#!/usr/bin/env python3
"""
ONE-TIME Stockbit Session Setup
================================
Run this locally whenever your session expires.

What it does:
  1. Opens a VISIBLE browser (not headless)
  2. Fills your email + password automatically
  3. Waits for you to enter the OTP code in the browser
  4. After successful login, captures session cookies
  5. Saves session to scripts/stockbit_session.json
  6. Prints the value to store as STOCKBIT_SESSION GitHub Secret

Run:
  STOCKBIT_USERNAME="your@email.com" STOCKBIT_PASSWORD="yourpassword" \
      python3 scripts/setup_stockbit_session.py
"""

import base64
import json
import os
import sys
import time
from pathlib import Path

USERNAME = os.getenv("STOCKBIT_USERNAME", "")
PASSWORD = os.getenv("STOCKBIT_PASSWORD", "")

if not USERNAME or not PASSWORD:
    print("ERROR: Set STOCKBIT_USERNAME and STOCKBIT_PASSWORD")
    sys.exit(1)

SESSION_PATH = Path(__file__).parent / "stockbit_session.json"


def setup_session():
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    token = None

    with sync_playwright() as p:
        # Non-headless — user can see the browser and enter OTP
        browser = p.chromium.launch(headless=False, slow_mo=100)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        # Intercept Bearer token from any exodus.stockbit.com request
        def on_request(request):
            nonlocal token
            if "exodus.stockbit.com" in request.url:
                auth = request.headers.get("authorization", "")
                if auth.lower().startswith("bearer ") and not token:
                    candidate = auth[7:].strip()
                    if candidate.startswith("eyJ"):
                        token = candidate
                        print(f"\n  ✅ Token intercepted from: {request.url[:60]}...")

        page.on("request", on_request)

        print("Opening browser — filling your credentials automatically ...")
        page.goto("https://stockbit.com/login", wait_until="domcontentloaded", timeout=30_000)
        time.sleep(2)

        # Fill email
        for sel in ['input[placeholder*="email" i]', 'input[type="email"]', 'input[name="email"]', 'input[name="username"]']:
            try:
                el = page.wait_for_selector(sel, timeout=3_000)
                if el:
                    page.fill(sel, USERNAME)
                    print(f"  Filled email with: {sel}")
                    break
            except PWTimeout:
                continue

        time.sleep(0.5)

        # Fill password
        for sel in ['input[type="password"]', 'input[name="password"]']:
            try:
                el = page.wait_for_selector(sel, timeout=3_000)
                if el:
                    page.fill(sel, PASSWORD)
                    print(f"  Filled password with: {sel}")
                    break
            except PWTimeout:
                continue

        time.sleep(0.5)

        # Click submit
        for sel in ['button[type="submit"]', 'button:has-text("Login")', 'button:has-text("Masuk")']:
            try:
                btn = page.wait_for_selector(sel, timeout=3_000)
                if btn:
                    btn.click()
                    print(f"  Clicked: {sel}")
                    break
            except PWTimeout:
                continue

        print()
        print("=" * 50)
        print("ACTION REQUIRED: Check the browser window.")
        print("1. Enter the OTP code sent to your email.")
        print("2. Complete any 'new device' confirmation step.")
        print("3. Wait until you reach the Stockbit home/feed page.")
        print("Waiting up to 5 minutes ...")
        print("=" * 50)

        # Wait until fully past login AND new-device pages
        try:
            page.wait_for_url(
                lambda url: "login" not in url and "new-device" not in url,
                timeout=300_000,  # 5 minutes
            )
            print(f"\n  Fully logged in! URL: {page.url}")
        except PWTimeout:
            print("\nERROR: Timed out. Make sure you completed all steps in the browser.")
            browser.close()
            sys.exit(1)

        # Extra wait for any post-login redirects to settle
        time.sleep(3)
        print(f"  Final URL: {page.url}")

        # Navigate to stock page to trigger API calls and capture token
        if not token:
            print("Navigating to stock page to capture token ...")
            page.goto(
                "https://stockbit.com/symbol/BBCA/chartbit",
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            try:
                page.wait_for_load_state("networkidle", timeout=15_000)
            except PWTimeout:
                pass
            time.sleep(5)

        # Save cookies
        cookies = context.cookies()
        print(f"  Captured {len(cookies)} cookies")

        browser.close()

    if not token:
        print("\nWARNING: Session saved but no Bearer token was intercepted.")
        print("The session cookies may still work for automated runs.")

    # Save session
    session_data = {
        "cookies": cookies,
        "token": token,
    }

    with open(SESSION_PATH, "w") as f:
        json.dump(session_data, f, indent=2, default=str)

    print(f"\nSession saved to: {SESSION_PATH}")

    # Encode for GitHub Secret
    encoded = base64.b64encode(
        json.dumps({"cookies": cookies}, default=str).encode()
    ).decode()

    print()
    print("=" * 60)
    print("NEXT STEP — Add this to GitHub Secrets as STOCKBIT_SESSION:")
    print("=" * 60)
    print()
    print("Go to: your GitHub repo → Settings → Secrets → New secret")
    print("Name:  STOCKBIT_SESSION")
    print("Value: (see stockbit_session.json — copy the full content)")
    print()
    print("Or use GitHub CLI:")
    print(f'  gh secret set STOCKBIT_SESSION < scripts/stockbit_session.json')
    print()

    # Also verify the token works
    if token:
        import requests
        resp = requests.get(
            "https://exodus.stockbit.com/marketdetectors/BBCA",
            params={
                "from": "2026-04-25", "to": "2026-04-25",
                "transaction_type": "TRANSACTION_TYPE_NET",
                "market_board": "MARKET_BOARD_REGULER",
                "investor_type": "INVESTOR_TYPE_ALL",
                "limit": 1,
            },
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "Mozilla/5.0",
                "Origin": "https://stockbit.com",
            },
            timeout=15,
        )
        if resp.status_code == 200:
            print("✅ Token verified against Stockbit API — everything works!")
        else:
            print(f"⚠️  Token captured but API returned {resp.status_code}")

    return session_data


if __name__ == "__main__":
    setup_session()
