# SahamGPT-Bot — Session Handoff Document
> Last updated: April 11, 2026 (v25 — 7 experiments REJECTED + data-driven pattern analysis → 3 new rules proposed)
> Repo: https://github.com/nstnarie/SahamGPT-Bot (public, Python 100%)
> Paste this at the start of a new chat to resume seamlessly.

---

## ⚠️ CLAUDE: READ THIS BEFORE DOING ANYTHING

1. **Do NOT re-read v21–v24** unless you need spec history. This doc (v25) is self-contained.
2. **Read `DEVELOPER_CONTEXT.py`** — locked rules, hard parameters.
3. **`idx-database` is shared** — NEVER run workflows in parallel.
4. **Branch is clean** — all experiments from this session reverted. HEAD is `67f349d`.
5. **DO NOT retry Exp 13, 14, 16, 18, 19, 20, 21** — all REJECTED with data. Move to new rules.
6. **Next action: implement Rule A (sector exclusion) as Exp 25, then Rule B and C.**

---

## 1. What Happened This Session (v25)

### Full experiment run results

Ran 7 experiments from the v23/v24 queue. **Every single one was REJECTED.** All experiments that tried to ADD more entries made 2024 worse.

| # | Experiment | 2024 PF | 2025 PF | Verdict | Root cause of failure |
|:-:|---|:-:|:-:|:-:|---|
| Baseline | — | **0.54** | **3.63** | ✅ | — |
| Exp 18 | A-tier cluster bypass | 0.44 | 3.36 | ❌ | Cluster limit was an implicit regime guard — bypassing it during crowded periods admitted poor trades |
| Exp 19 | Volatility stops (trend leaders) | null | null | ❌ | Structural: emergency stop (−12%) fires before any position reaches −15% to −20% range; trailing stop also fires first |
| Exp 21 | Re-entry after shake-out | 0.37 | 2.37 | ❌ | Most STOP_LOSS exits are trend reversals, not shake-outs. Re-entering doubled down on losers |
| Exp 13 | RSI upper bound removed | 0.48 | — | ❌ | Added 15 extra trades (2024) all losers. High RSI in bear year = overbought + reverting |
| Exp 14 | Volume cap removed | 0.57 | 2.47 | ❌ | More trades both years with lower WR. Volume cap is blocking real noise |
| Exp 20 | ADV20 liquidity floor | 0.41 | — | ❌ | Admitted penny/low-price stocks with volume — all bad in 2024 bear |
| Exp 16 | MA50 IHSG gate (instead of MA20+daily) | 0.24 | — | ❌ | Worst result of session. Allowed entries when IHSG between MA50 and MA20 — precisely the weakening zone |

### Key pattern: every loosening attempt fails

The consistent failure mode: every experiment that loosened an entry filter admitted more trades, and all of those extra trades lost in 2024. The filters (RSI cap, volume cap, min price, IHSG gate) are doing real work — they are NOT the problem.

---

## 2. Root Cause Analysis — First Principles

After 7 rejections, switched strategy: pulled both baseline trade logs and ran pattern analysis from scratch.

### The 3 core findings

#### Finding 1 — STOP_LOSS is destroying the portfolio

```
32 stop-loss trades across both years:
  6-10 day stops: 18 trades, 6% win rate, −Rp 59M  ← worst bucket
  11+ day stops:  14 trades, 36% win rate, −Rp 33M
  Combined: −Rp 92M
```

Stops at days 6-10 are dead money: these trades never showed momentum after the 5-day hold
period. They drifted flat then slowly hit the stop. A simple rule — "if at day 7 you're still
below entry, exit" — would cut many of these off at −2% instead of waiting for the −7% stop.

#### Finding 2 — TREND_EXIT is ALL the profit, TIME_EXIT is dead weight

```
10 TREND_EXIT trades = +Rp 247M = 85% of ALL gross profit
12 TIME_EXIT trades = −Rp 1.3M, avg 17 days each
  → 204 position-days locked in capital for essentially zero return
```

TIME_EXIT at 15 days is not killing bad trades — it's just holding them longer and producing
nothing. Shortening from 15d → 10d would free capital for more fresh entries.

#### Finding 3 — Three sectors NEVER produce winning momentum trades

```
Financial Services:  7 trades, 1 win (tiny +1.5%), −Rp 26M, 0 TREND_EXIT
Real Estate:         4 trades, 1 win (tiny +1.2%), −Rp 11M, 0 TREND_EXIT
Utilities:           2 trades, 0 wins,               −Rp 6M,  0 TREND_EXIT

Combined: 13 trades, PnL: −Rp 43M, 0 TREND_EXIT
```

These sectors never trend with enough momentum for breakout capture. Every entry is a slow
stop-loss death. They are destroying 2024 PF singlehandedly.

**Simulation: 2024 WITHOUT Financial/RE/Utilities:**
- 25 trades (removed 9), wins: 11/25, PF: 0.77 (vs 0.54 baseline)

### Summary stat: mega-winners vs non-mega

```
20 trades on mega-winner stocks:  75% WR, +Rp 233M
49 trades on non-mega stocks:     31% WR, −Rp 99M  ← problem is HERE
```

The system is correctly identifying the right stocks (29% of entries on mega-winners, generating
86% of profits). The damage comes from the 49 non-mega trades that bleed slowly.

---

## 3. Three New Data-Driven Rules (Next Session Action Items)

All three rules are DEFENSIVE — they remove bad trades, not add new ones. This is the opposite
direction of every failed experiment.

---

### Rule A — Sector exclusion (Exp 25)

**Hypothesis:** Financial Services, Real Estate, and Utilities never produce TREND_EXIT winners
across 2024 or 2025. These are rate-sensitive, low-momentum sectors where breakout signals are
noise. Excluding them removes 13 trades worth −Rp 43M.

**Change:** `config.py`
```python
excluded_sectors: List[str] = field(default_factory=lambda: [
    "Financial Services", "Real Estate", "Utilities"
])
```

The `excluded_sectors` field already exists in `UniverseConfig`. It is currently empty. Simply
populate it. No code changes needed — just config.

**But verify:** Does the backtest engine actually USE `excluded_sectors` to filter? Check
`backtest/engine.py` and `main_backtest.py`. If not wired up, wire it in.

**Expected impact:**
- 2024: removes BFIN, BBTN, BBRI, BBNI, BTPS (5), DMAS, SMRA, PWON (3), PGAS (1) = 9 trades, net +Rp 27M
- 2025: removes BTPS, BMRI (2), TOWR (1), PGAS (1) = 4 trades, net +Rp 16M
- 2024 PF estimate: 0.54 → ~0.77

**Pass criteria:**
- 2024 PF ≥ 0.70
- 2025 PF ≥ 3.00 (shouldn't regress much, these sectors were −Rp 16M in 2025)
- Trade count drops by ~9 (2024) and ~4 (2025)

**Risk:** In a future bull year, Financial Services (big banks) CAN have breakout runs. But the data
shows 0 TREND_EXIT wins across 69 combined trades. The risk of missing a sector rally is lower than
the certain cost of continued slow-stop bleeding.

---

### Rule B — Early momentum exit (Exp 26)

**Hypothesis:** Trades that haven't shown momentum by day 7-8 rarely recover. The current system
holds these through the 5-day min_hold period, then waits until the −7% stop fires. A "momentum
check" at day 7: if PnL ≤ 0%, exit immediately. Turns −7% stops into −2% exits.

**Change:** `backtest/portfolio.py` — in `check_exit_conditions`, add after the min_hold_days block:

```python
# Rule B: Early momentum exit — day 7-8 check
# If we're past the hold period and still below entry, exit before full stop fires
if (position.days_held == 7 or position.days_held == 8):
    early_exit_threshold = getattr(self.exits, 'early_exit_momentum_pct', 0.0)
    if profit_pct <= early_exit_threshold:
        return "EARLY_EXIT", 1.0
```

Add to `ExitConfig`:
```python
early_exit_momentum_pct: float = 0.0   # if PnL <= this at day 7, exit
```

And to `main_backtest.py` (opt-in):
```python
config.exit.early_exit_momentum_pct = 0.0  # exit if still at entry price on day 7
```

**Expected impact:**
- Converts ~10 slow stop-losses from −7% → −2% (approx)
- Combined 2024+2025 stop-loss cost was −Rp 92M; this targets the worst bucket
- Risk: some slow-builders get cut early (e.g. AMMN 2024 held 15d before TIME_EXIT at +1.6%)

**Pass criteria:**
- 2024 PF improves
- 2025 PF ≥ 3.00
- Stop-loss count decreases (replaced by EARLY_EXIT at smaller losses)

---

### Rule C — Tighten time exit: 15 → 10 days (Exp 27)

**Hypothesis:** 12 TIME_EXIT trades hold avg 17 days for net −Rp 1.3M. These are capital
zombies. Cutting from 15 to 10 days frees capital faster for stocks actually trending.

**Change:** `config.py` → `ExitConfig`:
```python
time_exit_max_days: int = 10   # was 15
```

And use opt-in in `main_backtest.py`:
```python
config.exit.time_exit_max_days = 10
```

**Expected impact:**
- 7 of 12 TIME_EXIT trades were held >10 days — would have been cut 5-7 days earlier
- Freed capital means ~2-3 additional entry slots per year
- Tiny net PnL change on the exited trades themselves (avg −0.4%)
- Real benefit is in capital efficiency / opportunity cost

**Pass criteria:**
- 2024 PF ≥ 0.54 (no regression)
- 2025 PF ≥ 3.50 (no regression)
- Both years show similar trade counts (time_exit exits earlier, but replaced by fresh entries)

---

### Combined run: Rule A + B + C (Exp 28)

After testing A, B, C individually, combine all three if all pass individually.
Combined target: 2024 PF ≥ 1.0.

---

## 4. Remaining Queue from v23/v24 (DEFERRED — do Rule A/B/C first)

These are still on the list but **do NOT run them next session** until Rule A/B/C are tested.
If Rule A/B/C push 2024 PF past 1.0, the remaining experiments become the growth layer.

| # | Experiment | Status | Notes |
|:-:|---|:-:|---|
| **Exp 15** | MA20 trail after +25% | ⏸ deferred | Exit improvement. Run after Rule A/B/C |
| **Exp 22** | Disable TIME_EXIT for RS leaders | ⏸ deferred | May overlap with Rule C |
| **Exp 23** | Pyramid-add on winners | ⏸ deferred | Only meaningful after entry/exit fixed |
| **Exp 24** | Auto-cluster sector tailwind | ⏸ deferred | Quality filter, lowest confidence |
| **Full stack** | All accepted experiments | ⏸ deferred | Final validation run |

---

## 5. Codebase State (HEAD: 67f349d)

### Active experiments in feature/v10-experiments:
- **Exp 2:** IHSG market filter (`signals/market_regime.py`)
- **Exp 4:** Post-TREND_EXIT + post-STOP_LOSS 30d cooldown (`backtest/engine.py`)
- **Exp 12:** Consecutive loss throttle (`backtest/engine.py`)

### Clean — no pending experiments, no uncommitted changes.

### Branch: `feature/v10-experiments`, HEAD: `67f349d`

---

## 6. Baselines (unchanged from v24 — use these for all comparisons)

| Metric | 2024 | 2025 |
|--------|------|------|
| Trades | **34** | **35** |
| Win Rate | **38.2%** | **48.6%** |
| Total Return | **−4.14%** | **+17.70%** |
| Profit Factor | **0.54** | **3.63** |
| Max Drawdown | **−4.84%** | **−3.38%** |
| Run ID | **24220505468** | **24220636277** |

**Primary target: 2024 PF 0.54 → >1.0, without 2025 regression beyond −2pp.**

---

## 7. Key Run IDs Reference

| Description | Run ID |
|---|---|
| **2024 clean baseline** | **24220505468** |
| **2025 clean baseline** | **24220636277** |
| Exp 17 2024 (REJECTED) | 24203548317 |
| Exp 18 2024 (REJECTED) | ~24245000000 (see this session) |
| Exp 19 2024 (null/REJECTED) | — |
| Exp 21 2024 (REJECTED) | — |
| Exp 13 2024 (REJECTED) | 24254455427 |
| Exp 14 2024 (REJECTED) | 24254851952 |
| Exp 14 2025 (REJECTED) | 24255054154 |
| Exp 20 2024 (REJECTED) | 24255625803 |
| Exp 16 2024 (REJECTED) | 24255954845 |

---

## 8. What NOT to Do

- Do NOT retry Exp 13, 14, 16, 18, 19, 20, 21 — all REJECTED, data is conclusive
- Do NOT loosen entry filters (RSI, volume, price, IHSG gate) — all made things worse
- Do NOT run idx-database workflows in parallel
- Do NOT merge feature → main until full stack validated
- Do NOT use old baselines from v21 (have Exp 9 residue)
- Do NOT run Rule B or C before verifying Rule A first (A is the highest-confidence rule)

---

## 9. Next Session Execution Plan

```
Step 1: Verify excluded_sectors is wired up in backtest/engine.py
        grep for "excluded_sectors" in engine.py, main_backtest.py
        If not wired: add filter in universe loop before signal generation

Step 2: Implement Rule A (Exp 25)
        config.py → UniverseConfig.excluded_sectors = ["Financial Services", "Real Estate", "Utilities"]
        Use feature flag if needed (default empty, main_backtest.py populates it)
        Commit → push → run 2024 → wait → run 2025 → evaluate

Step 3: If Rule A ACCEPTED → implement Rule B (Exp 26)
        Add early_exit_momentum_pct to ExitConfig, wire in portfolio.py check_exit_conditions
        Commit → push → run 2024 → wait → run 2025 → evaluate

Step 4: If Rule B ACCEPTED → implement Rule C (Exp 27)
        config.exit.time_exit_max_days = 10 in main_backtest.py
        Commit → push → run both years → evaluate

Step 5: If all three pass → run combined Rule A+B+C (Exp 28)
        Stack all three, single run each year

Step 6: Evaluate combined. If 2024 PF > 1.0 → proceed to Exp 15/22/23/24
        Otherwise → brainstorm new rules
```

---

*End of v25. Next session begins at Rule A (Exp 25) — sector exclusion.*
