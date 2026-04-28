"""
Stockbit Automated Authentication
===================================
Uses a saved browser session (cookies) to obtain a fresh Bearer token
without requiring manual login or OTP entry.

Session is stored in STOCKBIT_SESSION env var (GitHub Secret) as JSON,
or locally in scripts/stockbit_session.json for testing.

When the session expires, get_stockbit_token() returns None.
main_daily.py sends a Telegram alert so you know to re-run setup.
"""

import base64
import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_LOCAL_SESSION_PATH = Path(__file__).parent.parent / "scripts" / "stockbit_session.json"


def _load_session() -> Optional[dict]:
    """Load session data from env var or local file."""

    # 1. Try GitHub Secret (base64-encoded JSON)
    raw = os.getenv("STOCKBIT_SESSION", "")
    if raw:
        try:
            # Try base64 decode first
            try:
                decoded = base64.b64decode(raw).decode()
                return json.loads(decoded)
            except Exception:
                # Maybe it's plain JSON
                return json.loads(raw)
        except Exception as e:
            logger.warning(f"Failed to parse STOCKBIT_SESSION env var: {e}")

    # 2. Try local file (for local testing)
    if _LOCAL_SESSION_PATH.exists():
        try:
            with open(_LOCAL_SESSION_PATH) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load local session file: {e}")

    return None


def _verify_token(token: str) -> bool:
    """Quick API call to verify the token is still valid."""
    import requests
    try:
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
        return resp.status_code == 200
    except Exception as e:
        logger.warning(f"Token verification request failed: {e}")
        return False


def get_stockbit_token() -> Optional[str]:
    """
    Load saved Bearer token from session file and verify it is still valid.

    The token is captured once via setup_stockbit_session.py (requires OTP),
    saved as the full JWT string in STOCKBIT_SESSION env var or
    scripts/stockbit_session.json, and reused until it expires.

    Returns:
        Bearer token string if valid.
        None if token is missing or expired (triggers Telegram alert to re-run setup).
    """
    session = _load_session()
    if not session:
        logger.error(
            "No Stockbit session found. "
            "Run scripts/setup_stockbit_session.py to create one."
        )
        return None

    token = session.get("token")
    if not token or not token.startswith("eyJ"):
        logger.error(
            "Session file has no valid Bearer token. "
            "Re-run scripts/setup_stockbit_session.py to capture a fresh token."
        )
        return None

    logger.info("Verifying saved Bearer token ...")
    if _verify_token(token):
        logger.info("Bearer token is valid.")
        return token

    logger.warning(
        "Saved Bearer token has expired. "
        "Re-run scripts/setup_stockbit_session.py to refresh the session."
    )
    return None
