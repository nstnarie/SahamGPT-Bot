"""
Telegram Notifier with Claude AI Reasoning
============================================
Sends top-5 daily signals to Telegram with AI-generated explanation.

Setup:
  1. Create a Telegram bot via @BotFather → get BOT_TOKEN
  2. Send a message to your bot, then get your CHAT_ID via:
     https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
  3. (Optional) Get a Claude API key from console.anthropic.com
  4. Set environment variables:
     export TELEGRAM_BOT_TOKEN="your-bot-token"
     export TELEGRAM_CHAT_ID="your-chat-id"
     export ANTHROPIC_API_KEY="sk-ant-..."  (optional, for AI reasoning)
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-20250514"


# ──────────────────────────────────────────────────────────────
# TELEGRAM
# ──────────────────────────────────────────────────────────────

def send_telegram_message(text: str, parse_mode: str = "HTML") -> bool:
    """
    Send a message to Telegram.
    Uses HTML parse mode for bold/italic/code formatting.
    Telegram limit is 4096 chars — splits if needed.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error(
            "Telegram not configured. Set TELEGRAM_BOT_TOKEN and "
            "TELEGRAM_CHAT_ID environment variables."
        )
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    # Split long messages (Telegram max 4096 chars)
    chunks = _split_message(text, max_len=4000)

    success = True
    for chunk in chunks:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        try:
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code != 200:
                logger.error(f"Telegram API error: {resp.status_code} — {resp.text}")
                success = False
            else:
                logger.info("Telegram message sent successfully")
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            success = False

    return success


def _split_message(text: str, max_len: int = 4000) -> List[str]:
    """Split a message into chunks that fit Telegram's limit."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        # Find a good split point (newline near the limit)
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


# ──────────────────────────────────────────────────────────────
# CLAUDE API — AI REASONING FOR SIGNALS
# ──────────────────────────────────────────────────────────────

def generate_signal_reasoning(
    signals: List[Dict],
    regime: str,
    exposure: float,
) -> str:
    """
    Use Claude API to generate human-readable explanations for
    the top signals. Falls back to rule-based explanation if
    the API key is not set.

    Each signal dict contains:
        ticker, close, composite_score, rsi, volume_ratio,
        foreign_score, volume_price_score, broker_score,
        ema_50, macd_histogram, atr, signal_type (BUY/SELL)
    """
    if not ANTHROPIC_API_KEY:
        logger.info("No ANTHROPIC_API_KEY — using rule-based reasoning")
        return _rule_based_reasoning(signals, regime, exposure)

    # Build the prompt with signal data
    signal_data = json.dumps(signals, indent=2, default=str)

    prompt = f"""You are an IDX (Indonesia Stock Exchange) swing trading analyst.
Analyse these trading signals and provide a concise explanation for each.

Market Regime: {regime} (exposure multiplier: {exposure:.0%})
Date: {datetime.now().strftime('%Y-%m-%d')}

Signals (top 5 by composite score):
{signal_data}

For each signal, explain in 2-3 sentences:
1. WHY the big-money score is high/low (which component — foreign flow, volume-price, or broker activity — is driving it)
2. The technical setup (RSI level, volume confirmation, MACD direction)
3. Key risk to watch

Keep it practical and specific to each stock. Use Indonesian stock market context.
Format as a simple list with ticker headers. No markdown — plain text only.
Keep the total response under 1500 characters."""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": CLAUDE_MODEL,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )

        if resp.status_code == 200:
            data = resp.json()
            reasoning = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    reasoning += block["text"]
            return reasoning.strip()
        else:
            logger.warning(
                f"Claude API returned {resp.status_code}: {resp.text}. "
                f"Falling back to rule-based reasoning."
            )
            return _rule_based_reasoning(signals, regime, exposure)

    except Exception as e:
        logger.warning(f"Claude API call failed: {e}. Using rule-based reasoning.")
        return _rule_based_reasoning(signals, regime, exposure)


def _rule_based_reasoning(
    signals: List[Dict], regime: str, exposure: float
) -> str:
    """
    Generate explanations without Claude API, using the signal
    component scores directly.
    """
    lines = []
    for s in signals:
        ticker = s.get("ticker", "???")
        sig_type = s.get("signal_type", "BUY")
        composite = s.get("composite_score", 0)
        foreign = s.get("foreign_score", 0.5)
        vol_price = s.get("volume_price_score", 0.5)
        broker = s.get("broker_score", 0.5)
        rsi = s.get("rsi", 50)
        vol_ratio = s.get("volume_ratio", 1.0)

        # Identify the strongest driver
        drivers = {
            "foreign flow": foreign,
            "volume-price action": vol_price,
            "broker accumulation": broker,
        }
        top_driver = max(drivers, key=drivers.get)
        top_score = drivers[top_driver]

        if sig_type == "BUY":
            reason = (
                f"• {ticker} — Composite score {composite:.2f}. "
                f"Primary driver: {top_driver} ({top_score:.2f}). "
                f"RSI at {rsi:.0f} (healthy range), "
                f"volume {vol_ratio:.1f}x above average. "
            )
            if rsi > 60:
                reason += "Watch for overbought exhaustion."
            elif vol_ratio > 3:
                reason += "Unusually high volume — confirm follow-through."
            else:
                reason += "Setup looks balanced."
        else:
            reason = (
                f"• {ticker} — Distribution signal (score {composite:.2f}). "
                f"Weakest component: {top_driver} ({top_score:.2f}). "
                f"Consider reducing/exiting position."
            )

        lines.append(reason)

    return "\n\n".join(lines)


# ──────────────────────────────────────────────────────────────
# FORMAT & SEND DAILY REPORT
# ──────────────────────────────────────────────────────────────

def format_and_send_daily_report(
    buy_signals: List[Dict],
    sell_signals: List[Dict],
    regime: str,
    exposure: float,
    ihsg_close: Optional[float] = None,
) -> bool:
    """
    Format the daily signals into a Telegram message and send it.
    Includes AI-generated reasoning for the top 5 signals.
    """
    today = datetime.now().strftime("%Y-%m-%d %H:%M WIB")

    # Header
    msg_parts = [
        f"<b>📊 IDX SWING TRADER</b>",
        f"<i>{today}</i>",
        "",
        f"<b>Market Regime:</b> {_regime_emoji(regime)} {regime} "
        f"(exposure: {exposure:.0%})",
    ]

    if ihsg_close:
        msg_parts.append(f"<b>IHSG:</b> {ihsg_close:,.0f}")

    msg_parts.append("")

    # Top 5 BUY signals
    if buy_signals:
        top5 = sorted(buy_signals, key=lambda x: x["composite_score"], reverse=True)[:5]

        msg_parts.append("<b>🟢 TOP BUY SIGNALS</b>")
        msg_parts.append("")

        for i, s in enumerate(top5, 1):
            msg_parts.append(
                f"<b>{i}. {s['ticker']}</b> — "
                f"Rp {s['close']:,.0f}\n"
                f"   Score: <b>{s['composite_score']:.2f}</b> | "
                f"RSI: {s.get('rsi', 0):.0f} | "
                f"Vol: {s.get('volume_ratio', 0):.1f}x"
            )

        msg_parts.append("")

        # Generate reasoning
        for s in top5:
            s["signal_type"] = "BUY"
        reasoning = generate_signal_reasoning(top5, regime, exposure)
        msg_parts.append("<b>📝 Analysis</b>")
        msg_parts.append(f"<i>{reasoning}</i>")
        msg_parts.append("")
    else:
        msg_parts.append("No BUY signals today.")
        msg_parts.append("")

    # SELL signals
    if sell_signals:
        msg_parts.append("<b>🔴 SELL / EXIT SIGNALS</b>")
        for s in sell_signals[:5]:
            msg_parts.append(
                f"• <b>{s['ticker']}</b> — "
                f"Rp {s['close']:,.0f} (score: {s['composite_score']:.2f})"
            )
        msg_parts.append("")

    # Footer
    msg_parts.extend([
        "─" * 30,
        "<i>⚠️ Educational/research only. Not financial advice.</i>",
    ])

    full_message = "\n".join(msg_parts)

    return send_telegram_message(full_message, parse_mode="HTML")


def _regime_emoji(regime: str) -> str:
    return {"BULL": "🟢", "BEAR": "🔴", "SIDEWAYS": "🟡"}.get(regime, "⚪")


# ──────────────────────────────────────────────────────────────
# QUICK TEST
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test with sample data
    test_buys = [
        {"ticker": "BBCA", "close": 9500, "composite_score": 0.78,
         "rsi": 55, "volume_ratio": 2.1, "foreign_score": 0.82,
         "volume_price_score": 0.71, "broker_score": 0.68},
        {"ticker": "TLKM", "close": 3200, "composite_score": 0.65,
         "rsi": 48, "volume_ratio": 1.8, "foreign_score": 0.60,
         "volume_price_score": 0.72, "broker_score": 0.55},
    ]

    result = format_and_send_daily_report(
        buy_signals=test_buys,
        sell_signals=[],
        regime="BULL",
        exposure=1.0,
        ihsg_close=7250,
    )
    print(f"Send result: {result}")
