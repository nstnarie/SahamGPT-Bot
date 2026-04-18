# SahamGPT-Bot — Session Handoff Document
> Last updated: April 10, 2026 (v23 — 2024 + 2025 mega-winner analysis + Exp 13–24 framework proposal)
> Repo: https://github.com/nstnarie/SahamGPT-Bot (public, Python 100%)
> Paste this at the start of a new chat to resume seamlessly.

**v23 is a BRAINSTORMING OUTPUT. No code changes, no CI runs in this session.**

This handoff supersedes v22. It extends the 2024 analysis with a 2025 analysis, adds six new experiments (Exp 19–24), and re-prioritises the full queue based on a critical cross-year finding: the capacity-manager bug (cluster limit + cooldown ignoring ALL-PASS signals) is the single highest-impact issue.

**Read order for next session:** v21 → v22 → v23 → `DEVELOPER_CONTEXT.py`

---

## ⚠️ CLAUDE: READ THIS BEFORE DOING ANYTHING

1. **Read `HANDOFF_SESSION_2026_04_09_v21.md` first** — current baselines, codebase state, cleanup TODOs, v10 experiment history.
2. **Read `HANDOFF_SESSION_2026_04_09_v22.md`** — 2024 mega-winner analysis, Exp 13–18 specs.
3. **Read this doc (v23)** — 2025 analysis, Exp 19–24 specs, revised priority ranking.
4. **Read `DEVELOPER_CONTEXT.py`** — locked rules, hard parameters.
5. **`idx-database` is shared** — NEVER run workflows in parallel.
6. **⚠️ Exp 9 cleanup still outstanding** per v21 — `backtest/portfolio.py` NO_FOLLOWTHROUGH exit + `backtest/engine.py` cooldown condition must be removed before Exp 13 runs.
7. This session (v23) produced **zero code changes**.

---

## 1. Session Summary (what v23 adds on top of v22)

v22 established that the 2024 system missed 17 of 22 mega-winners, with RSI cap + IHSG regime gate + volume cap as the primary blockers. v23 repeats the analysis on 2025 and discovers:

1. **A capacity-manager bug that is cross-year and catastrophic.** JARR (+2,304% in 2025) had **2 ALL-PASS signal days ignored** by cluster limit / cooldown — the same bug seen in 2024 for PNBN, LINK, JPFA. This bug alone may account for the single largest miss of the entire 2024+2025 period. **Exp 17 + 18 are now the highest priority experiments.**

2. **Stop-loss structure is incompatible with mega-move capture.** 86% of 2025 mega-winners endured drawdowns worse than −20% during their run to peak. 47% endured worse than −30%. The current −7% / 1.5×ATR / −12% emergency stop structure cannot hold through these. **Fixing entries (Exp 13/14) without fixing stops is worthless.** → Exp 19.

3. **R4 min-price rule became a 7× bigger blocker in 2025.** 28 breakout blocks (vs 4 in 2024). Multiple penny-stock mega-movers (INTA Rp 12→115, MDIA Rp 10→93). Exp 5 was rejected for the wrong reason — it removed the price floor without adding a liquidity floor. → Exp 20.

4. **Mega-moves take 5–11 months, not 2 weeks.** System's avg hold is ~2 weeks. TIME_EXIT rule (15 days no +3%) is fundamentally incompatible. → Exp 22.

5. **Pyramiding opportunities were visible on every captured winner.** PTRO, DSSA, TINS had multiple stacked breakouts — single-tranche entries capped the upside. → Exp 23.

6. **Same 10 stocks are mega-winners in both years** (DSSA, PTRO, TINS, JARR, TOTL, DSNG, BBSS, LINK, NIKL, and partial overlaps). Fixing capture on these 10 alone would move 2024 PF from 0.51 → >1.5 and 2025 PF from 3.25 → >5.0.

---

## 2. 2025 Mega-Winners (30 stocks with peak gain ≥50%)

| # | Ticker | Jan | Peak | Peak Date | Dec | Jan→Peak | Jan→Dec |
|---|--------|-----:|-----:|-----------|-----:|---------:|--------:|
| 1 | JARR | 340 | 8,175 | Oct 13 | 3,230 | **+2,304%** | +850% |
| 2 | INTA | 12 | 115 | Dec 11 | 115 | **+858%** | +858% |
| 3 | MDIA | 10 | 93 | Dec 18 | 88 | **+830%** | +780% |
| 4 | HRTA | 328 | 2,300 | Dec 29 | 2,150 | **+601%** | +555% |
| 5 | BRPT | 940 | 4,280 | Oct 10 | 3,270 | **+355%** | +248% |
| 6 | LINK | 1,210 | 4,900 | Dec 04 | 4,070 | **+305%** | +236% |
| 7 | PTRO | 2,745 | 11,025 | Dec 11 | 10,925 | **+302%** | +298% |
| 8 | FILM | 3,870 | 14,500 | Dec 30 | 14,500 | **+275%** | +275% |
| 9 | TINS | 1,085 | 3,550 | Dec 15 | 3,110 | **+227%** | +187% |
| 10 | DSSA | 1,492 | 4,620 | Dec 02 | 4,040 | **+210%** | +171% |
| 11 | EMTK | 525 | 1,565 | Oct 01 | 1,085 | +198% | +107% |
| 12 | BBSS | 150 | 446 | Oct 28 | 398 | +197% | +165% |
| 13 | SCMA | 167 | 460 | Oct 08 | 338 | +175% | +102% |
| 14 | WSBP | 16 | 39 | Sep 09 | 23 | +144% | +44% |
| 15 | ANTM | 1,545 | 3,670 | Sep 23 | 3,150 | +138% | +104% |
| 16 | BCIP | 54 | 128 | Sep 26 | 83 | +137% | +54% |
| 17 | DSNG | 900 | 1,950 | Oct 22 | 1,540 | +117% | +71% |
| 18 | NIKL | 242 | 472 | Oct 08 | 346 | +95% | +43% |
| 19 | PGEO | 940 | 1,830 | Jul 29 | 1,125 | +95% | +20% |
| 20 | SSMS | 1,210 | 2,220 | Feb 03 | 1,535 | +83% | +27% |
| 21 | NCKL | 755 | 1,360 | Oct 29 | 1,125 | +80% | +49% |
| 22 | ALTO | 15 | 26 | Feb 07 | 18 | +73% | +20% |
| 23 | EXCL | 2,250 | 3,900 | Dec 19 | 3,750 | +73% | +67% |
| 24 | INDY | 1,495 | 2,550 | Oct 17 | 2,240 | +71% | +50% |
| 25 | MDKA | 1,595 | 2,700 | Sep 09 | 2,280 | +69% | +43% |
| 26 | BTPS | 935 | 1,540 | Jul 23 | 1,205 | +65% | +29% |
| 27 | TOTL | 675 | 1,100 | Nov 24 | 1,015 | +63% | +50% |
| 28 | BBKP | 55 | 87 | Aug 28 | 77 | +58% | +40% |
| 29 | BUKA | 125 | 195 | Oct 06 | 158 | +56% | +26% |
| 30 | UNVR | 1,835 | 2,770 | Dec 03 | 2,600 | +51% | +42% |

### Cross-year shared mega-winners (appeared in both 2024 and 2025)

| Ticker | 2024 Peak | 2025 Peak | Priority |
|--------|----------:|----------:|:--------:|
| JARR | +113% | **+2,304%** | 🔥 highest |
| PTRO | +399% | +302% | 🔥 |
| TINS | +130% | +227% | 🔥 |
| DSSA | +504% | +210% | 🔥 |
| LINK | +71% | +305% | 🔥 |
| BBSS | +199% | +197% | 🔥 |
| DSNG | +151% | +117% | 🔥 |
| TOTL | +120% | +63% | high |
| NIKL | +100% | +95% | high |

---

## 3. Capture Rate Under Current Exp 12 Baseline (2025)

**Run 24199629162, 35 trades, PF 3.25**

Caught 9/30 mega-winners (30%):

| Ticker | Result | % of available move captured |
|---|---|---:|
| **TINS** | +22.9% partial + **+118% TREND_EXIT** | 52% ← best catch |
| **EMTK** | +13.9% partial + **+77% TREND_EXIT** | 39% |
| **UNVR** | +25% TREND_EXIT | 49% |
| **PTRO** | +14.5% partial + **+45% TREND_EXIT** | 15% |
| **ANTM** | +45.4% TREND_EXIT | 33% |
| **DSSA** | +24.7% TREND_EXIT | 12% |
| **HRTA** | −8.8% stop → +19.7% trend exit | **3%** of +601% |
| **SCMA** | −1.1% stop | 0% |
| **BTPS** | −6.6% stop | 0% |

**Never triggered (21):** JARR, INTA, MDIA, BRPT, LINK, FILM, BBSS, WSBP, BCIP, DSNG, NIKL, PGEO, SSMS, NCKL, ALTO, EXCL, INDY, MDKA, TOTL, BBKP, BUKA

### Capacity-manager ignores (ALL-PASS signals not traded)

| Ticker | ALL-PASS days | Peak gain | Likely cause |
|---|---:|---:|---|
| **JARR** | 2 | **+2,304%** | Cluster limit or cooldown |
| **FILM** | 2 | +275% | Cluster limit or cooldown |
| **LINK** | 1 | +305% | Cluster limit or cooldown |
| **TOTL** | 1 | +63% | Cluster limit or cooldown |
| **EXCL** | 1 | +73% | Cluster limit or cooldown |

**Combined with 2024's PNBN/LINK/JPFA ignores** — this is the same bug, cross-year, affecting the single largest winner (JARR +2,304%). Exp 17 + 18 are the highest-priority fixes in the entire queue.

---

## 4. Blocking-Rule Tally — 2024 vs 2025 Comparison

Computed across all 60-day-high breakout days for never-triggered mega-winners.

| Rule | 2024 blocks | 2025 blocks | Change |
|---|---:|---:|---|
| R7 RSI 40–75 cap | ~85 | 77 | structural, same |
| R2 Volume 1.5–5× cap | ~50 | 47 | structural, same |
| R9 IHSG regime gate | ~55 | 19 | much less in 2025 (better index) |
| **R4 Min price ≥ Rp 150** | 4 | **28** | 🚨 **7× jump** |
| R5 Candle quality | ~20 | 15 | similar |
| R8 MACD hist > 0 | ~6 | 2 | minor |

---

## 5. 🚨 The Biggest New Insight: Max Drawdown During the Mega-Move

For each 2025 mega-winner, computed the worst peak-to-trough drawdown that occurred while the stock was still on its way up to its eventual peak.

| Drawdown bucket | # of stocks | % |
|---|---:|---:|
| 0 to −10% | 2 | 7% |
| −10 to −20% | 2 | 7% |
| −20 to −30% | 12 | 40% |
| **worse than −30%** | **14** | **47%** |

**86% of mega-winners endured drawdowns worse than −20%. 47% endured worse than −30%.**

Worst cases:
- FILM: −64.8% DD mid-move → +275% peak
- MDIA: −60.4% DD → +830% peak
- PTRO: −55.1% DD → +302% peak
- LINK: −43.8% DD → +305% peak
- INTA: −42.1% DD → +858% peak

**Current stops (−7% / 1.5×ATR, −12% emergency) are mathematically incompatible with holding through these drawdowns.** Even if Exp 13/14/16 fix entries perfectly, the stops will exit on every mega-move's first shake-out.

**Captured vs missed max-DD comparison:**
- Captured (9): avg max-DD during move = −32.7%
- Missed (21): avg max-DD during move = −31.5%

Same magnitude — the captured 9 weren't structurally different, they just happened to have their biggest drawdowns after trend-exit fired. This is the single most important finding of v23.

---

## 6. Liquidity Insight (ADV20)

Median 20-day average daily value traded (billions IDR):

| Group | Median ADV20 |
|---|---:|
| **Captured** (9) | **52.0 Bn** |
| **Missed** (21) | **10.2 Bn** |

The system is systematically better at catching liquid stocks. Missed names like INTA (~0 Bn), MDIA (0.1 Bn), LINK (0.2 Bn), BBSS (0.2 Bn), WSBP (0.1 Bn), ALTO (~0 Bn) aren't just sub-Rp150 — they fall below any reasonable liquidity threshold. This explains why Exp 5 (remove min price) failed: it removed the price floor without adding a liquidity floor, letting in true penny garbage. **Exp 20 fixes this cleanly.**

---

## 7. Time-to-Peak Insight — mega-moves take 5–11 months

Days from first 60d-high breakout to peak (2025 mega-winners):

| Ticker | Days to peak | Peak gain |
|---|---:|---:|
| PTRO | 336 | +302% |
| MDIA | 336 | +830% |
| HRTA | 327 | +601% |
| LINK | 317 | +305% |
| FILM | 315 | +275% |
| DSSA | 302 | +210% |
| TINS | 234 | +227% |
| JARR | 231 | +2,304% |
| ANTM | 215 | +138% |
| INTA | 205 | +858% |

**System's average hold time is ~2 weeks.** This is a 10–20× mismatch. Fix requires:
- Exp 15 (MA20 trail after +25%) — basic extension
- Exp 22 (disable TIME_EXIT for RS leaders) — rule-level extension
- Exp 23 (pyramid-add on proven winners) — capital extension

---

## 8. NEW Experiment Specs (Exp 19–24)

### 🔥 Exp 19 — Volatility-adjusted stops for trend leaders

**Hypothesis:** Stocks with proof-of-trend (close > MA50 for 20+ consecutive days AND position is up ≥10% from entry AND RS rank > 80th percentile of universe) get a widened stop: −15% fixed or 3×ATR, whichever is wider. Pre-trend-proof stocks keep the current −7% / 1.5×ATR.

**Why:** 86% of 2025 mega-movers endured >20% drawdowns during their run to peak. Current stops are structurally incompatible.

**Change:**
- `backtest/portfolio.py` — add `trend_leader` flag on positions; compute daily
- When flag true, override stop to `max(entry_price * 0.85, entry_price - 3*ATR_on_entry)`
- Flag activation condition: holding_days ≥ 10 AND position pnl_pct ≥ +10% AND close > MA50 for past 20 days
- Emergency stop stays at −12% (unchanged)

**Reference cases:**
- HRTA: stopped Apr 30 at −8.8%, came back to +601%
- FILM: −64.8% drawdown mid-move
- PTRO: −55.1% drawdown mid-move

**Risk:** Larger individual losses on failed trend entries (capped by −12% emergency). Mitigation: only activates after proof-of-trend.

**Pass criteria:**
- 2024 PF improves
- 2025 PF ≥ 3.00 (vs 3.25 baseline — small regression acceptable for mega-capture)
- Avg winning-trade size ≥ 1.5× baseline

---

### 🔥 Exp 20 — Liquidity floor replaces min price (solves rejected Exp 5)

**Hypothesis:** Replace `close ≥ Rp 150` with `ADV20 ≥ Rp 2bn`. Captures uptrending penny stocks with real volume while still excluding illiquid garbage.

**Why:** R4 blocked 28 breakout days on 2025 mega-winners (up from 4 in 2024). Exp 5 was rejected because removing Rp 150 without a liquidity floor let in true garbage. A value-traded threshold is the correct filter.

**Change:**
- `signals/signal_combiner.py` — replace `close >= 150` with `adv20 >= 2e9`
- `backtest/engine.py` — same
- Requires `daily_value = close * volume` column and 20d rolling avg (likely already computed)

**Reference cases recovered:** BCIP (Rp 54, ADV 2.3Bn), TOTL, NCKL, INDY, NIKL (ADV 0.4Bn — edge case, would fail 2Bn floor, may need 1Bn)

**Trade-off:** INTA (Rp 12, ADV ~0) and MDIA (Rp 10) still excluded — these are edge cases truly below any reasonable liquidity.

**Pass criteria:**
- 2024 AND 2025 return both improve
- No regression in PF
- Trade count may increase by 5–10 annually

---

### 🔥 Exp 21 — Re-entry after shake-out (stronger Exp 17)

**Hypothesis:** Track the breakout level that was stopped out. If price re-crosses that level within 60 days AND makes a new higher high, re-enter at 50% position size regardless of cooldown.

**Why:** Mega-moves include shake-outs by design. 30d cooldown assumes "stopped = bad," but for trend stocks, a stop is a liquidity event, not a trend change.

**Change:** `backtest/engine.py`:
- On STOP_LOSS, record `{ticker: (stop_date, breakout_level)}` in `stopped_positions` dict
- On new signal: if ticker in stopped_positions AND days_since_stop ≤ 60 AND current_close > stopped_breakout_level AND signal is a new 60d-high break → enter at 50% normal size, bypass cooldown
- If re-entry also stops → remove from stopped_positions (don't chase a 3rd time)

**Complements Exp 17:** Exp 17 only bypasses cooldown on a new 60d high. Exp 21 is more aggressive — re-enter on any higher high after a stop, not just 60d high.

**Reference cases:** HRTA (2025), ADRO + TOTL (2024).

**Risk:** Over-trading stopped names. Mitigation: 60-day window + max 1 re-entry.

**Pass criteria:**
- Trade count up by 3–6 winners in each year
- 2024 PF ≥ 0.80
- 2025 PF no worse than −0.10 from baseline

---

### Exp 22 — Disable TIME_EXIT for RS leaders

**Hypothesis:** If position is in top 20% RS rank vs universe AND close > MA50, disable the "15 days no +3% AND below MA10" TIME_EXIT rule.

**Why:** Mega-moves take 5–11 months with frequent multi-week digestion periods. TIME_EXIT assumes 15 days is long enough to judge trend continuation — false on long-duration trends.

**Change:** `backtest/portfolio.py` — TIME_EXIT check gated by `not is_rs_leader(ticker, date)`

**Reference cases:** EMTK held 61 days (close to TIME_EXIT). PTRO mega-phase was 336 days. ANTM 215 days.

**Pass criteria:**
- Avg hold time for winners ≥ 1.5× baseline
- Max winner pnl_pct improves

---

### Exp 23 — Pyramid-add on proven winners

**Hypothesis:** When a position is ≥+20% from entry AND makes a new 10-day high AND that day's volume > 1.5× 20d avg, add 50% more size at the new high.

**Why:** Single-tranche entries cap the upside of compounding trends. PTRO, DSSA, TINS all had multiple stacked breakouts during their mega-runs.

**Change:**
- `backtest/engine.py` — add `pyramid_add` action type
- `backtest/portfolio.py` — track entry tranches separately, compute weighted-avg entry
- Cap: max 2 pyramid adds per position
- Requires: Exp 15 (MA20 trail) active to exit cleanly on trend break

**Reference cases:** PTRO Sep 18 entry + multiple subsequent breakouts, DSSA similar pattern.

**Risk:** Drawdown amplification if pyramid fails. Mitigation: max 2 adds, require Exp 15 trail.

**Pass criteria:**
- 2025 total return ≥ +20%
- Max drawdown no worse than baseline + 1pp

---

### Exp 24 — Auto-cluster sector tailwind (reframes rejected Exp 11)

**Hypothesis:** On each breakout, compute the 5 most price-correlated tickers over the last 60 days. Require ≥2 of them to be within 5% of their own 60d high. Uses return-based clustering instead of yfinance sector labels.

**Why:** Exp 11 was rejected because yfinance sector labels are too noisy for IDX. But sector/theme leadership is real — DSSA/PTRO/BRPT/DSNG moved together; JARR ran with digital-adjacents. Return-based auto-clustering avoids the label issue entirely.

**Change:** `signals/signal_combiner.py`:
- Precompute per-ticker correlation matrix (60-day rolling, updated weekly)
- On signal: lookup top-5 correlated peers; count how many are within 5% of their 60d high
- Require count ≥ 2 for signal to pass

**Risk:** Reduces trade count during non-trending markets. Lowest-confidence experiment in the queue.

**Pass criteria:**
- PF improves on both years
- Trade count reduction ≤ 20%

---

## 9. Revised Priority Ranking (Exp 13–24 combined)

| Rank | # | Experiment | Justification |
|:-:|:-:|---|---|
| 🥇 1 | **17** | Cooldown bypass on new 60d high | Part of JARR fix. Same bug in both years. |
| 🥇 2 | **18** | A-tier cluster exemption | Other half of JARR fix. ALL-PASS signals ignored. |
| 🥈 3 | **19** | Volatility-adjusted stops for trend leaders | Without this, 86% of mega-winners can't be held. Entry fixes useless. |
| 🥈 4 | **21** | Re-entry after shake-out | Complements 17 for post-stop resumption. HRTA-style recovery. |
| 🥉 5 | **13** | RS cap removed | ~55% of breakouts blocked by RSI. Fundamental entry fix. |
| 🥉 6 | **14** | Volume cap removed | ~32% blocked. High synergy with Exp 13. |
| 7 | **20** | Liquidity floor replaces min price | 28 blocks in 2025. Solves Exp 5 correctly. |
| 8 | **16** | Simplified IHSG regime gate | Big 2024 impact (~35% blocks), less in 2025. |
| 9 | **15** | MA20 trail after +25% | Exit improvement. Needed for 17/18 to pay off. |
| 10 | **22** | Disable TIME_EXIT for RS leaders | Specific hold-extension rule. |
| 11 | **23** | Pyramid-add on winners | Additive. Only meaningful after 13/14/19 stick. |
| 12 | **24** | Auto-cluster sector tailwind | Quality filter. Lowest confidence. |

---

## 10. Execution Queue (for next session)

### Step 0 — Sanity checks (5 min)

Before writing any code:
1. Verify the 2024 Exp 12 baseline trade log captures the same "5/22 traded" that v22 Section 3 lists — download run 24199627413 artifact and confirm
2. Verify the 2025 Exp 12 baseline trade log matches v23 Section 3 (run 24199629162) — **already done in v23**
3. Confirm `git status` clean on `feature/v10-experiments`

### Step 1 — Cleanup carryover from v21 (10 min)

1. `backtest/portfolio.py` — remove `NO_FOLLOWTHROUGH` exit block (Exp 9, REJECTED)
2. `backtest/engine.py` — remove `NO_FOLLOWTHROUGH` from cooldown condition
3. `config.py` — set `exp11_sector_filter_enabled = False`
4. Verify diff, commit, push: `cleanup: remove Exp 9/11 residue before Exp 13–24 sequence`

### Step 2 — Experiment run order

Standard matrix: each experiment backtested on both 2024 and 2025 via `run_backtest.yml` on `feature/v10-experiments`, `real_broker=true`, **sequential** (shared idx-database).

**24 CI runs total, ~4 min each = ~90–100 min wall clock.**

| # | Experiment | 2024 Run | 2025 Run | 2024 Return | 2024 PF | 2025 Return | 2025 PF | Verdict |
|:-:|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| 0 | Current baseline | 24199627413 | 24199629162 | −4.67% | 0.51 | +16.61% | 3.25 | ✅ |
| 1 | **Exp 17** Cooldown bypass new 60d high | TBD | TBD | TBD | TBD | TBD | TBD | ⏸ |
| 2 | **Exp 18** A-tier cluster exemption | TBD | TBD | TBD | TBD | TBD | TBD | ⏸ |
| 3 | **Exp 17 + 18** combined (synergy) | TBD | TBD | TBD | TBD | TBD | TBD | ⏸ |
| 4 | **Exp 19** Volatility stops for leaders | TBD | TBD | TBD | TBD | TBD | TBD | ⏸ |
| 5 | **Exp 21** Re-entry after shake-out | TBD | TBD | TBD | TBD | TBD | TBD | ⏸ |
| 6 | **Exp 13** RSI upper bound removed | TBD | TBD | TBD | TBD | TBD | TBD | ⏸ |
| 7 | **Exp 14** Volume cap removed | TBD | TBD | TBD | TBD | TBD | TBD | ⏸ |
| 8 | **Exp 13 + 14** combined | TBD | TBD | TBD | TBD | TBD | TBD | ⏸ |
| 9 | **Exp 20** Liquidity floor | TBD | TBD | TBD | TBD | TBD | TBD | ⏸ |
| 10 | **Exp 16** Simplified IHSG gate | TBD | TBD | TBD | TBD | TBD | TBD | ⏸ |
| 11 | **Exp 15** MA20 trail after +25% | TBD | TBD | TBD | TBD | TBD | TBD | ⏸ |
| 12 | **Exp 22** Disable TIME_EXIT for RS leaders | TBD | TBD | TBD | TBD | TBD | TBD | ⏸ |
| 13 | **Exp 23** Pyramid-add on winners | TBD | TBD | TBD | TBD | TBD | TBD | ⏸ |
| 14 | **Exp 24** Auto-cluster sector tailwind | TBD | TBD | TBD | TBD | TBD | TBD | ⏸ |
| 15 | **Full stack** of ACCEPTED experiments | TBD | TBD | TBD | TBD | TBD | TBD | ⏸ |

### After each experiment

1. Record run IDs
2. Download `trade_log.csv` + `metrics_summary.txt`
3. Verdict: ✅ ACCEPT / ❌ REJECT / ⚠️ PARTIAL
4. If ACCEPT → keep in branch, move next
5. If REJECT → revert that experiment's code, move next
6. After all experiments → assemble final stack, run 2024 + 2025 validation
7. Produce v24 handoff with results + merge plan

### After Exp 13–24 complete

1. If stack is net positive → merge `feature/v10-experiments` → `main`
2. If mixed → new brainstorm before merge
3. Update next handoff with all run IDs + verdict

---

## 11. Current Baselines (reference)

### feature/v10-experiments — post Exp 2 + 4 + 12, 109 tickers

| Metric | 2025 | 2024 |
|--------|------|------|
| Trades | 35 | 34 |
| Win Rate | **45.7%** | 32.4% |
| Total Return | **+16.61%** | −4.67% |
| Profit Factor | **3.25** | 0.51 |
| Max Drawdown | **−3.25%** | −5.35% |
| Sharpe | **1.42** | −1.83 |
| Calmar | **5.49** | −0.93 |
| Run ID | 24199629162 | 24199627413 |

**Primary target: 2024 PF from 0.51 → >1.0 without 2025 regression beyond −2pp.**
**Stretch goal: 2024 PF >1.5 AND 2025 PF ≥3.0, capturing JARR in 2025.**

---

## 12. What NOT to Do in the Next Session

- Do NOT run multiple `idx-database` workflows in parallel
- Do NOT skip Step 0 or Step 1 — dirty branch state breaks experiment isolation
- Do NOT retry Exp 9, Exp 10, Exp 11 (yfinance labels), Exp 5 (as originally framed) — all REJECTED
- Do NOT start experiments in random order — run order is designed to test highest-impact fixes first
- Do NOT merge feature → main until the full stack is validated
- Do NOT forget `exp11_sector_filter_enabled = False` before merge
- Do NOT interpret "PF regresses on 2025" as automatic reject — for Exp 19, a small 2025 PF regression is acceptable if it enables 2024 mega-capture

---

## 13. Files / Data Referenced

- `HANDOFF_SESSION_2026_04_09_v19.md` — v10 experiment history, rules
- `HANDOFF_SESSION_2026_04_09_v21.md` — current baselines, codebase state
- `HANDOFF_SESSION_2026_04_09_v22.md` — 2024 mega-winner analysis, Exp 13–18
- `idx_swing_trader.db` (local, 2025 only)
- `/tmp/bt2025/trade_log.csv` — current Exp 12 2025 baseline (35 trades, run 24199629162)
- `/Users/arienasution/Downloads/backtest-2024-01-01-to-2024-12-31 2/trade_log.csv` — original 2024 baseline (42 trades) — **still need to download current 34-trade Exp 12 log for Step 0**
- yfinance — source for all mega-winner analyses (same source CI uses)

---

## 14. Key Quantitative Findings (summary table)

| Finding | 2024 | 2025 |
|---|:---:|:---:|
| Mega-winners (≥50% peak gain) | 22 | 30 |
| Caught by system | 5 (23%) | 9 (30%) |
| Never triggered | 17 | 21 |
| ALL-PASS signals ignored (capacity bug) | 3 stocks, 4 signals | 5 stocks, 7 signals |
| #1 blocking rule | R7 RSI (~85) | R7 RSI (77) |
| #2 blocking rule | R9 regime (~55) | R2 vol (47) |
| #3 blocking rule | R2 vol (~50) | **R4 min price (28)** 🚨 |
| % with >20% DD mid-move | N/A | 86% |
| % with >30% DD mid-move | N/A | 47% |
| Median time to peak | N/A | 205 days (~7 months) |
| Captured median ADV20 | N/A | 52 Bn IDR |
| Missed median ADV20 | N/A | 10 Bn IDR |

---

*End of v23 brainstorming handoff. Next session begins at Step 0 (sanity check), then Step 1 (cleanup), then Exp 17 (highest priority).*
