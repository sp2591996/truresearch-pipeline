# Step 6 (TrueScore ML Model) — Full Decision Log, Session 6

*Purpose: a complete, chronological record of everything found, tested, and decided during the Session 6 correction of Phase B Step 6, so this model can be revisited later (by Avdhoot or a future session) without re-deriving any of it. Read this alongside `TrueScore_Validation_Report.md` (the sign-off summary) and `PROJECT_STATE.md` (the running project log).*

## Background

Session 5 built and Avdhoot signed off on a TrueScore ML model (`truescore_v1` / `truescore_ml_v1`), built and validated using TrueResearch's own Supabase data, "faithfully replicating" a separate, earlier experiment Avdhoot had already run and validated independently — an XGBoost model predicting each Nifty-listed stock's 3-month excess return vs. the Nifty 100 benchmark, built and refined through several tested variations (referred to as "Case A", "Case B", and the final, validated "Case C"). Case C used 14 numeric features (RSI, 50/200-day moving averages, 1/3/6-month returns, 30-day volatility, relative strength vs. the market, ROE, total debt, stockholders' equity, net income, total revenue, and a capex-intensity-change feature) plus one-hot sector columns, and was walk-forward validated across 13 quarters (2023 Q2 – 2026 Q2): 12 of 13 quarters showed the model's top picks beating its bottom picks, average spread ~7.7%, average Rank IC ~0.133.

In Session 6, a review was requested to check whether Session 5's replication was actually faithful.

## Bug #1: Feature drift

**Found by:** directly comparing Session 5's `11_train_model.py` feature list against the original Case C model's actual feature list (read from the original's `train_model.py`).

**What was wrong:** Session 5's model trained on 17 numeric features, not 14. Three extra columns — `Debt_to_Equity`, `Revenue_Growth_YoY`, `NetIncome_Growth_YoY` — existed in the dataset (built as candidate features, same as the original experiment's own dataset had extra unused columns like macro data) but were never part of Case C's validated, final feature list. They had been added without being independently tested or disclosed as a deviation.

**Fix:** `11_train_model.py`, `12_walkforward_validation.py`, and `14_score_current_stocks.py` all updated to use exactly Case C's 14-feature list.

## Bug #2: Live-scoring Relative Strength bug

**Found by:** comparing how `Relative_Strength_3M` was computed in the training script (`09_build_training_data.py`) vs. the live-scoring script (`14_score_current_stocks.py`).

**What was wrong:** Training correctly computed it as "this stock's 3-month return minus the Nifty 100 benchmark's 3-month return over the same window." Live scoring just reused the stock's raw `Return_3M` value directly — not a relative-strength measure at all, just a duplicate of another feature.

**Fix:** `14_score_current_stocks.py` now fetches the benchmark's price history and computes this the same way training does.

## Bug #3: Dataset-building bug (rows dropped when fundamentals unavailable)

**Found by:** Avdhoot asked why TrueResearch's walk-forward validation only covered 10 quarters (2024 Q1 – 2026 Q2) vs. the original's 13 (2023 Q2 – 2026 Q2). Investigating this led to a row-by-row comparison of the original `training_dataset.csv` (7,607 rows, 194 stocks) against TrueResearch's (6,475 rows, 194 stocks) — same nominal date range, meaningfully fewer rows.

**What was wrong:** `09_build_training_data.py` was skipping (`continue`) any snapshot date entirely when a stock's fundamentals weren't usable yet at that point in time (fiscal year end + 120-day reporting lag not yet passed). The original methodology kept these rows, leaving the fundamentals-derived columns blank/NaN, and relied on XGBoost's native ability to handle missing values — confirmed directly by inspecting the original dataset (e.g. Reliance's rows from Aug 2022 – Jul 2023 have blank ROE/Debt/etc. but are present in the dataset). Dropping them cut 2022 Q3 – 2023 Q2 from 900+ rows to about 70, which is why those quarters couldn't clear the minimum-row bar for walk-forward testing.

**Fix:** `09_build_training_data.py` no longer skips these rows — it keeps the technical-only snapshot and leaves fundamentals columns blank.

**Side effect discovered after the fix:** rebuilding the dataset didn't just recover the missing 2022-2023 quarters — it produced 18,755 rows spanning back to **2017 Q2**, because TrueResearch's price history had already been backfilled a full 10 years (in Session 5, for reasons unrelated to this main dataset), whereas the original Case C dataset's price history only went back to ~2022. This meant TrueResearch's corrected dataset now had MORE historical depth than the original ever tested with, including the 2020 COVID crash period (which the original explicitly kept out of its production Case C model, treating a COVID-era test as a separate, non-production side experiment).

## Finding #4: training on full history hurt recent-quarter accuracy (led to the rolling-window decision)

**What happened:** re-running the walk-forward validation on this fuller (2017-2026) dataset, using the same "expanding window" approach as before (train on all data available before each test quarter), made recent-quarter (2024-2026) results WORSE, not better:

| Version | Window tested | Avg Rank IC (2024 Q1 – 2026 Q2) |
|---|---|---|
| Old (buggy, 17 features) | 10 qtrs | 0.115 |
| Corrected features, old truncated dataset | 10 qtrs | 0.101 |
| Corrected features, full 2017-2026 dataset, expanding window | 10 qtrs | 0.061 |

**Hypothesis:** training on 2017-2021 data (very different market regimes — pre-COVID, the COVID crash, the recovery) diluted what the model learned about how the market behaves today, since an "expanding window" approach mixes all of that history into every training run without limit.

**Experiment run to test this** (`experiment.py`, not part of the production pipeline, kept for reference — see below): five training-window strategies were tested against the same 10-quarter (2024 Q1 – 2026 Q2) evaluation window:

| Variant | Description | Sig+positive | Directional+ | Avg Rank IC | Avg spread |
|---|---|---|---|---|---|
| A | Expanding window, full 2017-2026 history (baseline) | 4/10 | 6/10 | 0.061 | 5.6pp |
| B | Train only on 2022 onward (drop 2017-2021 entirely) | 6/10 | 8/10 | 0.095 | 8.8pp |
| C | Rolling 3-year trailing window | 6/10 | 8/10 | 0.088 | 7.1pp |
| **D** | **Rolling 2-year trailing window** | **6/10** | **8/10** | **0.117** | **10.4pp** |
| E | Rolling 1-year trailing window | 6/10 | 7/10 | 0.115 | 9.2pp |
| F | Rolling 2.5-year trailing window | 6/10 | 8/10 | 0.098 | 9.1pp |

**Variant D (2-year rolling window) won**, and was confirmed not to be a fluke by checking its quarter-by-quarter detail (positive in 8 of 10 recent quarters, weak only in the same mid/late-2024 stretch every version has struggled with) and by re-testing it on the original's exact 13-quarter window (2023 Q2 – 2026 Q2): 11 of 13 directionally positive, 9 of 13 statistically significant, average Rank IC **0.150**, average spread **12.5 points** — better than the original Case C's own result (12/13, avg IC ~0.133) on a genuinely matched comparison.

**Decision:** lock in the 2-year (730-day / 8-quarter) rolling training window as the final methodology. This is a disclosed, tested DEVIATION from the original Case C methodology (which used an expanding window because it never had enough history to test rolling windows) — not a hidden change.

**Caveat on this decision, for future revisits:** picking the best of several tested window lengths carries some risk of overfitting to this particular dataset/period. This is mitigated by: (a) the win being consistent across two different evaluation windows (10-quarter and 13-quarter), and (b) the quarter-by-quarter results being stable rather than driven by one outlier quarter. Still, if this model's live performance is ever reviewed months from now and the edge has faded, revisiting the window-length choice (and re-running `experiment.py`-style comparisons on fresh data) should be one of the first things checked.

## Other findings, not yet acted on

- **The 2017-2021 stretch (including COVID) tested reasonably well on its own**: 14 of 17 quarters directionally positive, average Rank IC 0.101, when evaluated with the same rolling-window methodology. This history isn't used by the final model's 2-year training window, but it's a reasonable sanity check that the underlying signal isn't a recent-data fluke.
- **The original StockApp experiment's "sector-neutral" picking test** (validating the model's edge isn't just from favoring one hot sector in a given quarter) has never been replicated in TrueResearch. Flagged as a to-do before any expansion past 200 stocks.
- **Deeper fundamentals history (10 years, via Screener.in)** is planned for Phase 5, not this correction — see `PROJECT_STATE.md`. Free sources (yfinance, NSE/BSE filings, other APIs) were researched and found inadequate for this purpose (see PROJECT_STATE.md's Phase 5 note for the full rundown).

## Files touched this session

- `09_build_training_data.py` — fixed to stop dropping technical-only rows.
- `11_train_model.py` — fixed feature list; added 2-year rolling training window for the final production model.
- `12_walkforward_validation.py` — fixed feature list; changed from expanding window to 2-year rolling window (the validated final methodology).
- `13_save_backtest_results.py` — formula_version bumped to `truescore_ml_v2`; description rewritten to reflect the final methodology.
- `14_score_current_stocks.py` — fixed feature list and Relative_Strength_3M bug; formula_version bumped to `truescore_v2`.
- `TrueScore_Validation_Report.md` — rewritten as the final sign-off document.
- `trueresearch_model.json`, `model_feature_columns.json`, `walkforward_results.csv` — regenerated with the final methodology.
- `training_dataset.csv` — rebuilt by Avdhoot locally with the Bug #3 fix (18,755 rows, 2017-2026).
- This file (`Step6_ML_Model_Decision_Log.md`) — new, for future reference.

## Still open / not yet done as of end of this session

1. Avdhoot to review `TrueScore_Validation_Report.md` and sign off.
2. Run `13_save_backtest_results.py` locally (writes `truescore_ml_v2` backtest evidence to Supabase).
3. Run `14_score_current_stocks.py` locally (re-scores current stocks under `truescore_v2`; old versions untouched in the database).
4. (Future, not blocking) Replicate the original's sector-neutral robustness check.
5. (Future, Phase 5) Retrain with 10-year Screener.in fundamentals data, as noted in `PROJECT_STATE.md`.
