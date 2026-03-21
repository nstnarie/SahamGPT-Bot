# IDX Swing Trading Framework v6

> **Breakout Detection + Foreign Flow Confirmation + Trend-Following Exit**

Fully automated swing trading signal system for the Indonesia Stock Exchange (IDX).
Runs on GitHub Actions (free), sends daily picks to Telegram.

**DISCLAIMER: For educational and research purposes only. Past performance does not guarantee future results.**

---

## How It Works

Every weekday at 16:35 WIB (after IDX closes), the system automatically:

1. Downloads latest prices for ~100 stocks (LQ45 + IDX SMC Liquid)
2. Identifies stocks breaking 60-day price resistance with volume spike
3. Confirms with real foreign flow data (for foreign-driven stocks)
4. Filters out selling pressure candles and gap-downs
5. Sends the top 5 picks to your Telegram with reasoning

## Entry Rules (ALL must be true)

| # | Condition | Rule |
|---|-----------|------|
| 1 | Historical resistance breakout | Close > 60-day highest high |
| 2 | Volume spike | 1.5x-5.0x of 20-day average |
| 3 | Uptrend | Close > 50-day MA |
| 4 | Minimum price | Close >= Rp 150 |
| 5 | No selling pressure | Upper shadow < 40% of range AND close in upper 2/3 |
| 6 | Foreign flow trend | 5-day FF sum positive + breakout day not net sell (foreign stocks only) |
| 7 | RSI | 40-75 |
| 8 | MACD | Histogram > 0 |
| 9 | Market regime | Not BEAR |

## Exit Rules (first trigger wins)

| Priority | Type | Rule |
|----------|------|------|
| 1 | Emergency stop | -15% loss (always active) |
| 2 | Hold period | No stop for first 5 days (let breakout develop) |
| 3 | Trend exit | Close < MA10 (for stocks that gained +15%) |
| 4 | Stop-loss | -7% or 1.5xATR, cap at -10% (after day 5) |
| 5 | Partial profit | Sell 30% at +15% |
| 6 | Time exit | No +3% in 15 days |
| 7 | FF exit | 5 consecutive days net foreign selling |
| 8 | Regime exit | BEAR = close all |

## Version History

| Version | Key Change | Result |
|---------|------------|--------|
| v1 | Synthetic big money score | -608M (broken signal) |
| v2 | Tighter -5% stop | -864M (too tight for IDX) |
| v3 | 2-day confirmation | -109M (signal still 20% accuracy) |
| v4 | Breakout + real FF rebuild | -680M (found: early stops kill profits) |
| v5 | 5-day hold, trend exit, Rp 150 min | Pending |
| **v6** | **FF trend + selling pressure filter** | **Current** |

## Deployment (GitHub Actions — Free)

| Workflow | Schedule | Purpose |
|----------|----------|---------|
| Daily IDX Signals | 16:35 WIB weekdays | Auto scrape + signal + Telegram |
| Initial Data Scrape | Manual | Download 3+ years history |
| Run Backtest | Manual | Test per year with trade log |
| Monthly Optimisation | 1st of month | Walk-forward parameter tuning |

## Monthly Cost: Rp 0 (or ~Rp 4,500 with optional AI reasoning)
