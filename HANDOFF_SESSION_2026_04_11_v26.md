# SahamGPT-Bot — Session Handoff Document
> Last updated: April 11, 2026 (v26 — STRATEGY PIVOT: bottom-up mega-winner approach)
> Repo: https://github.com/nstnarie/SahamGPT-Bot (public, Python 100%)
> Paste this at the start of a new chat to resume seamlessly.

---

## CLAUDE: READ THIS BEFORE DOING ANYTHING

1. **Read `DEVELOPER_CONTEXT.py`** — locked rules, hard parameters.
2. **`idx-database` is shared** — NEVER run workflows in parallel.
3. **Branch is `feature/v10-experiments`** — HEAD was `67f349d` (v25 clean), new commits added for v26.
4. **Previous approach (Exp 13-21 filter tweaks + Rule A/B/C defensive rules) is SUPERSEDED** by this new bottom-up strategy.
5. **v25 handoff still has valid baseline data and experiment history** — reference it for historical context only.

---

## 1. Strategy Pivot — Why

After 7 consecutive rejected experiments (all tried to loosen entry filters) and 3 proposed defensive rules (sector exclusion, early exit, tighter time exit), the user decided to fundamentally change approach.

**Old approach:** Incrementally tweak filters on existing breakout system.
**New approach:** Start from proven mega-winners, reverse-engineer what predicts them, rebuild entry rules from scratch if needed.

### The 9-Step Plan

**Phase A — Capture mega winners (Steps 1-5):**
1. Identify real mega-winner stocks (>50% gain at any point in 2024/2025)
2. Find patterns that predict these mega-winners using all available data
3. Get additional data if needed (scrape new sources)
4. Adjust system trading rules (can rewrite entry rules entirely)
5. Backtest to validate we capture the mega winners (win rate doesn't matter yet)

**Phase B — Filter out losers (Steps 6-9):**
6. Analyze backtest loss trades, find patterns to prevent them
7. Get additional data if needed for loss filtering
8. Adjust framework based on loss analysis
9. Backtest to validate improved win rate and profitability

**Key principle:** Step 1-5 = make sure we catch winners. Step 6-9 = filter out losers. Sequential, not parallel.

---

## 2. Step 1 — Mega Winner Identification (IMPLEMENTED)

### New files created:
- **`scripts/identify_mega_winners.py`** — Standalone script that downloads yfinance data for all 137 tickers and identifies stocks with >50% trough-to-peak gain in 2024 and 2025
- **`.github/workflows/identify_mega_winners.yml`** — Manual workflow to run the script and upload Excel artifact

### How to run:
```bash
gh workflow run identify_mega_winners.yml
```

### Output:
- Artifact: `mega-winners-analysis` containing `mega_winners_analysis.xlsx`
- Three sheets: "Mega Winners 2024", "Mega Winners 2025", "All Stocks Summary"
- Columns: ticker, sector, year, max_drawup_pct, trough/peak dates and prices, duration, year return

### Algorithm:
- Max drawup: tracks running minimum (daily low) and computes gain to daily high
- O(n) per ticker per year
- Uses intraday extremes (low for trough, high for peak) for true maximum gain

### Important notes:
- This workflow does NOT touch `idx-database` — safe to run anytime
- Expansion batch tickers (added Apr 2026) likely won't have 2024/2025 data — they're skipped gracefully
- ~5 min expected runtime (137 tickers x ~2s each)

---

## 3. Current Step: Run Step 1 workflow, download results

### Immediate next actions:
1. Commit and push the new files
2. Run `gh workflow run identify_mega_winners.yml`
3. Wait for completion
4. Download and review the Excel artifact
5. Proceed to Step 2: pattern analysis of mega-winners

---

## 4. Baselines (unchanged from v25)

| Metric | 2024 | 2025 |
|--------|------|------|
| Trades | **34** | **35** |
| Win Rate | **38.2%** | **48.6%** |
| Total Return | **-4.14%** | **+17.70%** |
| Profit Factor | **0.54** | **3.63** |
| Max Drawdown | **-4.84%** | **-3.38%** |
| Run ID | **24220505468** | **24220636277** |

These remain the comparison baselines for any future backtests.

---

## 5. What NOT to Do

- Do NOT retry Exp 13-21 (all REJECTED, data is conclusive)
- Do NOT run idx-database workflows in parallel
- Do NOT skip Step 1-5 to jump to Step 6-9
- Do NOT optimize for win rate until mega-winner capture is validated (Step 5)

---

*End of v26. Current action: push code and run Step 1 workflow.*
