# SahamGPT-Bot — Session Handoff Document
> Last updated: April 9, 2026 (v22 — 2024 mega-winner analysis + Exp 13–18 framework proposal)
> Repo: https://github.com/nstnarie/SahamGPT-Bot (public, Python 100%)
> Paste this at the start of a new chat to resume seamlessly.

**v22 is a BRAINSTORMING OUTPUT. No code changes, no CI runs in this session.**

This handoff is the output of the "framework analysis session" flagged at the end of v21. It produces a fresh experiment queue (Exp 13–18) targeting a different axis than v10's Exp 1–12. Read **v21 first** for baselines and current state; this doc builds on it.

---

## ⚠️ CLAUDE: READ THIS BEFORE DOING ANYTHING

1. **Read `HANDOFF_SESSION_2026_04_09_v21.md` first** — current baselines (post Exp 2 + 4 + 12), codebase state, cleanup TODOs, database state, next steps.
2. **Read `DEVELOPER_CONTEXT.py`** — locked rules, hard parameters.
3. **`idx-database` is shared** — NEVER run workflows in parallel.
4. **⚠️ Exp 9 cleanup still outstanding** per v21 — `backtest/portfolio.py` NO_FOLLOWTHROUGH exit + `backtest/engine.py` cooldown condition must be removed before Exp 13 runs.
5. This session (v22) produced **zero code changes** — everything below is a plan awaiting execution in a new session.

---

## 1. Session Summary

Ran a forensic analysis of 2024 to understand why the system misses the year's mega-winners. Reconciled findings against the full v10 experiment history (including v21's Exp 9/10/12 results). Produced a new experiment queue (Exp 13–18) that attacks a **different axis** than v10: instead of tweaking thresholds on existing rules, it questions which entry rules should exist at all.

### The question
"Which IDX stocks in our 109-ticker universe gained ≥50% at any point during 2024 (Jan first close → intra-year peak), and why did our system miss them?"

Note: analysis used "peak gain" (Jan first close → intra-year high), NOT Jan→Dec change. A Jan→Dec filter hides mega-movers that ran then reversed (NIKL, LINK, ADRO, WIKA, AMMN all ran 60–100% mid-year then gave most back by Dec).

---

## 2. The 22 Mega-Winners of 2024

Computed from yfinance (reminder: `daily_prices` is rebuilt live during every CI run; the `idx-database` artifact only persists broker_summary).

| # | Ticker | Jan Close | Peak | Peak Date | Dec Close | Jan→Peak | Jan→Dec |
|---|--------|----------:|-----:|-----------|----------:|---------:|--------:|
| 1 | DSSA | 308 | 1,860 | Oct 28 | 1,480 | **+503.9%** | +380.5% |
| 2 | PTRO | 568 | 2,830 | Dec 27 | 2,762 | **+398.7%** | +386.8% |
| 3 | BBSS | 79 | 236 | Oct 24 | 148 | **+198.7%** | +87.3% |
| 4 | DSNG | 545 | 1,370 | Nov 12 | 950 | **+151.4%** | +74.3% |
| 5 | TINS | 660 | 1,520 | Nov 05 | 1,070 | **+130.3%** | +62.1% |
| 6 | TOTL | 378 | 830 | Oct 28 | 680 | **+119.6%** | +79.9% |
| 7 | BALI | 800 | 1,745 | Dec 30 | 1,745 | **+118.1%** | +118.1% |
| 8 | JARR | 246 | 525 | Mar 19 | 310 | +113.4% | +26.0% |
| 9 | NIKL | 312 | 625 | Mar 19 | 236 | +100.3% | −24.4% |
| 10 | AMMN | 6,600 | 13,200 | May 29 | 8,475 | +100.0% | +28.4% |
| 11 | WIKA | 240 | 460 | Sep 03 | 244 | +91.7% | +1.7% |
| 12 | TPIA | 5,700 | 10,625 | Aug 14 | 8,475 | +86.4% | +31.6% |
| 13 | PNBN | 1,130 | 2,010 | Nov 11 | 1,860 | +77.9% | +64.6% |
| 14 | ESSA | 560 | 985 | Oct 31 | 810 | +75.9% | +44.6% |
| 15 | SILO | 2,160 | 3,750 | Oct 31 | 3,240 | +73.6% | +50.0% |
| 16 | LINK | 1,320 | 2,260 | Sep 09 | 1,200 | +71.2% | −9.1% |
| 17 | SRTG | 1,640 | 2,780 | Dec 09 | 2,090 | +69.5% | +27.4% |
| 18 | JPFA | 1,170 | 1,960 | Dec 12 | 1,940 | +67.5% | +65.8% |
| 19 | ADRO | 2,490 | 4,040 | Nov 05 | 2,430 | +62.2% | −2.4% |
| 20 | TSPC | 1,825 | 2,840 | Oct 24 | 2,500 | +55.6% | +37.0% |
| 21 | KIJA | 132 | 204 | Dec 09 | 186 | +54.5% | +40.9% |
| 22 | SIDO | 510 | 775 | Jun 28 | 590 | +52.0% | +15.7% |

---

## 3. Capture Rate Under Original Baseline (run 24171380283, 42 trades)

> **IMPORTANT CAVEAT:** Cross-reference was done against the **original baseline** trade log (42 trades). The **current** baseline under Exp 12 has 34 trades (run 24199627413). The specific list below may differ under the current baseline — re-verify as Step 0 of execution.

### Traded (5/22) — all underperformed the move
- **TOTL** 2024-07-18 → 2024-08-05 −9.0% STOP_LOSS (rally began late Sep, 30d cooldown locked re-entry)
- **AMMN** 2024-03-01 → 2024-03-27 −0.1% TIME_EXIT (mega rally May–Jun blocked by RSI + regime on every subsequent breakout)
- **WIKA** 2024-08-14 partial (+18.9%) + trend exit (+17.5%) — caught, but 2nd leg blocked
- **ADRO** 2024-03-07 → 2024-04-17 +0.7% REGIME_EXIT (Nov rally blocked by RSI + regime + cooldown)
- **TINS** 2024-09-26 → 2024-10-23 +15.2% TREND_EXIT (peak Nov 5 at +130% — MA10 trail exited 12 days too early)

### Never triggered (17/22)
DSSA, PTRO, BBSS, DSNG, BALI, JARR, NIKL, TPIA, PNBN, ESSA, SILO, LINK, SRTG, JPFA, TSPC, KIJA, SIDO

### Signal-day analysis (computed offline via yfinance)
Computed all 8 entry rules for every 60-day-high breakout day across all 22 stocks in 2024 and tallied which rule(s) failed on each day. Key finding:

**Three stocks had ALL-PASS signal days but no trade was taken** — meaning the rule filters approved the signal, but cluster limit / cooldown blocked execution:
- **PNBN** 2024-10-18 ALL-PASS
- **LINK** 2024-09-09 ALL-PASS
- **JPFA** 2024-03-19 and 2024-07-11 — two ALL-PASS days, neither taken

This proves the issue is **at least two separate bugs**: (a) entry rules reject too many true signals, and (b) capacity management rejects signals the rules already approved.

---

## 4. Blocking Rule Tally

Across all 60-day-high breakout days for the 22 mega-winners in 2024:

| Rank | Rule | Times blocked | % of breakouts |
|------|------|--------------:|---------------:|
| 1 | **R7 RSI 40–75** (upper bound) | ~85 | ~55% |
| 2 | **R9 IHSG regime** (Exp 2) | ~55 | ~35% |
| 3 | **R2 Volume 1.5×–5×** (upper cap) | ~50 | ~32% |
| 4 | R5 Candle quality | ~20 | ~13% |
| 5 | R8 MACD hist > 0 | ~6 | ~4% |
| 6 | R4 Min price ≥ Rp 150 | 4 | ~2.5% |

(Percentages sum >100% because many days fail multiple rules.)

---

## 5. Root-Cause Analysis (prose)

### Root cause 1 — **R7 RSI ≤75 is structurally anti-momentum**
A stock going from Rp 300 to Rp 1,800 spends almost the entire move with RSI(14) > 75. A breakout-momentum system must not reject momentum. **TSPC: 7/7 breakouts blocked by RSI alone.** DSSA, PTRO, SRTG: nearly identical. This is the highest-leverage single bug.

### Root cause 2 — **R2 volume cap at 5× discards ignition days**
Mega-moves print 6–15× on the ignition day. The cap was likely added to deter pump-and-dump, but it throws out genuine institutional accumulation too. JARR + NIKL parabolic 3-day runs both exceeded the cap on every breakout day.

### Root cause 3 — **Exp 2 regime gate kills Q2 2024 seed legs**
Exp 2 was ACCEPTED because it helped 2025 (PF +0.19, +Rp 10M). But on 2024 it killed first-leg breakouts of TPIA, PTRO, DSSA, SILO, ESSA, ADRO during March–May 2024 when IHSG was choppy. The current gate (`IHSG > MA20 AND IHSG daily > −1%`) is too tight for a sideways index year. Sector leadership exists independent of index daily noise.

### Root cause 4 — **Exp 4 cooldown + cluster limit lock out valid re-entries**
ADRO and TOTL stopped early, then the real rally was inaccessible due to 30d post-stop cooldown. PNBN, LINK, JPFA had clean ALL-PASS signals ignored during cluster-limit-heavy weeks. The cooldown is calendar-based when it should be price-based.

### Root cause 5 — **Trend exit fires too early on mega-moves**
TINS exited +15% on Oct 23, peak was Nov 5 at +130%. MA10 is noise-level on IDX volatility. The `+15% partial sell + MA10 trail` rule caps winners at small multiples while losers still run to −7 to −12%. R:R is inverted.

### Note on Exp 9 (rejected in v21)
v21 REJECTED Exp 9 with the note *"Cuts slow-building 2024 winners; regime problem not trade mgmt"*. This is **exactly the same diagnosis** I arrived at independently. Exp 9 attacked the exit side too aggressively — and what's actually needed is looser **entries** (so the losers get washed out fast by existing stops) combined with **longer runway for winners** (MA20 instead of MA10). Exp 13–18 are the coherent implementation of that worldview.

### Note on Exp 12 (accepted in v21) — new suspect
Exp 12 throttle cut trades from 42 → 34. Which trades did it remove? **Until we inspect the current trade log, we do not know whether Exp 12 also blocked mega-winner entries.** This is Step 0 of the execution plan — re-verify the 22-stock capture rate under the current baseline.

---

## 6. Reconciliation Against v10 Experiment History

| My suggestion | v10 status | Decision |
|---|---|---|
| Drop RSI upper bound | Never tested | ✅ NEW → Exp 13 |
| Remove volume cap | Never tested | ✅ NEW → Exp 14 |
| MA20 trail after +25% (replace MA10 after +15%) | Never tested | ✅ NEW → Exp 15 |
| Relax IHSG regime gate | Exp 2 ACCEPTED; Exp 6 (different) REJECTED | ⚠️ Re-test Exp 2 → Exp 16 |
| Cooldown exemption on new 60d high | Exp 4 ACCEPTED (plain 30d) | ⚠️ Modify Exp 4 → Exp 17 |
| A-tier cluster exemption | Never tested | ✅ NEW → Exp 18 |
| Pyramid on re-breakout | Tier 4 future (7b) | Defer |
| Lower min price to Rp 50 | Exp 5 REJECTED (sub-Rp 150 hits emergency stop) | Defer — only KIJA/BBSS affected |
| Early no-follow-through exit | Exp 9 REJECTED in v21 | Do not retry |
| ATR volatility cap | Exp 10 REJECTED in v21 | Do not retry |

**Two currently ACCEPTED experiments (Exp 2, Exp 4) are under suspicion for hurting 2024.** They helped 2025 — but since the current 2024 PF is 0.51 (losing money), there's room to test whether relaxing them loses less 2025 than it gains 2024.

---

## 7. Exp 13–18 Full Specs

### Exp 13 — Drop RSI upper bound *(TIER 1)*

**Hypothesis:** Removing the RSI ≤75 ceiling recovers breakout entries on genuinely strong momentum stocks without a corresponding increase in fakeout rate.

**Change:**
- `signals/signal_combiner.py` RSI check: `40 <= rsi <= 75` → `rsi >= 40`
- `backtest/engine.py` — same change if mirrored

**Expected 2024 recovery:** 8–10 missed winners (DSSA, PTRO, SRTG, TSPC, earlier JPFA legs, SILO, BBSS, NIKL, JARR, earlier TINS entries).

**Risk:** enters genuine pumps. Mitigation: candle quality (R5) still active; existing FF and gap-up filters still active.

**Pass criteria:**
- 2024 PF ≥ 0.80 (vs 0.51 baseline) AND total return improves
- 2025 total return does not regress > 2pp vs +16.61% baseline
- 2025 PF stays ≥ 2.50

---

### Exp 14 — Remove volume upper cap *(TIER 1)*

**Hypothesis:** The `vol_ratio ≤ 5.0` cap rejects ignition-day institutional buying on parabolic movers. Dropping the cap (keeping 1.5× floor) recovers those entries.

**Change:**
- `signals/signal_combiner.py`: `1.5 <= vr <= 5.0` → `vr >= 1.5`
- `backtest/engine.py`: same

**Expected 2024 recovery:** 4–6 parabolic movers (JARR, NIKL, ignition days on DSSA/PTRO/AMMN).

**Risk:** lower-quality signals on thin stocks. Mitigation: existing candle quality + foreign flow filters.

**Pass criteria:** same format as Exp 13 — 2024 PF ≥ 0.80, 2025 no > 2pp regression.

---

### Exp 13 + 14 combined *(synergy test)*

Both modifications active simultaneously. Strong synergy expected because the same breakout days often fail both R7 and R2. Run after individual tests to measure combined effect.

**Pass criteria:** combined PF improvement ≥ sum of individual improvements × 0.7 (test for super-additive synergy).

---

### Exp 15 — MA20 trailing stop after +25% *(exit side)*

**Hypothesis:** The current MA10 + `+15% partial sell` rule caps winners at small multiples. Switching to MA20 trail activated at +25% gain lets winners mature without materially increasing give-back.

**Change:**
- `backtest/portfolio.py` — swap MA10 for MA20 in the post-gain trail check
- `signals/exit_rules.py` — same
- Trend-exit activation threshold: +15% → +25%
- Remove or defer the 30%-partial-sell-at-+15% rule

**Reference case:** TINS exited Oct 23 at +15%; peak Nov 5 at +130%. Single trade gave up 115pp of capturable gain.

**Expected impact:** avg winner size up 1.5–2×; max drawdown may tick up 0.5–1pp.

**Pass criteria:**
- 2024 AND 2025 total return both improve
- Calmar ≥ baseline − 0.5 on both years
- Avg winning-trade size ≥ 1.3× baseline

---

### Exp 16 — Simplify IHSG regime gate *(re-test Exp 2)*

**Hypothesis:** The current gate (`IHSG > MA20 AND IHSG daily > −1%`) is too tight for sideways-index years. Replacing with a single trend-level check (`IHSG > MA50`) restores sector-leadership entries during index chop.

**Change:** `signals/market_regime.py` `ihsg_entry_ok`:
- From: `IHSG > MA20 AND IHSG daily > −1%`
- To: `IHSG > MA50`

**Reference cases:** TPIA, PTRO, DSSA, SILO, ESSA, ADRO first-leg breakouts all blocked in Mar–May 2024.

**Expected 2024 recovery:** 5–6 seed-leg entries.

**Risk:** re-introduces 2024 fakeout-reversal losses. **This is the key test** — does the coarser gate net more winners than losers?

**Pass criteria:**
- 2024 PF ≥ 0.70 (vs 0.51 baseline)
- 2025 total return does not regress > 2pp vs +16.61%
- 2025 PF stays ≥ 2.50

---

### Exp 17 — Cooldown bypass on new 60-day high *(modify Exp 4)*

**Hypothesis:** The blanket 30d post-STOP_LOSS / post-TREND_EXIT cooldown locks out real trend resumption. Bypassing it when the stock makes a new 60d high above the pre-stop breakout level preserves "don't re-fail immediately" protection while allowing re-entry into genuine continuation moves.

**Change:** `backtest/engine.py` cooldown check:
- Track `last_stop_breakout_level` per ticker (the `high_60` that was broken on the stopped entry)
- On new signal: if `current_close > last_stop_breakout_level` AND current setup is a fresh 60d-high break, bypass cooldown
- Otherwise keep 30d cooldown

**Reference cases:** ADRO (stopped Apr, rally Nov), TOTL (stopped Aug, rally Sep–Oct), PNBN, LINK, JPFA ALL-PASS days.

**Expected 2024 recovery:** 3–5 missed trades.

**Risk:** re-entering true failures. Mitigation: higher-high condition ensures genuine trend resumption.

**Pass criteria:**
- 2024 PF improves OR winning-trade count up by ≥ 3
- 2025 no regression > 1pp

---

### Exp 18 — A-tier cluster exemption

**Hypothesis:** Leadership regimes produce simultaneous breakouts. Rationing by arrival order (first 5 entries in 10d, rest blocked) is arbitrary. Ranking breakouts by strength and letting top-2 bypass cluster limit improves selection.

**Change:** `signals/signal_combiner.py`:
- Compute per-signal strength: `vol_ratio × (close / high_60 − 1)`
- Top 2 daily signals bypass cluster limit
- Remaining signals still subject to 5-in-10d limit
- **Interaction with Exp 12:** A-tier signals also bypass the consecutive-loss throttle (cleanest semantics)

**Reference cases:** LINK 2024-09-09, JPFA 2024-07-11.

**Expected 2024 recovery:** 2–3 missed entries.

**Risk:** concurrent position count rises; portfolio concentration.

**Pass criteria:**
- 2024 AND 2025 total return both improve
- Max concurrent positions ≤ 8
- Max drawdown no worse than 1pp vs baseline

---

## 8. Execution Queue (for next session)

### Step 0 — Sanity check: re-verify capture rate under current Exp 12 baseline

**Why:** My analysis used the original 42-trade baseline (run 24171380283). The current baseline is Exp 12 with 34 trades (run 24199627413). Exp 12 throttle may have removed some of the 5 mega-winner trades or added others.

**How:** Download backtest artifact for run 24199627413, inspect `trade_log.csv`, rebuild the "traded/never triggered" split for the 22 stocks listed in Section 2, re-tally whether any of the 22 gained or lost capture under Exp 12.

**Decision point:** If Exp 12 made capture worse on 2024, add it to the suspect list alongside Exp 2 and Exp 4.

**Time:** 5 minutes.

### Step 1 — Cleanup carryover from v21

Per v21 Section 3:
1. `backtest/portfolio.py` — remove `NO_FOLLOWTHROUGH` exit block (Exp 9, rejected)
2. `backtest/engine.py` — remove `NO_FOLLOWTHROUGH` from cooldown condition
3. `config.py` — set `exp11_sector_filter_enabled = False`
4. Verify `git status` clean before committing
5. Commit message: `cleanup: remove Exp 9 NO_FOLLOWTHROUGH residue + disable exp11 flag`

### Step 2 — Experiment run order

Standard matrix: each experiment backtested on both 2024 and 2025 via `run_backtest.yml` on `feature/v10-experiments`, `real_broker=true`, sequential (shared `idx-database`). ~4 min per run in CI.

| # | Experiment | 2024 Run ID | 2025 Run ID | 2024 Return | 2024 PF | 2025 Return | 2025 PF | Verdict |
|:-:|------------|:-----------:|:-----------:|:-----------:|:-------:|:-----------:|:-------:|:-------:|
| 0 | Sanity check current baseline | (already 24199627413) | (already 24199629162) | −4.67% | 0.51 | +16.61% | 3.25 | ✅ baseline |
| 1 | **Exp 13** RSI upper bound removed | TBD | TBD | TBD | TBD | TBD | TBD | ⏸ |
| 2 | **Exp 14** Volume cap removed | TBD | TBD | TBD | TBD | TBD | TBD | ⏸ |
| 3 | **Exp 13+14** combined | TBD | TBD | TBD | TBD | TBD | TBD | ⏸ |
| 4 | **Exp 16** Simplified IHSG regime gate | TBD | TBD | TBD | TBD | TBD | TBD | ⏸ |
| 5 | **Exp 17** Cooldown bypass on new 60d high | TBD | TBD | TBD | TBD | TBD | TBD | ⏸ |
| 6 | **Exp 15** MA20 trail after +25% | TBD | TBD | TBD | TBD | TBD | TBD | ⏸ |
| 7 | **Exp 18** A-tier cluster exemption | TBD | TBD | TBD | TBD | TBD | TBD | ⏸ |
| 8 | **Stacked winners** from above | TBD | TBD | TBD | TBD | TBD | TBD | ⏸ |

**Total:** ~14 CI runs (7 experiments × 2 years) + 1 combined stack × 2 years = 16 runs. Sequential. ~60–90 min wall clock.

### After each experiment

1. Record run IDs in table above
2. Download artifacts, inspect `trade_log.csv` + `metrics_summary.txt`
3. Mark verdict: ✅ ACCEPT / ❌ REJECT / ⚠️ PARTIAL
4. If ACCEPT → keep in branch, move to next
5. If REJECT → revert that experiment's code, move to next
6. After all 7 runs → assemble stacked winners, run final 2024 + 2025 validation
7. Update v10 experiment list (reject/accept), produce merge plan

### After Exp 13–18 complete

1. If stack is net positive → cleanup carryover (already done in Step 1), merge `feature/v10-experiments` → `main`
2. If mixed results → new brainstorm with Arie before merge
3. In either case: update `HANDOFF_SESSION_*_v23.md` with results

---

## 9. Current Baselines (reference — copied from v21)

### feature/v10-experiments — post Exp 2 + Exp 4 + Exp 12, 109 tickers

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

### v9 main branch (reference)
45 trades | 37.8% WR | PF 2.14 | +12.74% | DD −3.28% | Sharpe 0.89 | Calmar 4.16

**Primary improvement target: 2024 PF from 0.51 → > 1.0 without 2025 regression.**

---

## 10. What NOT to Do in the Next Session

- Do NOT run multiple `idx-database` workflows in parallel
- Do NOT skip Step 0 (sanity check) — the plan's expected recovery counts are from the original baseline
- Do NOT skip 2025 re-tests — a 2024 fix that regresses 2025 is net negative
- Do NOT retry Exp 9 or Exp 10 — already REJECTED in v21
- Do NOT merge feature → main until the full Exp 13–18 stack is validated
- Do NOT forget Step 1 cleanup (Exp 9 NO_FOLLOWTHROUGH residue) before Exp 13 runs
- Do NOT forget to re-set `exp11_sector_filter_enabled = False` before merging

---

## 11. Files / Data Referenced

- `HANDOFF_SESSION_2026_04_09_v19.md` — v10 experiment history, entry/exit rules
- `HANDOFF_SESSION_2026_04_09_v21.md` — current baselines, Exp 9/10/12 results, cleanup TODOs
- `idx_swing_trader.db` (local, 2025-only daily_prices) — used to extract 109-ticker universe
- `/Users/arienasution/Downloads/backtest-2024-01-01-to-2024-12-31 2/trade_log.csv` — ORIGINAL 42-trade baseline (must re-download current Exp 12 trade log in Step 0)
- `.github/workflows/run_backtest.yml` — confirmed daily_prices populated live from yfinance during CI
- yfinance — used for 2024 price analysis (same data source CI uses)

---

*End of v22 brainstorming handoff. Next session begins at Step 0 (sanity check), then Step 1 (cleanup), then Exp 13.*
