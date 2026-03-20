# IDX Swing Trading Framework — Quick Start Guide

> **DISCLAIMER**: This framework is for educational and research purposes only.
> Past performance does not guarantee future results. Trading in the stock market
> involves risk of loss. Consult a licensed financial advisor before investing.

---

## Overview

A complete, rule-based swing trading system for the Indonesia Stock Exchange (IDX)
that detects and follows institutional / "big money" movement. The system is fully
codified — no discretionary judgment required during execution.

### Architecture

```
idx_swing_trader/
├── config.py              # All parameters, thresholds, constants
├── scraper/
│   ├── price_scraper.py   # OHLCV data from Yahoo Finance
│   └── flow_scraper.py    # Foreign flow, broker summary, fundamentals
├── database/
│   ├── schema.py          # SQLAlchemy ORM models
│   └── data_loader.py     # Bulk insert/query utilities
├── signals/
│   ├── market_regime.py   # IHSG bull/bear/sideways classifier
│   ├── big_money.py       # Institutional flow detection (3 methods)
│   ├── technical.py       # RSI, MACD, EMA, ATR indicators
│   └── signal_combiner.py # Merge all signals → BUY/SELL/HOLD
├── backtest/
│   ├── engine.py          # Event-driven backtesting engine
│   ├── portfolio.py       # Position sizing & risk management
│   ├── costs.py           # IDX transaction cost model
│   └── metrics.py         # Performance metrics calculator
├── reports/
│   └── visualizer.py      # Equity curves, drawdown, heatmaps
├── main_backtest.py       # Run full backtest
├── main_daily.py          # Daily signal generator (live)
└── requirements.txt
```

---

## Step 1: Install Dependencies

```bash
# Python 3.10+ required
pip install -r requirements.txt
```

## Step 2: Initialise Database

The database is created automatically on first run. By default it uses SQLite
(`idx_swing_trader.db` in the project directory).

For PostgreSQL, set the environment variable:
```bash
export IDX_DB_URL="postgresql://user:pass@localhost/idx_swing"
```

## Step 3: Scrape Historical Data & Run Backtest

```bash
# Full run: scrape + backtest (first time — takes ~30-60 minutes)
cd idx_swing_trader
python main_backtest.py --scrape --start 2021-01-01 --end 2024-12-31

# Subsequent runs (data already in DB)
python main_backtest.py --start 2021-01-01 --end 2024-12-31

# Custom tickers and capital
python main_backtest.py --tickers BBCA BBRI TLKM --capital 500000000

# Debug mode (verbose logging)
python main_backtest.py --log-level DEBUG
```

## Step 4: Interpret Results

After the backtest completes, check the `reports/` directory:

| File                    | Description                                      |
|-------------------------|--------------------------------------------------|
| `metrics_summary.txt`   | Full performance report (returns, risk, trades)   |
| `equity_curve.png`      | Strategy vs IHSG buy-and-hold                     |
| `drawdown.png`          | Drawdown from peak chart                          |
| `monthly_heatmap.png`   | Monthly returns colour-coded grid                 |
| `trade_distribution.png`| PnL histogram + exit reason breakdown             |
| `trade_log.csv`         | Every trade with entry/exit/PnL details           |

### Key Metrics to Focus On

- **CAGR > IHSG CAGR**: The system should outperform buy-and-hold
- **Sharpe > 1.0**: Good risk-adjusted returns
- **Max Drawdown < -25%**: Acceptable for IDX swing trading
- **Win Rate > 45%**: Combined with favourable avg-win/avg-loss ratio
- **Profit Factor > 1.5**: Gross wins significantly exceed gross losses

## Step 5: Daily Signal Generator (Live Use)

Run after market close each day to get fresh signals:

```bash
python main_daily.py

# Or for specific tickers
python main_daily.py --tickers BBCA BBRI BMRI TLKM ASII
```

Output shows:
- Current market regime (BULL / SIDEWAYS / BEAR)
- BUY signals with composite score, RSI, volume
- SELL signals for stocks showing distribution

---

## Customisation Guide

### Adjust Parameters

All parameters are in `config.py`. Key ones to tune:

| Parameter | Location | Default | Effect |
|-----------|----------|---------|--------|
| `risk_per_trade` | PositionSizingConfig | 2% | Higher = larger positions |
| `max_positions` | PositionSizingConfig | 8 | More diversification |
| `score_entry_threshold` | BigMoneyConfig | 0.55 | Lower = more signals |
| `stop_loss_pct` | ExitConfig | 7% | Wider = fewer stop-outs |
| `time_exit_max_days` | ExitConfig | 20 | Longer = more patience |

### Add Real Broker Data

If you have broker summary data from RTI Business or a broker platform:

```python
from scraper.flow_scraper import FlowScraper
from database.schema import create_all_tables, get_session

engine = create_all_tables("sqlite:///idx_swing_trader.db")
session = get_session(engine)

scraper = FlowScraper()
scraper.import_foreign_flow_csv(session, "path/to/foreign_flow.csv", "BBCA")
scraper.import_broker_summary_csv(session, "path/to/broker_summary.csv", "BBCA")
```

Expected CSV format for foreign flow:
```
date,foreign_buy_value,foreign_sell_value,foreign_buy_volume,foreign_sell_volume
2024-01-02,50000000000,30000000000,1000000,600000
```

### Swap Big Money Detection Method

The modular design lets you replace any signal component. For example, to add
a custom institutional detection method:

```python
# In signals/big_money.py, add a new method:
def _custom_method_score(self, price_df, custom_data):
    # Your logic here
    return score_series  # pd.Series, 0.0 to 1.0

# Then update compute_composite_score to include it
```

---

## Framework Decision Rules Summary

### When to BUY
ALL of these must be true simultaneously:
1. Market regime is BULL or SIDEWAYS (not BEAR)
2. Big money composite score ≥ 0.55
3. Price > 50-day EMA
4. RSI between 40 and 70
5. MACD histogram > 0
6. Today's volume ≥ 1.2× 20-day average
7. Portfolio has room (< 8 positions, < 80% invested, < 30% in sector)

### When to SELL (first trigger wins)
1. Price hits stop-loss (7% below entry or 2× ATR)
2. Trailing stop hit (after +10% profit, trail at 2.5× ATR)
3. Partial sell: 50% of position at +15% profit
4. No +5% move within 20 trading days
5. Big money score drops below 0.25 (distribution)
6. Market regime shifts to BEAR

### Position Sizing
- Risk 2% of equity per trade
- Size = (2% of equity) / (2× ATR)
- Capped at 15% of equity per position
- Rounded to IDX lot size (100 shares)
