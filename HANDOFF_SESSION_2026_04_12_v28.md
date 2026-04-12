# SahamGPT-Bot — Session Handoff Document
> Last updated: April 12, 2026 (v28 — Phase B Step 6: Filters implemented, 2021-2025 backtest pending)
> Repo: https://github.com/nstnarie/SahamGPT-Bot (public, Python 100%)
> Paste this at the start of a new chat to resume seamlessly.

---

## CLAUDE: READ THIS BEFORE DOING ANYTHING

1. **Read `DEVELOPER_CONTEXT.py`** — locked rules, hard parameters.
2. **`idx-database` is shared** — NEVER run workflows in parallel.
3. **Branch is `main`** — all changes merged to main.
4. **Phase A is COMPLETE** — 93% mega-winner capture (103/111). Do NOT re-open Phase A work.
5. **Current task: Phase B Step 6** — filters implemented, 2021-2025 backtest in progress.

---

## 1. The 9-Step Plan — Status

**Phase A — Capture mega winners (Steps 1-5): ✅ COMPLETE**
- System catches 93% of mega-winners (103/111 identified)
- Key changes: breakout period=20, FF entry gate removed, universe expanded to 147 tickers

**Phase B — Filter out losers (Steps 6-9): 🔄 IN PROGRESS — Step 6**
- Step 6: Analyze loss trades → implement entry filters → verify (THIS SESSION — nearly done)
- Steps 7-9: pending

---

## 2. Phase A — Key Findings & Decisions (DO NOT REVERT)

### Step 1: Mega-Winner Definition
- **111 mega-winners identified** across 2024+2025 (stocks with >50% trough-to-peak gain)
- Algorithm: O(n) max-drawup using running minimum (daily low) to daily high
- Script: `scripts/identify_mega_winners.py`, workflow: `.github/workflows/identify_mega_winners.yml`

### Step 2: Breakout Period = 20 Days (changed from 60)
- N=20 catches **100% of mega-winners** at median 13 days after trough
- N=60 missed 40%+ because the 60-day high was still too far above price at trough

### Step 2: FF Entry Gate Removed (ff_confirmed no longer required for BUY)
- Foreign flow at trough has **d = -0.0001** — zero predictive power for entry quality
- FF stays as **exit-only** signal: `ff_consecutive_sell >= 5 → SELL` (untouched)
- Code location: `signals/signal_combiner.py` `_evaluate_signal()` ~line 228

### Step 2: Indicator Effect Sizes at TROUGH (mega-winners vs non-mega-winners)

| Indicator | Cohen's d | Direction | Interpretation |
|-----------|-----------|-----------|----------------|
| prior_return_20d | +0.60 | Winners lower | Mega-winners down MORE before breakout |
| atr_pct | +0.63 | Winners higher | More volatile stocks = more upside |
| price_vs_ma50 | +0.53 | Winners lower | Further below MA50 at trough |
| breakout_strength | +0.47 | Winners higher | Stronger breakout day signal |

### Step 3: Universe Expansion
Added 3 expansion batches in `scraper/price_scraper.py` `LQ45_TICKERS` (~147 tickers total):
- **Batch 1:** AADI, ADMR, BREN, BRIS, CUAN, DEWA, PANI, PSAB, RAJA, RATU, WIFI
- **Batch 2:** ADHI, AGRO, AMAN, ARGO, ARTO, ASSA, AVIA, BNBA, DOID, ENRG, IMAS, KRAS, POWR, SMBR, SMDR, WIIM
- **Batch 3:** INET

### Why RSI/MACD Were Removed from Entry (v11)
- Old filter: RSI 40-75 AND MACD > 0 required for BUY
- **They blocked 80% of mega-winners** — mega-winners at trough have very low RSI and negative MACD
- Do NOT add them back as entry filters

---

## 3. Current Backtest Baselines (v14 framework — BEFORE Phase B changes)

| Metric | 2024 | 2025 | 2021-2025 (5yr) |
|--------|------|------|-----------------|
| Trades | 152 | 143 | 156 |
| Win Rate | 31.6% | 39.2% | 40.4% |
| Total Return | -18.46% | +16.78% | +32.34% |
| CAGR | -21.46% | +20.58% | +6.00% |
| Profit Factor | 0.55 | 1.34 | 1.62 |
| Max Drawdown | -19.47% | -7.04% | -6.22% |
| Alpha vs IHSG | -17.53% | -4.92% | NaN |

**Key problem:** 65% of all trades are losers (191/295 combined 2024+2025).

---

## 4. Phase B Step 6 — Statistical Analysis Results

Analysis of 295 trades (152 in 2024, 143 in 2025) using full 2021-2025 price DB.

### Top Discriminating Indicators (Cohen's d, winners vs losers at entry)

| Indicator | 2024 d | 2025 d | Consistent? | Interpretation |
|-----------|--------|--------|-------------|----------------|
| breakout_strength | +0.98 | +0.61 | YES | #1 signal — losers close BELOW 20d high |
| price_vs_ma20 | +0.57 | +0.51 | YES | Winners further above MA20 |
| price_vs_ma50 | +0.41 | +0.54 | YES | Winners further above MA50 |
| rsi_14 | +0.44 | +0.45 | YES | Winners enter at higher RSI |
| prior_return_5d | +0.66 | +0.42 | YES | Short-term momentum matters |
| volume_ratio | +0.77 | +0.19 | YES | Volume confirmation |
| dist_from_52w_high | +0.32 | +0.37 | YES | Closer to 52w high = better |

### Cleanest Entry Filters Found

| Filter | Trades blocked | Losers blocked | Big winners lost |
|--------|---------------|---------------|-----------------|
| dist_from_52w_high < -40% | 23 total | 20 | **0** |
| breakout_strength >= 0% | 0 effective | 0 | 0 (NO-OP) |

---

## 5. Phase B Step 6 — Implementation (DONE, commits on main)

### What Was Implemented (commit `0dff7c2`)

**`signals/technical.py`** — Added 52-week high computation:
```python
out["high_252d"] = out["high"].rolling(window=252, min_periods=60).max()
out["dist_from_52w_high"] = (out["close"] / out["high_252d"] - 1) * 100
```

**`config.py`** — Added `EntryFilterConfig` dataclass + field in `FrameworkConfig`:
```python
@dataclass
class EntryFilterConfig:
    max_dist_from_52w_high: float = -40.0
    min_breakout_strength: float = 0.0
    use_52w_filter: bool = True
    use_breakout_strength_filter: bool = False  # disabled — see below
```

**`signals/signal_combiner.py`** — Applied 52w filter in `_add_breakout_signals()`:
```python
ef = self.config.entry_filter
if ef.use_52w_filter and "dist_from_52w_high" in df.columns:
    is_breakout = is_breakout & (df["dist_from_52w_high"] >= ef.max_dist_from_52w_high)
breakout_strength = (df["close"] / df["high_Nd"] - 1) * 100
df["breakout_strength"] = breakout_strength  # always computed for Step 7 ranking
if ef.use_breakout_strength_filter:
    is_breakout = is_breakout & (breakout_strength >= ef.min_breakout_strength)
```

### Why breakout_strength Filter Was Disabled (commit `8b5c09a`)

The `breakout_strength >= 0%` filter is a **confirmed no-op**: the existing condition
`close > high_Nd` already guarantees `breakout_strength > 0`. Setting threshold at 0%
adds zero filtering. Disabled via `use_breakout_strength_filter: False`.

`breakout_strength` column is still computed and emitted for use in Step 7 signal ranking.

---

## 6. Phase B Step 6 — Backtest Results (Phase B v1 filters)

### 2024

| Metric | BEFORE | AFTER | Delta |
|--------|--------|-------|-------|
| Trades | 152 | 153 | +1 |
| Win Rate | 31.6% | 31.4% | -0.2pp |
| Profit Factor | 0.55 | 0.48 | **-0.07** |
| Total Return | -18.46% | -21.60% | **-3.14pp** |
| Alpha vs IHSG | -17.53% | -20.85% | -3.32pp |

### 2025

| Metric | BEFORE | AFTER | Delta |
|--------|--------|-------|-------|
| Trades | 143 | 146 | +3 |
| Win Rate | 39.2% | 37.0% | -2.2pp |
| Profit Factor | 1.34 | 1.34 | 0.00 |
| Total Return | +16.78% | +20.91% | **+4.13pp** |
| Alpha vs IHSG | -4.92% | +0.25% | **+5.17pp** |
| Big Winners (≥30%) | 10 | 10 | 0 |

### Key Finding: Portfolio Cascade Effect

Blocking 8-10 signals/year (each ~12% capital) cascades to **35% different trades** by year-end:
- The 52w filter IS correctly blocking losers at signal level
- But freed capital immediately fills with the next breakout signal from the same pool
- This reshuffles 46-55 trades/year — some reshuffles are positive (2025), some negative (2024)
- Database consistency confirmed: all divergence is from the filter, not data differences

**Conclusion:** Pass/fail entry filtering alone cannot reliably fix a 65% loss rate when the
portfolio is always near capacity. The right solution is signal *ranking*, not *filtering*.

---

## 7. What the 2021-2025 Run Will Tell Us

**Run ID:** 24302370877 (triggered April 12, results in GitHub Actions artifacts)
**Download:** `gh run download 24302370877 --dir /tmp/bt_full_v2`

Compare against v14 baseline:
- v14: 156 trades, 40.4% WR, PF 1.62, +32.34% return, CAGR 6.00%
- If PF and return improve → 52w filter is net-positive over full period
- If neutral/worse → confirms cascade noise dominates, need Step 7 immediately

---

## 8. Step 6 Completion Criteria

- [ ] 2021-2025 backtest analyzed (run 24302370877)
- [ ] Decision documented: keep 52w filter as-is OR adjust threshold
- [ ] Step 6 verdict written and Step 7 plan initiated

### Step 6 Is Complete When:
The 2021-2025 result is analyzed AND a clear decision is made on whether to:
- Accept the 52w filter and move to Step 7 (signal ranking)
- Or make a threshold adjustment and re-run

---

## 9. Step 7 Preview — Signal Quality Ranking

The real lever for Phase B: rank all same-day breakout signals by composite quality score,
take only top-ranked signals. This directly controls *which* trades fill the portfolio.

Phase B analysis found 4 consistently predictive features (consistent across 2024 + 2025):

| Feature | 2024 d | 2025 d | Direction |
|---------|--------|--------|-----------|
| breakout_strength | +0.98 | +0.61 | Higher = stronger |
| volume_ratio | +0.77 | +0.19 | Higher = better |
| prior_return_5d | +0.66 | +0.42 | More momentum = better |
| dist_from_52w_high | +0.32 | +0.37 | Closer to 52w high = better |

Today's engine ranks by `vol_ratio` alone (engine.py line 293). Step 7 replaces this with
a weighted composite score. This is the proper Phase B solution to the 65% loss rate problem.

---

## 10. Codebase Structure (key files)

| File | Role |
|------|------|
| `signals/signal_combiner.py` | Entry/exit signal logic. `_add_breakout_signals()` ~line 79, `_evaluate_signal()` ~line 228 |
| `signals/technical.py` | All indicator computation (`compute_all_indicators()` line ~22) |
| `config.py` | All configuration dataclasses incl. new `EntryFilterConfig` |
| `backtest/engine.py` | Backtest loop — line 293: `pending_entries[ticker] = sig_row.get("vol_ratio", 1.0)` (Step 7 target) |
| `backtest/portfolio.py` | Position sizing, exit logic (lines 158-251) |
| `scraper/price_scraper.py` | Stock universe `LQ45_TICKERS` (~147 tickers) |
| `.github/workflows/run_backtest.yml` | Main backtest CI |

---

## 11. What NOT to Do

- Do NOT run idx-database workflows in parallel
- Do NOT re-open Phase A work (mega-winner capture is at 93%)
- Do NOT add RSI/MACD back as entry filters (they blocked 80% of mega-winners)
- Do NOT tighten 52w filter below -40% (trades between -40% and -30% have avg +5.3% PnL — winners)
- Do NOT run `scrape_broker_summary.yml` while a backtest is in progress

---

*End of v28. Current state: 2021-2025 backtest running (run 24302370877). Next: analyze result, complete Step 6, plan Step 7.*
