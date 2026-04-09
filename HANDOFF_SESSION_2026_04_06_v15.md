# SahamGPT-Bot — Session Handoff Document
> Last updated: April 9, 2026 (v16 — 2024 backfill COMPLETE, split files updated, ready for Step 2)
> Repo: https://github.com/nstnarie/SahamGPT-Bot (public, Python 100%)
> Paste this at the start of a new chat to resume seamlessly.

---

## ⚠️ CLAUDE: READ THIS BEFORE DOING ANYTHING

1. **Read `DEVELOPER_CONTEXT.py` first** — locked rules, hard parameters, architectural decisions.
2. **Never answer workflow questions without reading the actual .yml files first.**
3. **`idx-database` is shared** — `scrape_broker_summary.yml`, `initial_scrape.yml`, `bootstrap_database.yml`, `daily_signals.yml`. **NEVER run in parallel.**
4. **Data loss is unrecoverable.** When in doubt, stop and ask Arie.

---

## 1. Baselines

### v9 — main branch baseline
| Metric | Value |
|--------|-------|
| Trades | 45 |
| Win Rate | 37.8% |
| Total Return | +12.74% (+Rp 127M) |
| Profit Factor | **2.14** |
| Max Drawdown | -3.28% |
| Sharpe | 0.89 |
| Calmar | **4.16** |

### feature/v10-experiments — current baseline (post Exp 4)
| Metric | Value |
|--------|-------|
| Trades | 41 |
| Win Rate | **41.5%** |
| Total Return | +14.55% (+Rp 145M) |
| Profit Factor | **2.52** |
| Max Drawdown | -3.37% |
| Sharpe | **1.11** |
| Sortino | **1.93** |
| Calmar | **4.59** |

---

## 2. What Happened This Session (April 5–6, 2026)

### Trade Log Loss Analysis (done in Opus)
Full analysis of all 28 losing trades (-Rp 103M total) from v9 backtest.
5 new experiments queued (Exp 6–10) based on patterns found:
- Pattern 1: Apr-May cluster (-Rp 27.8M, 7 straight losses) → Exp 6
- Pattern 2: Re-entry after exhaustion → Exp 4 (already done)
- Pattern 3: Emergency stops (ESSA, HRUM, EMTK Oct) → Exp 8, 10
- Pattern 4: Financial sector correlation (-Rp 18.4M) → Exp 7
- Pattern 5: TIME_EXIT dead trades (-Rp 11.1M) → Exp 9

### Experiments Run This Session
| Exp | Description | Run ID | Result |
|-----|-------------|--------|--------|
| 4 | Post-TREND_EXIT cooldown 30d | 24005616009 | ✅ ACCEPTED — PF +0.19, +Rp 8M |
| 5 | Remove Rp 150 min price filter | 24005950325 | ❌ REJECTED — WTON+GOTO both emergency stopped |
| 6 | IHSG 5-day momentum filter | 24006068747 | ❌ REJECTED — too backward-looking, -Rp 68M |
| 7 | Financial sector entry limit | 24006206306 | ❌ REJECTED — zero effect, banks naturally spread |

### 2024 Q2 Batch 3 — STILL RUNNING
- Run 24003326023, tickers 51–74, Apr 1→Jun 30
- Started ~14:15 WIB Apr 5, expected ~4h — should complete soon
- **Do NOT trigger batch 4 until this is confirmed complete**

---

## 3. Entry / Exit Rules (feature/v10-experiments)

### Entry (ALL must be true)
| # | Condition | Value |
|---|-----------|-------|
| 1 | Resistance breakout | Close > 60-day high |
| 2 | Volume spike | 1.5x–5.0x 20-day avg |
| 3 | Uptrend | Close > 50-day MA |
| 4 | Min price | >= Rp 150 |
| 5 | No selling pressure | Upper shadow < 40%, close upper 2/3 |
| 6 | Foreign flow trend | 5-day FF sum > 0, breakout day not net sell *(if `is_foreign_driven`)* |
| 7 | RSI | 40–75 |
| 8 | MACD | Histogram > 0 |
| 9 | Regime | Not BEAR + IHSG > MA20 + IHSG daily > -1% *(Exp 2)* |
| 10 | No gap-up | Entry day open not >7% above signal day close |
| 11 | Cluster limit | Max 5 new entries in rolling 10 trading days |

### Exit (first trigger wins)
| Priority | Rule |
|----------|------|
| 1 | -12% emergency stop (always) |
| 2 | No stop first 5 days |
| 3 | Close < MA10 after +15% gain |
| 4 | -7% or 1.5xATR, cap -10% — hold extension if acc_score > 0 on days 6–10 |
| 5 | Sell 30% at +15% |
| 6 | No +3% in 15 days + below MA10 |
| 7 | 5 consecutive net foreign sell days (foreign-driven, price weakening) |
| 8 | BEAR regime = close all |

### Re-entry Cooldown (Exp 4)
| Exit Type | Cooldown |
|-----------|----------|
| STOP_LOSS | 30 trading days |
| TREND_EXIT | 30 trading days *(NEW — Exp 4)* |

---

## 4. Architecture

### Two execution paths — NEVER cross-contaminate
- BACKTEST: `main_backtest.py → backtest/engine.py`
- LIVE: `main_daily.py → signals/signal_combiner.py`

### Key files changed in feature/v10-experiments (accepted: Exp 2 + Exp 4)
- `signals/market_regime.py`: adds `ihsg_entry_ok` (Exp 2)
- `signals/signal_combiner.py`: gates BUY on `ihsg_entry_ok` (Exp 2)
- `backtest/engine.py`: cooldown on `STOP_LOSS OR TREND_EXIT` (Exp 4)

### run_backtest.yml from feature branch
Safe while scraper runs — idx-database upload gated: `if: always() && github.ref == 'refs/heads/main'`

---

## 5. Database State

- **broker_summary:** 2,071,251 records, 2024-01-02 → 2025-12-30
- **Q1 2024:** COMPLETE ✅
- **Q2 2024:** COMPLETE ✅ (Apr 6, 2026)
- **Q3 2024:** COMPLETE ✅ (Apr 8, 2026)
- **Q4 2024:** COMPLETE ✅ (Apr 9, 2026) — 5 runs, split files updated
- **daily_prices:** 107 tickers, 2021-01-01 to 2026-03-28 (new tickers not yet scraped)
- **Split files:** `idx_broker_part_a.db` (1,269,996) + `idx_broker_part_b.db` (801,255) = 2,071,251 ✅

---

## 6. Workflows

All workflows touching idx-database must run **sequentially, never in parallel.**

| File | Touches idx-database? | Purpose |
|------|-----------------------|---------|
| `daily_signals.yml` | ✅ | Full pipeline → Telegram (weekday 16:35 WIB) |
| `initial_scrape.yml` | ✅ | Historical price download |
| `run_backtest.yml` | ✅ | On-demand backtesting |
| `scrape_broker_summary.yml` | ✅ | Batch broker data scraping |
| `export_summary.yml` | ❌ | Export per-day ticker count CSV |
| `bootstrap_database.yml` | ✅ | Merges split files into artifact |
| `update_split_files.yml` | ❌ | Regenerates split files |

---

## 7. Next Steps (in order)

### ⚠️ EXPERIMENT STRATEGY — IMPORTANT DECISION (Apr 6, 2026)
All v10 experiments (Exp 8, 9, 10 and any re-tests) are **ON HOLD** until the full dataset is ready:
- ~~Full 2024 broker summary data~~ ✅ DONE (Apr 9, 2026)
- Full 2025 broker summary data (already complete) ✅
- Price + broker data for 27+ new tickers (initial_scrape + scrape_broker_summary pending) ⬜
- Then: re-run ALL experiments (including re-tests of Exp 4, 7) against the complete 2024+2025 universe ⬜

Reason: results on partial/old-universe data will be invalidated once the full dataset is ready. No point running Exp 8–10 twice.

### ✅ COMPLETE — 2024 Broker Data Backfill (109 original tickers)
```
Q1 2024: ✅ COMPLETE
Q2 2024: ✅ COMPLETE (Apr 6, 2026) — 1,518,834 total records
Q3 2024: ✅ COMPLETE (Apr 8, 2026) — 1,805,857 total records, split files updated

Q4 2024: ✅ COMPLETE (Apr 9, 2026)
         ✅ batch 1 (tickers 1-25, Oct 1→Dec 31) run 24111084856 — +79,207
         ✅ batch 2 (tickers 26-50, Oct 1→Dec 31) run 24119625128 — +62,137
         ✅ batch 3 (tickers 51-75, Oct 1→Dec 31) run 24131152829 — +53,737
         ✅ batch 4 pt1 (tickers 76-109, Oct 1→Nov 15) run 24145458928 — +40,359
         ✅ batch 4 pt2 (tickers 76-109, Nov 16→Dec 31) run 24153250161 — +29,954
         ✅ export_summary.yml → update_split_files.yml (Apr 9, 2026)
```
Final: **2,071,251 records** | part_a 1,269,996 + part_b 801,255 ✅

### AFTER 2024 BACKFILL — TICKER UNIVERSE EXPANSION ✅ (scraper/price_scraper.py updated Apr 6)
LQ45_TICKERS expanded from **109 → 136 tickers**. 27 added, based on price + liquidity check (yfinance, 30d avg):

**Batch 1 (high-liquidity):** AADI, ADMR, BREN, BRIS, CUAN, DEWA, PANI, PSAB, RAJA, RATU, WIFI

**Batch 2 (additional screening):** ADHI, AGRO, AMAN, ARGO, ARTO, ASSA, AVIA, BNBA, DOID, ENRG, IMAS, KRAS, POWR, SMBR, SMDR, WIIM

**Not added:** MLPL(Rp91), ABBA(Rp44), ACST(Rp98), BKSL(Rp108) — sub-Rp150 / AMAR, CMNP, MCAS — too thin (<Rp1B/day)

**Added Apr 9, 2026:** INET (Rp 258, Rp 106B/day ✅) — added to feature branch Batch 3

⚠️ **ENRG: verify price manually** — yfinance shows Rp 1500 (historically ~Rp 100-200). May be split-adjusted.

**Remaining steps after 2024 backfill:**
1. `initial_scrape.yml` — OHLCV 2021-01-01→present for 27 new tickers
2. `scrape_broker_summary.yml` with tickers override, 2024-01-01→2025-12-31 (sequential batches)
3. `export_summary.yml` → `update_split_files.yml` → push to main

### v10 EXPERIMENTS — STATUS

> ⚠️ **ALL PENDING EXPERIMENTS ON HOLD** — Will redo the entire experiment suite once the full dataset is ready: 2024+2025 broker summary + price data for all 136 tickers. Results on partial/old-universe data will be invalidated.

**Current baseline (post Exp 4, 2025 data only, 109 tickers): 41t | 41.5% WR | PF 2.52 | +Rp 145M | DD -3.37% | Calmar 4.59**

| # | Experiment | Status |
|---|------------|--------|
| ~~1~~ | Emergency stop -12% → -10% | ❌ REJECTED (run 23982773904) — re-test on full data |
| ~~2~~ | IHSG market filter (daily) | ✅ ACCEPTED (run 23982879523) — re-test on full data |
| ~~3~~ | FF magnitude filter | ❌ REJECTED (run 23982978951) — re-test on full data |
| ~~4~~ | Post-TREND_EXIT cooldown 30d | ✅ ACCEPTED (run 24005616009) — re-test on full data |
| ~~5~~ | Remove Rp 150 min price filter | ❌ REJECTED (run 24005950325) — likely stays rejected |
| ~~6~~ | IHSG 5d momentum filter | ❌ REJECTED (run 24006068747) — likely stays rejected |
| ~~7~~ | Financial sector entry limit | ❌ REJECTED (run 24006206306) — re-test on full data (may fire in 2024) |
| **8** | Breakout margin filter (close ≥1-2% above 60d high) | ⏸ ON HOLD — pending full data |
| **9** | Early no-follow-through exit (no +1% by day 8) | ⏸ ON HOLD — pending full data |
| **10** | ATR/price volatility cap (ATR > 5% of close → skip) | ⏸ ON HOLD — pending full data |
| 7a | Support/resistance detection | ⬜ ON HOLD (post-integration) |
| 7b | Averaging up on resistance break | ⬜ ON HOLD (needs 7a) |
| 7c | Chart pattern detection | ⬜ ON HOLD (needs 7a) |

### INTEGRATION (after full data + experiment re-run complete)
- Merge `feature/v10-experiments` → `main` (accepted experiments only)
- Run `run_backtest.yml` from main to confirm stable post-merge
- Integrate into live path (`main_daily.py → signal_combiner.py`)
- Update `daily_signals.yml` with live broker scraping
- Paper trade 1 month → go live
