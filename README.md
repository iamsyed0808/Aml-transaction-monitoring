# AML Transaction Monitoring: Rule Design, Tuning & Dashboard
 Dashboard](dashboard.png)
End-to-end transaction monitoring project: build detection rules, measure them, tune thresholds, report results.

## What it does
- Generates ~75k synthetic transactions across 3,000 accounts with injected typologies (structuring, rapid pass-through, high-risk jurisdiction wires) plus realistic false-positive traps (cash-heavy businesses, escrow/payroll flows).
- Implements three scenarios in Python (pandas) and SQL (`queries.sql`); the script verifies both give identical structuring alerts.
- Sweeps thresholds for each rule and scores precision, recall and F1 against known truth.
- Produces `dashboard.png`, `tuning_results.csv` and `tuning_summary.csv`.

## Results (before -> after tuning)
| Rule | Alerts | Precision | Recall |
|---|---|---|---|
| Structuring (2+ deposits -> 3+ deposits in 3 days) | 65 -> 25 | 38% -> 100% | 100% -> 100% |
| Pass-through (min inflow $5k -> $17.5k) | 39 -> 20 | 51% -> 100% | 100% -> 100% |
| High-risk wires (min $1k -> $10k) | 136 -> 17 | 11% -> 88% | 100% -> 100% |

Total alert volume falls from 240 to 62 (about 74%) with no missed typologies. Caveat: the data is synthetic, so the separation is cleaner than real life. On real data, expect a precision/recall tradeoff and use below-the-line testing to justify thresholds.

## Run it
`pip install pandas numpy matplotlib` then `python aml_monitoring.py`

## Using real data
Swap `build_data()` for a loader of the IBM AML dataset (Kaggle) with columns acct, day, type, amount, country, and use its laundering labels as truth.

## Next steps
Add a customer risk-rating feature, a sanctions name-screening scenario with fuzzy matching, and a Power BI/Tableau version of the dashboard.
