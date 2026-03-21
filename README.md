# IDX Swing Trading Framework v6

> **Breakout + Real Broker Summary + Trend-Following Exit**

Automated swing trading signal system for Indonesia Stock Exchange (IDX). Runs on GitHub Actions (free), scrapes real broker data from Stockbit, sends daily picks to Telegram.

**DISCLAIMER: For educational and research purposes only. Past performance does not guarantee future results.**

---

## Backtest Results (v6)

| Year | Trades | Win Rate | PnL | Profit Factor | Best Trade |
|------|--------|----------|-----|---------------|-----------|
| 2024 | 45 | 33% | Rp -37M | 0.68 | SRTG +39% |
| **2025** | **55** | **31%** | **Rp +60M** | **1.38** | **EMTK +77%** |
| Combined | 100 | 32% | Rp +23M | 1.08 | W/L ratio 2.85x |

## How It Works

Every weekday at 16:35 WIB (after IDX closes), the system:

1. Downloads prices for ~100 stocks (LQ45 + IDX SMC Liquid)
2. Scrapes broker summary from Stockbit (who's buying/selling — Asing/Lokal/Pemerintah)
3. Identifies stocks breaking 60-day resistance with volume + institutional backing
4. Filters out selling pressure candles, gap-downs, and fake breakouts
5. Sends top 5 picks to Telegram

## Entry Rules (ALL must be true)

| # | Condition | Rule |
|---|-----------|------|
| 1 | Historical resistance breakout | Close > 60-day highest high |
| 2 | Volume spike | 1.5x-5.0x of 20-day average |
| 3 | Uptrend | Close > 50-day MA |
| 4 | Minimum price | Close >= Rp 150 |
| 5 | No selling pressure | Upper shadow < 40%, close in upper 2/3 |
| 6 | Foreign flow trend | 5-day FF sum > 0, breakout day not net sell (foreign stocks) |
| 7 | RSI | 40-75 |
| 8 | MACD | Histogram > 0 |
| 9 | Market regime | Not BEAR |

## Exit Rules (first trigger wins)

| Priority | Type | Rule |
|----------|------|------|
| 1 | Emergency stop | -15% (always active, even during hold) |
| 2 | Hold period | No stop for first 5 days |
| 3 | Trend exit | Close < MA10 (after stock gains +15%) |
| 4 | Stop-loss | -7% or 1.5xATR, cap -10% (after day 5) |
| 5 | Partial profit | Sell 30% at +15% |
| 6 | Time exit | No +3% in 15 days |
| 7 | FF exit | 5 consecutive days net foreign selling |
| 8 | Regime exit | BEAR = close all |

## Version History

| Ver | Key Change | Result |
|-----|------------|--------|
| v1 | Synthetic big money score | -608M (broken signal) |
| v2 | Tighter -5% stop | -864M (too tight for IDX) |
| v3 | 2-day confirmation | -109M (signal 20% accuracy) |
| v4 | **Breakout + real FF rebuild** | -680M (found: early stops kill profits) |
| v5 | 5-day hold, trend exit, Rp 150 min | Near breakeven |
| **v6** | **FF trend + selling pressure** | **+60M in 2025 (first profit!)** |

## File Structure

```
config.py                           # All parameters (v5)
signals/
  signal_combiner.py                # Breakout + FF + candle filter (v6)
  technical.py                      # RSI, MACD, EMA, ATR
  market_regime.py                  # IHSG regime classifier
backtest/
  engine.py                         # Event-driven backtester (v5)
  portfolio.py                      # Hold period, trend exit (v5)
  costs.py / metrics.py             # IDX costs, performance metrics
scraper/
  price_scraper.py                  # Yahoo Finance + ticker list
  broker_scraper.py                 # Stockbit API scraper (NEW)
  stockbit_auth.py                  # Playwright auto-login (NEW)
database/
  schema.py                         # SQLAlchemy ORM + broker_type column
notifications/
  telegram_notifier.py              # Telegram + Claude AI
verify_broker_data.py               # Post-scrape data check
.github/workflows/
  daily_signals.yml                 # Auto daily pipeline
  initial_scrape.yml                # One-time data download
  run_backtest.yml                  # On-demand backtesting
  monthly_optimise.yml              # Parameter tuning
  scrape_broker_summary.yml         # Stockbit broker backfill (NEW)
```

## GitHub Secrets

| Secret | Purpose |
|--------|---------|
| STOCKBIT_USERNAME | Stockbit email (Playwright auto-login) |
| STOCKBIT_PASSWORD | Stockbit password |
| TELEGRAM_BOT_TOKEN | From @BotFather |
| TELEGRAM_CHAT_ID | Your chat ID |
| ANTHROPIC_API_KEY | Optional — Claude AI reasoning |

## Cost: Rp 0/month (or ~Rp 4,500 with AI reasoning)
