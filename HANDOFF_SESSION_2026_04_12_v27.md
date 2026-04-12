# SahamGPT-Bot — Session Handoff Document
> Last updated: April 12, 2026 (v27 — Phase B Step 6: Loss Trade Pattern Analysis)
> Repo: https://github.com/nstnarie/SahamGPT-Bot (public, Python 100%)
> Paste this at the start of a new chat to resume seamlessly.

---

## CLAUDE: READ THIS BEFORE DOING ANYTHING

1. **Read `DEVELOPER_CONTEXT.py`** — locked rules, hard parameters.
2. **`idx-database` is shared** — NEVER run workflows in parallel.
3. **Branch is `main`** — Phase A changes fully merged.
4. **Phase A is COMPLETE** — 93% mega-winner capture (103/111). Do NOT re-open Phase A work.
5. **Current task: Phase B Step 6** — implement two entry filters identified from statistical analysis.

---

## 1. The 9-Step Plan — Status

**Phase A — Capture mega winners (Steps 1-5): ✅ COMPLETE**
- System catches 93% of mega-winners (103/111 identified)
- Key changes made: breakout period=20, FF entry gate removed, universe expanded to 147 tickers
- See Section 2 for detailed Phase A findings and rationale

**Phase B — Filter out losers (Steps 6-9): 🔄 IN PROGRESS — Step 6**
- Step 6: Analyze loss trades → find entry patterns → implement filters (THIS SESSION)
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
- Statistical basis: rolling capture rate analysis showed N=20 optimal

### Step 2: FF Entry Gate Removed (ff_confirmed no longer required for BUY)
- Foreign flow at trough has **d = -0.0001** — zero predictive power for entry quality
- Foreigners are NET SELLING during mega-winner troughs (they exit, retail buys)
- BTPS and KLBF had valid breakout signals blocked by FF gate — both would have been winners
- FF stays as **exit-only** signal: `ff_consecutive_sell >= 5 → SELL` (untouched)
- Code location: `signals/signal_combiner.py` `_evaluate_signal()` ~line 228

### Step 2: Indicator Effect Sizes at TROUGH (mega-winners vs non-mega-winners)
These are the indicators that discriminate whether a stock WILL become a mega-winner.
Different from Phase B which looks at entry-time indicators for trade outcome.

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
- Reason: 8 of the biggest mega-winners (DEWA, WIFI, SMDR, CUAN, ENRG, BREN, WIIM, KRAS) were missing from original universe

### Infrastructure: Artifact Pipeline Fix
- **Bug fixed:** `scrape_broker_summary.yml` was downloading from its own runs only, overwriting price data from `initial_scrape.yml`
- **Fix:** `search_artifacts: true` in `scrape_broker_summary.yml` + removed `workflow:` filter
- **Rule:** Only `initial_scrape.yml` should upload `idx-database`. `run_backtest.yml` downloads from `initial_scrape.yml` explicitly.

### Why RSI/MACD Were Removed from Entry (v11)
- Old filter: RSI 40-75 AND MACD > 0 required for BUY
- **They blocked 80% of mega-winners** — mega-winners at trough have very low RSI and negative MACD
- These indicators are still computed but NOT used for entry decisions
- Do NOT add them back as entry filters

---

## 3. Current Backtest Baselines (v14 framework, separate year runs)

| Metric | 2024 | 2025 | 2021-2025 (5yr) |
|--------|------|------|-----------------|
| Trades | 152 | 143 | 156 |
| Win Rate | 31.6% | 39.2% | 40.4% |
| Total Return | -18.46% | +16.78% | +32.34% |
| CAGR | -21.46% | +20.58% | +6.00% |
| Profit Factor | 0.55 | 1.34 | 1.62 |
| Max Drawdown | -19.47% | -7.04% | -6.22% |
| Exposure | 77.3% | 67.0% | 28.3% |
| Alpha vs IHSG | -17.53% | -4.92% | NaN (data gap) |

**Key problem:** 65% of all trades are losers (191/295 combined 2024+2025).

---

## 4. Phase B Step 6 — Analysis Results

Statistical analysis of 295 trades using full 2021-2025 price DB (`/tmp/full_db/idx_swing_trader.db`, 165,782 rows, 137 tickers). Analysis script: `/tmp/phase_b_analysis.py`.

### Top Discriminating Indicators (Cohen's d, winners vs losers)

| Indicator | 2024 d | 2025 d | Consistent? | Interpretation |
|-----------|--------|--------|-------------|----------------|
| breakout_strength | +0.98 | +0.61 | YES | #1 signal — losers close BELOW 20d high |
| price_vs_ma20 | +0.57 | +0.51 | YES | Winners further above MA20 |
| price_vs_ma50 | +0.41 | +0.54 | YES | Winners further above MA50 |
| rsi_14 | +0.44 | +0.45 | YES | Winners enter at higher RSI |
| prior_return_5d | +0.66 | +0.42 | YES | Short-term momentum matters |
| prior_return_10d | +0.52 | +0.37 | YES | Medium-term momentum |
| volume_ratio | +0.77 | +0.19 | YES | Volume confirmation |
| dist_from_52w_high | +0.32 | +0.37 | YES | Closer to 52w high = better |
| consec_up_days | +0.62 | +0.22 | YES | Momentum streak |

**Key insight:** ALL consistent indicators are positive — winners enter with MORE momentum,
not less. The losers are weak/false breakouts, not over-extended stocks.

### Cleanest Entry Filter Found

| Filter | Trades blocked | Losers blocked | Big winners lost | BW% kept |
|--------|---------------|---------------|-----------------|----------|
| 52w_high < -40% | 22 total | 19 | **0** | **100%** |
| ATR < 1.5% | 7 total | 7 | **0** | **100%** |

**`dist_from_52w_high < -40%`** is the highest-confidence filter: stocks more than 40% below
their 52-week high that trigger a breakout almost always fail. Zero big winners were ever
in this bucket across both 2024 and 2025.

### Exit Reason Breakdown

| Exit | WR | Interpretation |
|------|-----|----------------|
| TREND_EXIT | ~99% | The "good" exit — catches true mega-winners |
| PARTIAL_PROFIT | 100% | Fires at +15% |
| REGIME_EXIT | ~60% | BEAR regime protection |
| STOP_LOSS | ~13% | 87% of these are losses — main problem |
| EMERGENCY_STOP | 0% | Always -13% avg — worst outcome |
| TIME_EXIT | ~15% | Usually small losses |

**STOP_LOSS + EMERGENCY_STOP account for 85% of all losses.**

### Holding Period Pattern (consistent both years)

| Period | 2024 WR | 2025 WR |
|--------|---------|---------|
| 1-3 days | 37.5% | 50.0% |
| 4-5 days | 21.4% | 33.3% |
| **6-10 days (dead zone)** | **20.5%** | **16.4%** |
| 11-15 days | 53.8% | 58.3% |
| 21+ days | 100% | 100% |

---

## 5. Phase B Step 6 — Implementation Plan

**Plan file:** `~/.claude/plans/golden-rolling-reddy.md`

### 3 Files to Modify

**File 1: `signals/technical.py`** — Add 52-week high computation inside `compute_all_indicators()`:
```python
df["high_252d"] = df["high"].rolling(window=252, min_periods=60).max()
df["dist_from_52w_high"] = (df["close"] / df["high_252d"] - 1) * 100
```

**File 2: `config.py`** — Add new dataclass after `EntryConfig`:
```python
@dataclass
class EntryFilterConfig:
    max_dist_from_52w_high: float = -40.0   # block deep-discount breakouts
    min_breakout_strength: float = 0.0       # require actual close above 20d high
    use_52w_filter: bool = True
    use_breakout_strength_filter: bool = True
```
Add `entry_filter: EntryFilterConfig = field(default_factory=EntryFilterConfig)` to `FrameworkConfig`.

**File 3: `signals/signal_combiner.py`** — Apply filters inside `_add_breakout_signals()` before `df["is_breakout"] = ...`:
```python
ef = self.config.entry_filter
if ef.use_52w_filter and "dist_from_52w_high" in df.columns:
    is_breakout = is_breakout & (df["dist_from_52w_high"] >= ef.max_dist_from_52w_high)
if ef.use_breakout_strength_filter:
    breakout_strength = (df["close"] / df["high_Nd"] - 1) * 100
    df["breakout_strength"] = breakout_strength
    is_breakout = is_breakout & (breakout_strength >= ef.min_breakout_strength)
df["is_breakout"] = is_breakout
```

### After Code Changes

1. Commit + push to main
2. Trigger `run_backtest.yml` for:
   - 2024-01-01 to 2024-12-31 (verify improvement from PF 0.55)
   - 2025-01-01 to 2025-12-31 (verify no regression)
   - 2021-01-01 to 2025-12-31 (full period)

### Verification Targets

- [ ] 2024 profit factor improves from 0.55 (target: >0.7)
- [ ] 2025 win rate stays ≥39%, big winners ≥30
- [ ] GJTL (2024: 0% WR, -11.1% avg) filtered out
- [ ] Big winners (CUAN, BREN, WIFI) still appear in trade log
- [ ] `dist_from_52w_high` column present in signal output

### Rollback

Set `use_52w_filter: False` and `use_breakout_strength_filter: False` in config — no code revert needed.

---

## 6. Codebase Structure (key files)

| File | Role |
|------|------|
| `signals/signal_combiner.py` | Entry/exit signal logic. `_evaluate_signal()` at line ~228, `_add_breakout_signals()` at line ~79 |
| `signals/technical.py` | All indicator computation (`compute_all_indicators()` line ~22) |
| `config.py` | All configuration dataclasses |
| `backtest/engine.py` | Backtest loop, `pending_entries` queue, gap filters |
| `backtest/portfolio.py` | Position sizing, exit logic (lines 158-251) |
| `scraper/price_scraper.py` | Stock universe `LQ45_TICKERS` (~147 tickers) |
| `.github/workflows/run_backtest.yml` | Main backtest CI — downloads DB from `initial_scrape.yml` |

---

## 7. What NOT to Do

- Do NOT run idx-database workflows in parallel
- Do NOT re-open Phase A work (mega-winner capture is at 93% — acceptable)
- Do NOT add RSI/MACD back as entry filters (they blocked 80% of mega-winners — v11 removed them intentionally)
- Do NOT run `scrape_broker_summary.yml` while a backtest is in progress

---

*End of v27. Next action: implement 3 code changes above, then run backtests.*
