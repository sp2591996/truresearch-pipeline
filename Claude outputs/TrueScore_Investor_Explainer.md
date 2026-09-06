# Explaining TrueScore to Investors

*A layered explanation — read top to bottom for a full pitch, or pull just the layer that fits your audience/moment. Uses TrueScore's actual, current validated numbers (Session 6, formula_version `truescore_v2`).*

---

## Layer 1 — The one-line pitch (say this first, always)

> "TrueScore is a machine learning model that ranks Indian stocks by how likely they are to outperform the market over the next 3 months, using both price behavior and company financials — and unlike most retail research tools, we've actually tested it: on a matched historical comparison, it beat the market's ranking in 11 of the last 13 quarters."

That's it. Lead with the claim and the one number that proves you tested it. Everything else is elaboration for whoever asks a follow-up question.

---

## Layer 2 — The mechanism, in plain language (for anyone who asks "how")

TrueScore looks at two kinds of information about a stock, updated regularly:

1. **How the stock has been behaving** — its recent price momentum, whether it's trending up or down, how volatile it's been, and how it compares to the broader market.
2. **How healthy the underlying company is** — profitability, debt levels, revenue trends, and how much it's investing in itself.

A machine learning model (a well-established, industry-standard technique called gradient-boosted trees, specifically XGBoost) is trained to find patterns across both kinds of information that have historically preceded a stock beating the market over the following 3 months. Once trained, it scores every stock in the coverage universe and ranks them — the higher the score, the more the model expects that stock to outperform.

This ranking is one half of TrueScore. The other half is a simple, transparent valuation check (is the stock cheap or expensive relative to its own sector peers). The two are blended 50/50 into the final 0-100 score you see on the platform.

**The one honest caveat to volunteer here, unprompted:** this is a *research signal*, not a guarantee or a recommendation. It's a statistically real edge, not a crystal ball — it's right more often than random chance over many stocks and many quarters, not right about every single stock every single time.

---

## Layer 3 — The evidence (for a technical or skeptical investor)

This is where you show your work. Investors who ask deeper questions are testing whether you actually understand your own model or are just repeating a number someone gave you — so know these cold:

**How it's validated:** "walk-forward" testing — the gold-standard method for this kind of model. Instead of training once and checking the result, the model is retrained repeatedly using only data that would have actually been available at each point in time, then tested on the next 3 months it had never seen. This is repeated quarter by quarter across years of history, so the model is never accidentally being graded on data it already saw.

**The headline result:** on a 13-quarter test (mid-2023 to mid-2026), the model's top-ranked picks beat its bottom-ranked picks in 11 of 13 quarters, with an average outperformance gap of 12.5 percentage points between the two groups. In statistical terms, the model's ranking showed a real (not-by-chance) predictive signal in 9 of those 13 quarters.

**The specific technical measure, if asked:** we track something called "Rank IC" (rank information coefficient) — a standard measure of whether a model's predicted ranking actually lines up with what happened. A score of 0 means no better than a coin flip; ours currently averages 0.150 across the tested period. That's a modest, genuine edge — not a claim of near-perfect prediction, which no honest model would claim for equity markets.

**What it does NOT do (say this before they ask):**
- It does not predict individual-day price moves or try to time entries/exits.
- It has not been tested through a full market crash yet (our usable financial-statement data only goes back to 2023) — though a separate check on older technical data through 2020-2021 (including COVID) showed the underlying signal held up reasonably well even then.
- There have been real weak stretches — notably mid-to-late 2024 — where the model's ranking didn't add value or was mildly wrong. We don't hide this; it's expected for any market-based model and is part of why we keep re-testing it.
- It currently covers our initial ~200-stock universe, not the full market yet, and any expansion only happens after re-validating at the larger scale — we don't scale up on faith.

**On methodology rigor, if pressed:** the model's design was directly inherited from, and in a recent internal review, actually outperformed, an earlier independently-validated version of the same approach — and every change to the methodology (including a recent improvement to how much historical data it trains on) was tested against real walk-forward results before being adopted, not assumed to help.

---

## A ready-made Q&A for common investor pushback

**"How is this different from just following analyst ratings?"**
Analyst ratings are opinions, often unaudited and rarely back-tested publicly. TrueScore's predictions are logged and can be checked against what actually happened, quarter by quarter, forever — the model's track record is a queryable database table, not a claim.

**"Isn't this just backtesting bias — you tuned it until it looked good?"**
Fair question, and the honest answer is: some tuning risk always exists in any model built this way. We mitigate it by testing on strictly out-of-sample future quarters (walk-forward, never data the model could have seen), and by checking that any change performs consistently across multiple different time windows, not just one lucky test. We also log every methodology version we've ever used — including the ones that didn't work — so nothing is quietly cherry-picked after the fact.

**"What happens when it's wrong?"**
It will be wrong sometimes — any real, honest edge in markets is modest, not perfect. We track performance continuously (not just once) and re-validate the model periodically as new data comes in, specifically so a fading edge gets caught rather than assumed away.

**"Is this investment advice?"**
No — and we say so on every page that shows a score. TrueScore is framed and regulated as a research signal, consistent with operating without needing SEBI Research Analyst registration. It's an input to an investor's own decision-making, not a recommendation to buy or sell.

---

## How to use this in practice

- **Elevator pitch / first meeting:** Layer 1 only, maybe one sentence from Layer 2 if they ask "how."
- **Product demo or deeper conversation:** Layers 1 and 2, with the "what it does NOT do" list ready if they push.
- **Due diligence, technical investor, or written materials:** all three layers. Consider attaching `Step6_ML_Model_Decision_Log.md` (the internal working document) if a technical investor wants to see actual methodology rigor — it shows real bugs found and fixed, not just a polished final number, which tends to build more trust with sophisticated investors than a spotless narrative would.
