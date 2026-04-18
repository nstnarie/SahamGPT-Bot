# IDX Swing Trader — Automation, Telegram & Optimisation Guide (Step 8)

> **DISCLAIMER**: Educational and research purposes only. Past performance does not guarantee future results.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                 DAILY AUTOMATION                      │
│                                                       │
│  16:30 WIB (cron/scheduler)                          │
│      │                                                │
│      ▼                                                │
│  ┌─────────┐    ┌──────────┐    ┌──────────────────┐ │
│  │ Scrape   │───▶│ Compute  │───▶│ Rank Top 5       │ │
│  │ Yahoo    │    │ Signals  │    │ by composite      │ │
│  │ Finance  │    │ (regime, │    │ score             │ │
│  └─────────┘    │  big $,  │    └────────┬─────────┘ │
│                 │  tech)   │             │            │
│                 └──────────┘             ▼            │
│                              ┌──────────────────────┐ │
│                              │ Claude API           │ │
│                              │ (generate reasoning) │ │
│                              └──────────┬───────────┘ │
│                                         │             │
│                                         ▼             │
│                              ┌──────────────────────┐ │
│                              │ Telegram Bot         │ │
│                              │ → Your phone         │ │
│                              └──────────────────────┘ │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│              WEEKEND OPTIMISATION                     │
│                                                       │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────┐ │
│  │ Walk-Forward │───▶│ Test combos  │───▶│ Update  │ │
│  │ Windows     │    │ Train → Test │    │ config  │ │
│  └─────────────┘    └──────────────┘    └─────────┘ │
└─────────────────────────────────────────────────────┘
```

---

## Part 1: Telegram Bot Setup (15 minutes)

### Step 1: Create the Bot

1. Open Telegram, search for **@BotFather**
2. Send `/newbot`
3. Follow prompts — give it a name like "IDX Signal Bot"
4. Copy the **bot token** (looks like `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

### Step 2: Get Your Chat ID

1. Send any message to your new bot in Telegram
2. Open this URL in your browser (replace YOUR_TOKEN):
   ```
   https://api.telegram.org/botYOUR_TOKEN/getUpdates
   ```
3. Find `"chat":{"id":123456789}` — that number is your **chat ID**

### Step 3: Set Environment Variables

Add these to your shell profile (`~/.bashrc`, `~/.zshrc`, or `.env`):

```bash
export TELEGRAM_BOT_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
export TELEGRAM_CHAT_ID="123456789"

# Optional: enables AI-powered reasoning in messages
export ANTHROPIC_API_KEY="sk-ant-api03-..."
```

### Step 4: Test It

```bash
cd idx_swing_trader
python -c "
from notifications.telegram_notifier import send_telegram_message
send_telegram_message('<b>Test</b> — IDX Bot is working! 🚀', parse_mode='HTML')
"
```

You should receive a message on your phone immediately.

---

## Part 2: Daily Automation

### Option A: Cron Job (Recommended for Linux/Mac)

```bash
# Edit crontab
crontab -e

# Add this line — runs at 16:30 WIB (09:30 UTC) every weekday
30 9 * * 1-5 cd /path/to/idx_swing_trader && /usr/bin/python3 main_daily.py >> /var/log/idx_daily.log 2>&1
```

> **Why 16:30 WIB?** IDX session 2 closes at 16:15. We wait 15 minutes for
> Yahoo Finance to update, then run.

### Option B: Built-in Scheduler (Runs Continuously)

```bash
# Runs in foreground, executes at 16:30 WIB on weekdays
python main_daily.py --scheduler

# Custom time
python main_daily.py --scheduler --schedule-time 17:00

# Run in background with nohup
nohup python main_daily.py --scheduler > scheduler.log 2>&1 &
```

### Option C: Systemd Service (Production Linux)

```bash
# Create service file
sudo nano /etc/systemd/system/idx-trader.service
```

```ini
[Unit]
Description=IDX Swing Trader Daily Scheduler
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/idx_swing_trader
Environment="TELEGRAM_BOT_TOKEN=your-token"
Environment="TELEGRAM_CHAT_ID=your-chat-id"
Environment="ANTHROPIC_API_KEY=your-key"
ExecStart=/usr/bin/python3 main_daily.py --scheduler
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable idx-trader
sudo systemctl start idx-trader
sudo systemctl status idx-trader  # check it's running
```

### Option D: Cloud VPS (Always-On)

For a laptop that isn't always on, use a cheap VPS:
- **DigitalOcean**: $4/month droplet
- **Hetzner**: €3.79/month
- **Oracle Cloud**: Free tier (always free ARM instance)

Install Python, clone the project, set up cron or systemd.

### What the Daily Pipeline Does

Each run:
1. Scrapes latest prices from Yahoo Finance (~5-10 min for 137 stocks)
2. Applies 20-day breakout detection with volume spike filter
3. Runs MA200, ATR%, and KSEI foreign flow hard filters
4. Computes composite signal quality score for all breakout signals
5. Applies rolling 6-entry-per-10-day throttle (selects highest ranked only)
6. Sends top picks to Telegram with AI reasoning
7. Logs everything to `daily_pipeline.log`

### What You Receive on Telegram

```
📊 IDX SWING TRADER
2026-03-20 16:35 WIB

Market Regime: 🟢 BULL (exposure: 100%)
IHSG: 7,250

🟢 TOP BUY SIGNALS

1. BBCA — Rp 9,500
   Score: 0.78 | RSI: 55 | Vol: 2.1x

2. TLKM — Rp 3,200
   Score: 0.65 | RSI: 48 | Vol: 1.8x

3. BMRI — Rp 6,800
   Score: 0.62 | RSI: 52 | Vol: 1.5x

📝 Analysis
• BBCA — Strong foreign accumulation driving the
  score. Volume spike on up-days consistent with
  institutional buying. RSI at 55 gives room to
  run. Watch for resistance at 9,700.

• TLKM — Volume-price analysis strongest component.
  OBV trending up while price consolidates near
  support. Good risk-reward at current level.
  ...

──────────────────────────────
⚠️ Educational/research only. Not financial advice.
```

---

## Part 3: Backtest & Optimise the Formula

### Why You Need Walk-Forward Optimisation

If you optimise parameters on 3 years of data and test on the SAME 3 years,
you'll get amazing results that won't work in real trading. This is called
**overfitting**.

Walk-forward solves this by:
- Training on older data
- Testing on newer data the system has NEVER seen
- Repeating across multiple time windows
- The combined out-of-sample results = realistic performance

### Step 1: Initial Backtest (Baseline)

```bash
# First time: scrape data + run backtest with default parameters
python main_backtest.py --scrape --start 2024-01-01 --end 2024-12-31

# Or on GitHub Actions: Actions → Analyze Trade Log → Run workflow
# Downloads trade_analysis.md artifact with full breakdown
```

Check `reports/metrics_summary.txt` for baseline performance.
Expected: 2024 PF ~1.40, Return ~+6%, 2025 PF ~1.75, Return ~+15%.

### Step 2: Run Walk-Forward Optimisation

```bash
# Conservative grid (27 combinations × 4 windows ≈ 108 backtests)
# Takes 10-30 minutes depending on hardware
python main_optimise.py --start 2021-01-01 --end 2024-12-31 \
    --param-grid conservative

# Quick validation (4 combinations × 4 windows ≈ 16 backtests)
python main_optimise.py --param-grid minimal

# More thorough search
python main_optimise.py --param-grid aggressive

# Custom window sizes
python main_optimise.py --train-months 12 --test-months 6 --step-months 3
```

### Step 3: Interpret the Results

The optimiser outputs a table like:

```
── PER-WINDOW OUT-OF-SAMPLE RESULTS ──
Window   Period                         Return     Sharpe      MaxDD   Trades
  1      2022-07-01 → 2022-12-31         8.2%       1.24      -6.3%      12
  2      2023-01-01 → 2023-06-30         5.1%       0.87      -8.1%      15
  3      2023-07-01 → 2023-12-31        -2.3%      -0.31     -12.5%       9
  4      2024-01-01 → 2024-06-30        11.7%       1.56      -5.2%      18

── AGGREGATE ──
  Avg OOS Return:       5.7% (± 5.1%)
  Avg OOS Sharpe:       0.84 (± 0.68)

── RECOMMENDED PARAMETERS ──
  big_money.score_entry_threshold    = 0.55
  exit.stop_loss_pct                 = 0.07
  exit.time_exit_max_days            = 20
```

**What to look for:**
- **Consistent OOS Sharpe > 0.5** across windows → real edge
- **Wildly varying results** → strategy is fragile, be cautious
- **Recommended params close to defaults** → defaults are robust
- **Train performance much better than test** → overfitting

### Step 4: Apply the Recommended Parameters

Open `config.py` and update the values:

```python
# Before (defaults)
score_entry_threshold: float = 0.55

# After (from optimisation)
score_entry_threshold: float = 0.50  # if that's what was recommended
```

Then re-run the backtest to confirm:
```bash
python main_backtest.py --start 2021-01-01 --end 2024-12-31
```

### Step 5: Periodic Re-Optimisation

Run the optimiser monthly or quarterly to check if parameters need updating:

```bash
# Add to cron — runs at midnight on the 1st of each month
0 0 1 * * cd /path/to/idx_swing_trader && python main_optimise.py \
    --param-grid conservative >> /var/log/idx_optimise.log 2>&1
```

---

## Part 4: Complete Automation Timeline

| When | What | Command |
|------|------|---------|
| **One-time setup** | Install, scrape 3yr data | `pip install -r requirements.txt && python main_backtest.py --scrape` |
| **One-time setup** | Run initial optimisation | `python main_optimise.py --param-grid conservative` |
| **One-time setup** | Configure Telegram bot | Set env vars, test send |
| **Daily 16:30 WIB** | Auto: scrape + signal + Telegram | `python main_daily.py` (via cron) |
| **Monthly 1st** | Auto: re-optimise parameters | `python main_optimise.py` (via cron) |
| **Quarterly** | Manual: review performance, adjust universe | Check logs, update LQ45 list |

---

## Troubleshooting

**"No data loaded"**
- Run `python main_backtest.py --scrape` first to populate the database

**Telegram message not received**
- Check bot token and chat ID
- Make sure you've sent at least one message TO the bot first
- Test: `curl "https://api.telegram.org/botYOUR_TOKEN/getMe"`

**Claude API reasoning not working**
- Works fine without it (uses rule-based explanations)
- If you want AI reasoning: check `ANTHROPIC_API_KEY` is set
- API costs: ~$0.01 per daily run (Sonnet, ~500 tokens)

**Yahoo Finance rate limiting**
- The scraper has built-in delays (1s between requests)
- If you hit limits, increase `request_delay` in config.py
- 45 stocks × 1s = ~1 minute total scrape time

**Optimisation takes too long**
- Use `--param-grid minimal` for quick tests
- Reduce tickers: `--tickers BBCA BBRI TLKM BMRI ASII`
- Reduce windows: `--train-months 12 --test-months 3`
