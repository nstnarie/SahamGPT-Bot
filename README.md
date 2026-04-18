# IDX Swing Trading Framework — Step 8 (v29)

> **Breakout + Signal Quality Ranking + Trend-Following Exit**

Automated swing trading signal system for Indonesia Stock Exchange (IDX). Runs on GitHub Actions (free), scrapes real broker data from Stockbit, sends daily picks to Telegram.

**DISCLAIMER: For educational and research purposes only. Past performance does not guarantee future results.**

---

## Backtest Results (Step 8, MPW=6)

| Year | Trades | Win Rate | Return | Profit Factor | Best Trade |
|------|--------|----------|--------|---------------|-----------|
| 2024 | 75 | 36% | **+6.4%** | **1.40** | ARGO +65% |
| **2025** | **98** | **46%** | **+14.9%** | **1.75** | PANI +56% |

- 2024: +6.4% vs IHSG -3.3% (alpha +9.7%)
- 2025: +14.9% vs IHSG +20.7% (note: 2025 IHSG includes Jan-Apr 2026)
- Max drawdown: ≤8.2% both years
- Core profitability: TREND_EXIT trades — 92% WR, massive average gain

---

## How It Works

Every weekday at 16:35 WIB (after IDX closes), the system:

1. Downloads prices for ~137 stocks (LQ45 + extended universe)
2. Scrapes broker summary from Stockbit (Asing/Lokal/Pemerintah flow)
3. Identifies stocks breaking **20-day resistance** with volume spike
4. Filters with MA200 and ATR% hard filters (0 big winners blocked)
5. Ranks all breakout signals by composite quality score
6. Applies rolling 6-entry-per-10-day throttle (prevents false breakout clusters)
7. Sends top picks to Telegram

---

## Entry Rules

| # | Condition | Rule | Notes |
|---|-----------|------|-------|
| 1 | Resistance breakout | Close > 20-day highest high | Was 60-day; 20d catches BW 13d earlier |
| 2 | Volume spike | 1.5x–5.0x of 20-day average | Max cap prevents pump-and-dump |
| 3 | Minimum price | Close ≥ Rp 150 | Filter penny/junk stocks |
| 4 | Not structural downtrend | Price within 10% of 200MA | d=+0.402, 0 BW lost |
| 5 | Sufficient volatility | ATR% ≥ 1.75% | d=+0.360, 0 BW lost |
| 6 | Foreign flow (FF stocks only) | 5d cumulative FF > 0, breakout day not net sell | Only for FF-driven stocks |
| 7 | KSEI outflow filter | 5d net foreign ≥ -5B IDR | Blocks 50 bad trades/yr, 0 BW lost |
| 8 | Market regime | Not BEAR | Regime from IHSG EMA + breadth |
| 9 | Entry throttle | ≤6 entries per rolling 10 days | Ranked by composite quality score |

**Removed from v6**: RSI 40-75, MACD > 0, selling pressure candle filter, 52w-high dist filter active, breakout strength filter. All blocked too many mega-winners.

---

## Exit Rules (first trigger wins)

| Priority | Type | Rule | Notes |
|----------|------|------|-------|
| 1 | Emergency stop | -12% at any time (even during hold) | Was -15%; fires at genuine disasters |
| 2 | Hold period | No stop for first 5 days | Day 1-5: 7% WR → noise. Day 6+: 49% WR |
| 3 | Trend exit (high performers) | Close < MA10 after stock gains +15% | Lets ARGO run +65%, not exit at +20% |
| 4 | Stop-loss | -7% or 1.5×ATR, cap -10% (after day 5) | Hold extension: skip once if acc_score > 0 |
| 5 | Partial profit | Sell 30% at +15% | Lock gains, let rest run |
| 6 | Time exit | No +3% in 15 days AND below MA10 | MA10 override: don't exit PGAS early |
| 7 | FF exit | 5 consecutive net-sell days (FF stocks only) | AND price below entry or MA10 |
| 8 | Regime exit | BEAR → close all | |

---

## Signal Quality Ranking

When more than 6 breakout signals fire in a 10-day window, entries are ranked by **composite quality score** (weighted percentile rank over 60-day rolling window):

| Feature | Weight | Cohen's d |
|---------|--------|-----------|
| price_vs_ma200 | 30% | +0.402 |
| atr_pct | 20% | +0.360 |
| breakout_strength | 20% | +0.266 |
| prior_return_5d | 15% | +0.358 |
| rsi | 15% | +0.328 |

Analysis based on 803 trades (2021-2025).

---

## Version History

| Step | Key Change | 2024 PF | 2025 PF |
|------|------------|---------|---------|
| v6 | FF trend + selling pressure filter | 0.68 | 1.38 |
| v9/v10 | 20-day breakout, no RSI/MACD, trend exit | — | — |
| Step 6 | Phase B entry filters (52w, MA200, ATR%) | — | — |
| Step 7 | Composite ranking score, KSEI filter | 0.81 | 1.99 |
| **Step 8** | **MPW=6 entry throttle** | **1.40** | **1.75** |

---

## File Structure

```
config.py                           # All parameters (Step 8)
signals/
  signal_combiner.py                # Breakout + ranking + FF + hard filters (v5)
  technical.py                      # RSI, MACD, EMA, ATR, price_vs_ma200
  market_regime.py                  # IHSG regime classifier (EMA + breadth)
backtest/
  engine.py                         # Event-driven backtester (v4)
  portfolio.py                      # Hold period, trend exit, hold extension (v6)
  costs.py / metrics.py             # IDX costs, performance metrics
scraper/
  price_scraper.py                  # Yahoo Finance + 137-ticker universe
  flow_scraper.py                   # Foreign flow + fundamental scraper
database/
  schema.py / data_loader.py        # SQLAlchemy ORM + data loaders
notifications/
  telegram_notifier.py              # Telegram + Claude AI reasoning
.github/workflows/
  daily_signals.yml                 # Auto daily pipeline (16:35 WIB)
  run_backtest.yml                  # On-demand backtesting with artifacts
  analyze_trade_log.yml             # Deep trade log analysis (NEW Step 8)
  initial_scrape.yml                # One-time data download
  bootstrap_database.yml            # Database setup
  scrape_broker_summary.yml         # Stockbit broker backfill
  upload_database.yml               # DB artifact management
  monthly_optimise.yml              # Parameter tuning
```

---

## GitHub Secrets

| Secret | Purpose |
|--------|---------|
| STOCKBIT_USERNAME | Stockbit email (for broker data scraping) |
| STOCKBIT_PASSWORD | Stockbit password |
| TELEGRAM_BOT_TOKEN | From @BotFather |
| TELEGRAM_CHAT_ID | Your chat ID |
| ANTHROPIC_API_KEY | Optional — Claude AI reasoning in Telegram messages |

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/nstnarie/SahamGPT-Bot.git
cd SahamGPT-Bot
pip install -r requirements.txt

# 2. Scrape data and run backtest
python main_backtest.py --scrape --start 2024-01-01 --end 2024-12-31

# 3. Check results
cat reports/metrics_summary.txt
```

Or use GitHub Actions:
- **Analyze Trade Log**: `Actions → Analyze Trade Log → Run workflow`
  - Set start/end date, run, download `trade_analysis.md` artifact
- **Run Backtest**: `Actions → Run Backtest → Run workflow`

---

## Cost: Rp 0/month (or ~Rp 4,500 with AI reasoning)
