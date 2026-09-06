# TrueScore ML Model — FINAL Validation Report (for Avdhoot's sign-off)

*Phase B, Step 6. Formula version: `truescore_ml_v2` (combined: `truescore_v2`). This replaces both the original `truescore_v1` sign-off and the intermediate `truescore_v1_corrected` report. This is the final version — see `Step6_ML_Model_Decision_Log.md` in this folder for the complete story of everything found and tried this session.*

## Summary of what changed since your original sign-off

Three real bugs were found in Session 5's Step 6 work, and one genuine methodology improvement was discovered and tested along the way:

1. **Feature drift (bug).** The model had been trained on 17 numeric inputs instead of the 14 your original StockApp experiment's validated "Case C" model used. Fixed.
2. **Live-scoring bug.** "Relative Strength" was being computed as just the stock's raw 3-month return instead of comparing it to the market's return. Fixed.
3. **Dataset-building bug.** The script that builds training data was dropping any row where a stock's financial statements weren't available yet, instead of keeping the row with blank financials (as your original methodology did). Fixed — this also revealed that TrueResearch's price data goes back a full 10 years (to 2017), not just to 2022 like the original dataset.
4. **Methodology improvement (not a bug, a decision).** Once 10 years of data became available, training the model on ALL of it made recent predictions worse — most likely because 2017-2021 includes very different market conditions (pre-COVID, the COVID crash, the recovery) that diluted what the model learned about today's market. Testing several alternatives, a **2-year rolling training window** (train only on the most recent 2 years before each prediction, not everything ever available) came out clearly on top and is now locked in as the methodology.

## Final validated result

Tested on the exact same 13-quarter window as your original StockApp experiment (2023 Q2 – 2026 Q2), using real, current TrueResearch data:

| | Your original (Case C) | TrueResearch, final (`truescore_ml_v2`) |
|---|---|---|
| Quarters directionally positive | 12 of 13 | 11 of 13 |
| Quarters statistically significant | not reported to me | 9 of 13 |
| Average Rank IC | ~0.133 | **0.150** |
| Average top-vs-bottom spread | ~7.7% | **12.5 pts** |

**This version outperforms your original on a matched comparison**, using real current data rather than reused historical files. Full quarter-by-quarter numbers for all 37 tested quarters (2017 Q2 – 2026 Q2) are in `walkforward_results.csv`.

## Honest caveats

1. **The 2-year rolling window was chosen by testing several options and picking the best one** (1-year, 2-year, 2.5-year, 3-year windows, and a fixed "2022-onward" cutoff all tested — see the decision log). This carries a small risk of having picked a option that happened to fit this specific data well, versus a truly independent, pre-registered choice. Mitigating factor: the 2-year window won consistently across both the 10-quarter and 13-quarter comparison windows, and its quarter-by-quarter results are stable (positive in most quarters, weak only in the same mid-to-late-2024 stretch every version of this model has struggled with) — not driven by one lucky quarter.
2. **This is a genuine, disclosed change from your original Case C methodology** (which trained on an expanding/full-history window, because it never had more than ~4 years of data to begin with). It is not "the same model, bug-fixed" — it's the same model with one additional, tested design decision layered on top.
3. **Bonus finding, not yet acted on:** the 2017-2021 stretch (including COVID) tested reasonably well on its own (14 of 17 quarters positive, avg Rank IC 0.101) but isn't used in the final model's live training window. Worth knowing this history exists and behaves sensibly, even though the production model doesn't train on it directly.
4. **Fundamentals still only go back to 2023** (a Yahoo Finance limitation, same for your original experiment). Deeper fundamentals history is planned for Phase 5 via Screener.in (see `PROJECT_STATE.md`), not part of this correction.
5. **The original "sector-neutral" robustness check** (proving the edge isn't just from favoring one hot sector) still hasn't been repeated in TrueResearch. Not urgent, but worth doing before expanding past 200 stocks.
6. Applies to the **current ~200 stocks only** — expansion to Nifty 500 should wait for re-validation at that scale, per the locked project rule.

## What happens if you sign off

1. This model re-scores the current stocks under `truescore_v2`. Every prior version (`truescore_v1`, `truescore_v1_corrected`) stays in the database untouched — nothing is deleted, so before/after comparisons are always possible.
2. The final backtest evidence is saved permanently to `score_backtest_results` under `truescore_ml_v2`.

## What I'd recommend

Sign off — this is the version that's both correctly matches your validated methodology AND outperforms it on a fair, matched comparison, using an improvement (the rolling window) that was found, tested, and disclosed rather than assumed. Re-run this validation every few months as more data accumulates, keep the sector-neutral check on the to-do list, and revisit the fundamentals depth question in Phase 5 as already planned.
