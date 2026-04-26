# Handoff Session 2026-04-27 — v37

## What This Session Did

No code changes merged. Pure analysis session: deep-dive on individual trade stories,
price bucket analysis, and four filter experiments — all rejected.

---

## Trade Story Deep-Dives

### HMSP 2025

| Event | Date | Detail |
|-------|------|--------|
| Signal 1 | Apr 24 | Executed at 610. Vol 2.21x, BS +2.56% |
| Exit | May 9 | FF_EXIT at 595. −2.85%. Foreigners sold 5 consecutive days. |
| Signal 2 | May 22 | bs_tba_filter — gapped down to 655 on T+1 (BS=−2.24%), TBA negative |
| Sep mega-move | Sep 8–Nov | +67% from trough (545→910). Missed: vol_ratio 9–13x > vol_spike_max=5.0 |

Signal 2 block was the right call — stock fell to 530 by August after the May rejection. Sep move was driven by extraordinary volume (695M–1.45B shares/day) from a major corporate catalyst — impossible to enter within vol_max=5.0 constraint.

### DMAS 2025

| Event | Date | Detail |
|-------|------|--------|
| Signal | Apr 25 | Executed. Vol 3.2x, BS +2.72%, close 151 |
| Entry day T+1 | Apr 28 | Opened 152, closed 178. 938M shares, 167B IDR. +15.6% on entry day |
| Partial profit | Apr 28 | +13.83% on 20% of position (+2.53M) |
| Distribution | May 7 | 628M shares at 176 — big money selling into rally |
| Gap down | May 8 | Opens 150 (−14.8% overnight) |
| TREND_EXIT | May 9 | 136. −12.04% on main position |
| Net result | | −6.29M IDR. Event-driven spike-and-collapse. |

**Why it can't be avoided pre-entry:** signal on Apr 25 was clean (vol 3.2x, within range). Explosion happened on T+1 at open (only +0.7% gap — below gap_up filter). Partial profit at +10% was the best available mitigation. Stock never recovered above 150 after May 8 collapse.

### MTEL 2025

| Event | Date | Detail |
|-------|------|--------|
| Signal | May 15 | Executed. Vol 3.46x, BS +2.31%. Close 665, breaking 20d high of 650 |
| Entry | May 16 | 680. Entry price = approx 52-week high (dist_from_52w_high = −2.2%) |
| Hold | May 16–26 | Stock declined from 680 to 645. Never recovered entry price |
| STOP_LOSS | May 26 | 633.62. −7.19%. Day 6, first day stop allowed to fire |
| Saved from | May 28 | 282M volume crash to 605 (−11% from entry). Stop prevented worse loss |
| Signals 2/3/4 | Jul/Nov/Dec | All throttled (rolling 10d limit). Weak BS (0.83–0.86%). |
| Year-end rally | Dec 30 | Close 700, +30% from Oct low. No signal cleared throttle. |

---

## Price Bucket Analysis (180 trades, 3 years combined)

| Bucket | N | WR | Avg PnL% | PF | BW(>20%) |
|--------|---|----|----------|----|----|
| 150–199 | 8 | 62.5% | +3.38% | 3.56 | 1 |
| 200–299 | 10 | 50.0% | +0.58% | 2.46 | 1 |
| 300–499 | 15 | 40.0% | +6.08% | 7.44 | 2 |
| **500–999** | **23** | **34.8%** | **−2.68%** | **0.51** | **0** |
| 1000+ | 124 | 45.2% | +4.19% | 5.90 | 7 |

**Key finding:** 500–999 is the worst bucket (PF 0.51, zero big winners, consistent across all 3 years).
150–199 is actually fine — INET +31% (entry 193) and CUAN +19.6% (entry 160) live here.

## 52-Week Proximity Analysis (180 trades)

| Bucket | N | WR | Avg PnL% | PF | BW(>20%) |
|--------|---|----|----------|----|----|
| At 52w high (0 to −5%) | 55 | **61.8%** | +5.35% | 7.71 | 4 |
| −5% to −15% | 52 | 40.4% | +7.27% | 8.36 | 6 |
| −15% to −25% | 39 | 38.5% | −1.41% | 0.89 | 0 |
| −25% to −40% | 31 | 32.3% | −0.19% | 2.10 | 1 |

Counter-intuitive: the "at 52w high = resistance" bucket has the BEST win rate (61.8%).
Mega-winners INET +90%, WIIM +43%, HRTA +34% all came from this zone. Do not filter on 52w proximity.

---

## Four Experiments — All Rejected

### 1. MPW 6 → 8

| Year | Baseline | MPW=8 | Delta |
|------|----------|-------|-------|
| 2023 | +48.50% | +46.12% | −2.38pp |
| 2024 | +31.05% | +20.63% | **−10.42pp** |
| 2025 | +127.86% | +116.81% | **−11.05pp** |

Extra 8–11 trades/year are lower-quality false breakouts that MPW=6 correctly throttles.
MPW=6 confirmed as sweet spot.

### 2. Block 500–999 Price Range

| Year | Baseline | Block500 | Delta |
|------|----------|----------|-------|
| 2023 | +48.50% | +45.32% | −3.18pp |
| 2024 | +31.05% | +23.51% | −7.54pp |
| 2025 | +127.86% | +66.35% | **−61.51pp** |

The filter doesn't directly block JARR (signal close=1005) or PTRO (signal close=1720).
But it cascades: different capital allocation causes JARR Aug 20 entry to become "throttle" →
system enters Aug 27 at 1345 instead of 1065, exits Sep 12 at +12% instead of +219%.
Do not implement. Cascade effects make price-range blocks unpredictable.

### 3. Prior Avg Daily Value ≥ 2B (DMAS Prevention Attempt)

Computed `avg_daily_value_20d.shift(1)` (pre-breakout base liquidity, excludes signal day spike).
DMAS prior avg = 1.95B → blocked at 2B threshold.

Problem: every threshold from 1B to 5B also blocks HRTA 2023 +34.42% (prior avg 0.75B).
Blocked trades at 2B average +5.07% PnL — slightly profitable. Removing them hurts.
Do not implement.

### 4. 52-Week Historical Resistance Breakout

Added `close > high_252d.shift(1)` — requires stock to make genuine new 52-week high.

| Year | Baseline | 52w Filter | Delta |
|------|----------|------------|-------|
| 2023 | +48.50% | +31.65% | **−16.85pp** |
| 2024 | +31.05% | +34.08% | +3.03pp |
| 2025 | +127.86% | +81.70% | **−46.16pp** |

Blocks 44–50 trades/year. Blocks PANI +90% (2023), INET +90%/TINS +96%/BRPT +69% (2025).
Mega-winners typically break out BELOW their prior-year high during recovery from a trough.
Requiring 52w high breakout systematically misses them. Do not implement.

---

## FF_EXIT Explanation (for reference)

FF_EXIT fires when: stock is `is_foreign_driven=True` AND `ff_consecutive_sell >= 5`.

`is_foreign_driven` = rolling 60d directional consistency > 0.20:
```
consistency = |sum(net_foreign, 60d)| / sum(|net_foreign|, 60d)
```
If foreigners were directionally consistent (mostly buying or mostly selling) over 60 days,
the stock is flagged as foreign-driven. FF exit only applies to these stocks.
Threshold 0.20 is intentionally low — most large-cap stocks qualify.

---

## Remaining Priorities

1. **⚠️ MANDATORY — Pre-compute `top_broker_acc` daily CSV for GitHub**
   BS/TBA filter is no-op in live (84 signals blocked in backtest pass through live).
   Fix: pre-compute per ticker/day → `broker_acc_daily.csv` → commit to repo.
   Files: `database/data_loader.py`, `backtest/engine.py`, `signals/signal_combiner.py`.

2. **Mega winner capture rate analysis** — Cross-reference `mega_winners_analysis.xlsx`
   against `trade_log.csv` (all 3 years). Reports in `reports_local_2023_liq05/`,
   `reports_local_2024_liq05/`, `reports_local_2025_liq05/`. Compute:
   - How many of the 52/53/87 liquid mega-winners did we capture?
   - Which filter blocked each missed one?
   - Is there a pattern in the missed ones that suggests a fix?

3. **fp_ratios.json** — Needs regeneration with 2023-2025 data for CI compatibility.

4. **2021-2022 validation** — Run backtests for earlier years once price data confirmed.

5. **min_profit_to_add 15%→10%** — Lower pyramid trigger, test independently.
