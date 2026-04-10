# SahamGPT-Bot — Session Handoff Document
> Last updated: April 10, 2026 (v24 — Step 0/1 complete + Exp 17 REJECTED, new clean baselines)
> Repo: https://github.com/nstnarie/SahamGPT-Bot (public, Python 100%)
> Paste this at the start of a new chat to resume seamlessly.

**Read order for next session:** v21 → v22 → v23 → v24 → `DEVELOPER_CONTEXT.py`

---

## ⚠️ CLAUDE: READ THIS BEFORE DOING ANYTHING

1. **Read v21–v23 first** — experiment history, mega-winner analysis, Exp 13–24 specs.
2. **Read this doc (v24)** — new correct baselines + Exp 17 result.
3. **Read `DEVELOPER_CONTEXT.py`** — locked rules, hard parameters.
4. **`idx-database` is shared** — NEVER run workflows in parallel.
5. **Branch is clean** — Exp 9/11 residue removed (Step 1 done). Exp 17 reverted. Branch is at known-good state.

---

## 1. What Happened This Session (v24)

### Step 0 — Sanity check 2024 Exp 12 baseline ✅

Downloaded run 24199627413 (34 trades). Cross-referenced against 22 mega-winners from v22 Section 2.

**Result: 5/22 traded — same capture rate as original 42-trade baseline. Exp 12 cleared.**

| Ticker | Exp 12 Result | vs Original |
|--------|---------------|-------------|
| TOTL | −8.97% STOP_LOSS | Same |
| AMMN | +1.65% TIME_EXIT | Original was −0.1% (minor) |
| WIKA | +19.6% PARTIAL + **+41.0% TREND_EXIT** | Improved (+17.5% original) |
| ADRO | −2.99% NO_FOLLOWTHROUGH | Original was +0.7% REGIME_EXIT (Exp 9 residue) |
| TINS | +15.2% TREND_EXIT | Same |

17/22 mega-winners never triggered. Exp 12 is not a suspect. The Exp 9 NO_FOLLOWTHROUGH in ADRO's exit was carryover residue.

---

### Step 1 — Cleanup Exp 9/11 residue ✅

Commit: `40a7600` — `cleanup: remove Exp 9/11 residue before Exp 13-24 sequence`

1. `backtest/portfolio.py` — removed NO_FOLLOWTHROUGH exit block
2. `backtest/engine.py` — removed NO_FOLLOWTHROUGH from cooldown condition
3. `config.py` — set `exp11_sector_filter_enabled = False`

**Effect of cleanup on baselines (important for all future experiment comparisons):**

The cleanup improved BOTH years vs the old Exp 12 baseline:
- 2024: WR 32.4% → 38.2%, PF 0.51 → 0.54, return −4.67% → −4.14%
- 2025: WR 45.7% → 48.6%, PF 3.25 → 3.63, return +16.61% → +17.70%

NO_FOLLOWTHROUGH was slightly hurting both years (cutting trades too early in some cases, letting through bigger losses in others). Removing it was net positive.

---

### Step 2 — Exp 17: Cooldown bypass on new 60d high ❌ REJECTED

**Commit added:** `2dce49a` | **Reverted:** `32107bb`

**Implementation:** When STOP_LOSS fires, record `entry_breakout_level` (the `high_Nd` broken at entry). On next BUY signal during cooldown: if signal day's close > `entry_breakout_level` → bypass 30d cooldown.

**CI Runs:**
- 2024: run 24203548317
- 2025: run 24203761354

**Results:**

| Metric | NEW Baseline | Exp 17 2024 | Exp 17 2025 |
|--------|:-----------:|:-----------:|:-----------:|
| Trades | 34 / 35 | **38** | 35 |
| Return | −4.14% / +17.70% | **−7.79%** | +17.70% |
| PF | 0.54 / 3.63 | **0.33** | 3.63 |
| Win Rate | 38.2% / 48.6% | 31.6% | 48.6% |
| Max DD | −4.84% / −3.38% | **−7.96%** | −3.38% |

**2025 was completely unaffected (0 bypasses fired in 2025).** Only 2024 was impacted.

**Root cause of failure:**
The bypass fired mechanically correct (price was above old level) but too early. TOTL was stopped Aug 5 → re-entered Aug 14 via bypass (9 days later) → EMERGENCY_STOP −13.72%. The real TOTL rally started late September/October. The bypass condition `close > old_breakout_level` is satisfied almost immediately after a stop, not just when the trend resumes.

**New trades the bypass unlocked in 2024 (all net negative):**
- TOTL re-entry Aug 14: EMERGENCY_STOP −13.72% (9 days after stop, trend hadn't resumed)
- BTPS Sep 20: EMERGENCY_STOP −13.05% (fresh entry from freed capacity)
- EMTK re-entry Dec 9: STOP_LOSS −9.06%
- PNBN Aug 29: STOP_LOSS +0.48% (was ALL-PASS in v22, still just a tiny scrape)
- BBTN×2, TLKM, ISAT, HEXA: additional stops

**Pass criteria:** 2024 PF improves OR winning-trade count up by ≥ 3.
- 2024 PF: 0.54 → 0.33 ❌
- Winning trades: 13 → 12 ❌

**Verdict: ❌ REJECTED.**

**Learning for future cooldown bypass attempts:** The price condition alone is insufficient. Any bypass needs a minimum elapsed time guard (e.g., ≥ 15 trading days) in addition to the price condition, so that "trend resumption" is confirmed by time, not just by price rebounding above the old level.

---

## 2. NEW Correct Baselines (post Step 1 cleanup, Exp 2 + 4 + 12 active)

> ⚠️ Use THESE numbers for all future experiment comparisons. The old Exp 12 baseline (run 24199627413) included Exp 9 residue and is OBSOLETE.

### feature/v10-experiments — 109 tickers, real_broker=true

| Metric | 2025 | 2024 |
|--------|------|------|
| Trades | **35** | **34** |
| Win Rate | **48.6%** | **38.2%** |
| Total Return | **+17.70%** | **−4.14%** |
| Profit Factor | **3.63** | **0.54** |
| Max Drawdown | **−3.38%** | **−4.84%** |
| Sharpe | **1.54** | **−1.78** |
| Sortino | **3.01** | **−2.20** |
| Calmar | **5.64** | **−0.91** |
| Run ID | **24220636277** | **24220505468** |

### v9 main branch (reference, unchanged)
45 trades | 37.8% WR | PF 2.14 | +12.74% | DD −3.28% | Sharpe 0.89 | Calmar 4.16

**Primary improvement target: 2024 PF from 0.54 → >1.0 without 2025 regression beyond −2pp.**

---

## 3. Codebase State (HEAD: 32107bb)

### Active experiments in feature/v10-experiments:
- **Exp 2:** IHSG market filter (`signals/market_regime.py`)
- **Exp 4:** Post-TREND_EXIT + post-STOP_LOSS 30d cooldown (`backtest/engine.py`)
- **Exp 12:** Consecutive loss throttle (`backtest/engine.py`)

### Clean removals (Step 1):
- Exp 9 NO_FOLLOWTHROUGH exit block: **REMOVED** from `backtest/portfolio.py`
- Exp 9 cooldown condition: **REMOVED** from `backtest/engine.py`
- Exp 11 flag: **FALSE** in `config.py`

### No pending cleanup before Exp 18.

---

## 4. Experiment Queue (updated)

| # | Experiment | Status | 2024 Run | 2025 Run | 2024 Return | 2024 PF | 2025 Return | 2025 PF |
|:-:|---|:---:|:-:|:-:|:-:|:-:|:-:|:-:|
| 0 | **Clean baseline** | ✅ | 24220505468 | 24220636277 | **−4.14%** | **0.54** | **+17.70%** | **3.63** |
| 1 | **Exp 17** Cooldown bypass new 60d high | ❌ REJECTED | 24203548317 | 24203761354 | −7.79% | 0.33 | +17.70% | 3.63 |
| 2 | **Exp 18** A-tier cluster exemption | ⏸ next | TBD | TBD | TBD | TBD | TBD | TBD |
| 3 | **Exp 19** Volatility stops for trend leaders | ⏸ | TBD | TBD | TBD | TBD | TBD | TBD |
| 4 | **Exp 21** Re-entry after shake-out | ⏸ | TBD | TBD | TBD | TBD | TBD | TBD |
| 5 | **Exp 13** RSI upper bound removed | ⏸ | TBD | TBD | TBD | TBD | TBD | TBD |
| 6 | **Exp 14** Volume cap removed | ⏸ | TBD | TBD | TBD | TBD | TBD | TBD |
| 7 | **Exp 13+14** combined | ⏸ | TBD | TBD | TBD | TBD | TBD | TBD |
| 8 | **Exp 20** Liquidity floor | ⏸ | TBD | TBD | TBD | TBD | TBD | TBD |
| 9 | **Exp 16** Simplified IHSG gate | ⏸ | TBD | TBD | TBD | TBD | TBD | TBD |
| 10 | **Exp 15** MA20 trail after +25% | ⏸ | TBD | TBD | TBD | TBD | TBD | TBD |
| 11 | **Exp 22** Disable TIME_EXIT for RS leaders | ⏸ | TBD | TBD | TBD | TBD | TBD | TBD |
| 12 | **Exp 23** Pyramid-add on winners | ⏸ | TBD | TBD | TBD | TBD | TBD | TBD |
| 13 | **Exp 24** Auto-cluster sector tailwind | ⏸ | TBD | TBD | TBD | TBD | TBD | TBD |
| 14 | **Full stack** of ACCEPTED experiments | ⏸ | TBD | TBD | TBD | TBD | TBD | TBD |

---

## 5. Exp 18 Spec (NEXT — from v23 Section 8)

### Exp 18 — A-tier cluster exemption

**Hypothesis:** Leadership regimes produce simultaneous breakouts. Rationing by arrival order (first 5 entries in 10d, rest blocked) is arbitrary. Ranking breakouts by strength and letting top-2 bypass cluster limit improves selection.

**Change:** `signals/signal_combiner.py` (and mirror in `backtest/engine.py` if needed):
- Compute per-signal strength: `vol_ratio × (close / high_Nd − 1)`
- Top 2 daily signals bypass cluster limit (5-in-10d)
- Remaining signals still subject to 5-in-10d limit
- A-tier signals also bypass the consecutive-loss throttle (Exp 12)

**Reference cases (ALL-PASS signals ignored by capacity manager):**
- 2024: PNBN 2024-10-18, LINK 2024-09-09, JPFA 2024-03-19 + 2024-07-11
- 2025: JARR (2 signals, +2,304%), FILM (2 signals, +275%), LINK, TOTL, EXCL

**Pass criteria:**
- 2024 AND 2025 total return both improve
- Max concurrent positions ≤ 8
- Max drawdown no worse than baseline + 1pp (−5.84% / −4.38%)

**Implementation note:** The bypass is applied at signal generation time (before cluster limit fires), not at execution time. This is different from Exp 17 which modified the cooldown check at execution. Exp 18 modifies which signals are allowed to enter the capacity queue.

---

## 6. Next Steps

1. Read v21 → v22 → v23 → v24 (this doc) → `DEVELOPER_CONTEXT.py`
2. Implement Exp 18 per spec above
3. Commit, push, trigger 2024 run → wait → trigger 2025 run
4. Download artifacts, evaluate against new baseline (2024 PF 0.54, 2025 PF 3.63)
5. If ACCEPT: keep, move to Exp 19
6. If REJECT: revert, move to Exp 19
7. Continue queue through Exp 13, 14, etc.
8. After all experiments: assemble final stack, run 2024 + 2025 validation, produce v25 handoff

---

## 7. What NOT to Do

- Do NOT use the old baselines from v21 (run 24199627413 / 24199629162) — those had Exp 9 residue
- Do NOT re-run Exp 17 without adding a minimum elapsed-time guard (≥ 15 trading days) to the bypass condition
- Do NOT retry Exp 9 or Exp 10 — already REJECTED
- Do NOT run idx-database workflows in parallel
- Do NOT merge feature → main until full stack is validated

---

## 8. Key Run IDs Reference

| Description | Run ID |
|---|---|
| **NEW 2024 clean baseline (post cleanup)** | **24220505468** |
| **NEW 2025 clean baseline (post cleanup)** | **24220636277** |
| OLD 2024 Exp 12 baseline (has Exp 9 residue) | ~~24199627413~~ |
| OLD 2025 Exp 12 baseline (has Exp 9 residue) | ~~24199629162~~ |
| Exp 17 2024 (REJECTED) | 24203548317 |
| Exp 17 2025 (REJECTED, no effect) | 24203761354 |
| Exp 12 2024 (ACCEPTED, but obsolete baseline) | 24199627413 |
| Exp 12 2025 (ACCEPTED, but obsolete baseline) | 24199629162 |
| v9 main 2025 reference | 24171709463 |
| v10-exp original 2024 baseline | 24171380283 |

---

*End of v24. Next session begins at Exp 18.*
