# Methodology

How every number is produced: objective metrics, uncertainty and status, time alignment with external signals,
the association analysis, sensitivity and segment checks, and the wording rules. Definitions and assumptions
are in [`requirements_refinement.md`](requirements_refinement.md); sources in
[`source_register.md`](source_register.md); every choice in [`decision_log.md`](decision_log.md).

## 1. Pipeline in one paragraph

`retention run` (i) saves each source untouched in `data/raw/`; (ii) flattens it into source-shaped tables;
(iii) applies the cleaning rules to produce canonical tables with quality flags and a `metric_status`;
(iv) computes the objectives in SQL (DuckDB on Parquet) and adds rates, intervals and status in Python;
(v) joins each objective row to the indicator values already published on its as-of date; (vi) runs the
association tests. Everything is built in a temporary folder and published only if every step succeeds (D-48).

## 2. Objective metrics

**Hire retention** (`sql/hire_outcomes.sql`, `sql/retention_cohorts.sql`). For each hire from 2021-01-01
(INCLUDED; QUARANTINED only in the sensitivity variant) and each hire objective:

```text
observation_date = hire_date + 6 (or 12) calendar months           (D-16; 31 Aug + 6 m = 28 Feb)
outcome = immature      if observation_date > 2025-12-31            (D-18: not in the rate)
          not_retained  if termination_date <= observation_date     (D-17: any exit type)
          retained      otherwise
```

Counts are grouped per hire quarter (trend), hire year and the selected period (verdicts, D-76), per country
and for the company (the company includes the `Unknown` country, D-08). Senior hires are the career levels in
`settings.yaml metrics.senior_levels` (today `Senior Leader`, D-14, D-94).

**Regretted turnover** (`sql/regretted_turnover.sql`). At every month-end M from 2021-01 to 2025-12:

```text
rate(M) = exits with regretted_exit = TRUE in (M - 12 months, M]
          / average of the 13 month-end headcounts from M - 12 months to M     (D-20, D-21)
headcount(D) = hired on or before D and not terminated on or before D
```

Only December values receive a verdict, because consecutive months share 11 of 12 months of data (D-37).
`UNKNOWN` regretted values are counted separately, never as regretted (D-12).

## 3. Uncertainty and status

- **95% Wilson score interval** for every rate (`service/stats.py`, D-33). It stays within 0–100% and behaves
  well for small n and extreme rates. For turnover, n is the average headcount (an approximation).
- **Status** (D-75): *met* when the whole interval is on the good side of the target, *not met* when the whole
  interval is on the bad side, otherwise *inconclusive*.
- **Small samples:** rows with n < 10 carry `small_sample = true` and a warning (D-78).
- **What would settle an inconclusive verdict:** the dashboard computes the number of mature hires at which the
  same rate would give a Wilson interval that excludes the target (new-hire: about 1,982 vs 1,804 today).

## 4. Time alignment: no future information

Each objective row gets an **as-of date** (`service/alignment.py`):

| Rows | As-of date | Decision |
|---|---|---|
| New-hire cohorts (country × hire quarter) | first day of the hire quarter (2024-Q3 → 2024-07-01) | D-28 |
| Senior cohorts (country × hire year) | 1 January of the hire year | D-28, D-36 |
| Turnover (country × December value) | start of the 12-month window (Dec-2024 → 2024-01-01) | D-38 |

Each indicator value is **usable from** `last_day(period_end + lag)`, with monthly +2, quarterly +3, annual
+7 months (D-29). The lags were measured from when each source published its newest value (unemployment ~2
months, HICP ~1–1.5, job vacancies ~3, World Bank GDP ~6.5) and rounded up, so a value may be used later than
possible but never before it was public (D-58).

The join (`sql/as_of_join.sql`) is an **ASOF join**: for each row and indicator, the latest value whose
usable-from date is on or before the as-of date. Monthly indicators give one month, not an average (D-30).
Annual GDP is carried forward but keeps its **own period, frequency and age** (e.g. "2022, annual, 19 months
old"), never presented as a new quarterly value (D-31). A row with no published value yet keeps a visible
null and is excluded from the tests. Example, RO 2024-Q3 (as of 2024-07-01): unemployment 2024-04 (5.2%),
HICP 2024-04, job vacancies 2024-Q1, GDP 2022.

**Limitation:** the APIs return today's revised values, not the historical vintages (D-58).

## 5. Association analysis

**Question:** do the external signals move with the objectives? **Method** (`service/association.py`):

1. **Rows:** new-hire country × hire-quarter cohorts (108 rows, 6 countries); senior country × year (24 rows);
   turnover country × December (30 rows). GDP tests exclude Ireland (D-59), leaving 90 / 20 / 25 rows.
2. **Within-country view** (the formal test, D-54): subtract each country's own average from both the signal and
   the outcome, so stable differences between countries cannot create a pattern.
3. **Spearman rank correlation** ρ with a two-sided p-value (D-32): robust to outliers and non-linear shapes.
4. **Holm correction** over the 4 indicators of each objective, one family per objective, 12 formal tests in
   total (D-34, D-55). A clear association needs Holm p < 0.05.
5. **Bootstrap 95% interval for ρ** (1,000 resamples, fixed seed), labelled **exploratory**: rows are not
   independent (the same country appears in many periods), so the interval is probably too narrow (D-56).
6. **Time check** (D-79): ρ between each signal and time within countries, reported as a confounder warning;
   a **time-adjusted** view (also removing each period's average) and the **pooled** view are shown as
   descriptive context only, never in a Holm family.
7. **Rows are unweighted:** each cohort row counts once whatever its size; n is shown (D-80).

**Hierarchy of evidence** (D-35): `NEW_HIRE_6M` is the **primary** analysis (≈1,800 mature hires, 108 rows).
Senior (low power, 24 rows) and turnover (only 5 December points per country) are **secondary sensitivity
analyses**, run to show how their data limitations affect the analysis, not as equally strong evidence.

**Results (all 12 formal tests):**

| Objective | Indicator | n rows | ρ | p | Holm p |
|---|---|---|---|---|---|
| New-hire (primary) | unemployment | 108 | −0.10 | 0.29 | 0.87 |
| | inflation | 108 | −0.12 | 0.22 | 0.87 |
| | job vacancy | 108 | −0.02 | 0.84 | 1.00 |
| | GDP growth (no IE) | 90 | 0.00 | 0.99 | 1.00 |
| Senior (secondary, low power) | unemployment | 24 | −0.07 | 0.74 | 1.00 |
| | inflation | 24 | 0.20 | 0.35 | 1.00 |
| | job vacancy | 24 | −0.12 | 0.56 | 1.00 |
| | GDP growth (no IE) | 20 | 0.27 | 0.26 | 1.00 |
| Turnover (secondary) | unemployment | 30 | −0.08 | 0.69 | 1.00 |
| | inflation | 30 | −0.40 | **0.03** | 0.12 |
| | job vacancy | 30 | 0.02 | 0.90 | 1.00 |
| | GDP growth (no IE) | 25 | −0.27 | 0.20 | 0.59 |

**Reading:** none of the 12 formal tests shows a clear association after Holm correction. Turnover vs inflation
is the multiple-comparisons example: p = 0.03 alone, 0.12 after correcting for 4 tests. Unemployment trends
strongly with time within countries (ρ −0.71), so time is a plausible confounder. This non-finding is also
what the data's origin predicts: the brief's generator makes retention depend on hire year, country, business
unit, level and contract type, not on these indicators.

## 6. Sensitivity and robustness checks

| Check | How | Result |
|---|---|---|
| Unverified 90-day exits (12) | variant `with_unverified_exits`: counted as real exits (and in headcount) | no verdict changes |
| Unknown "regretted" (2) | variant `unknown_as_regretted`: worst case | no verdict changes |
| Senior definition | Senior Leader + Manager instead of Senior Leader only (D-94) | 81.3% vs 78.2%: not met either way |
| Segment stability | the whole-period verdict per employment type, career level and business unit (D-92; descriptive, many groups) | senior not met in all 6 segments; new-hire inconclusive overall but met for Permanent (88.0%) and Manager (91.1%) |
| Year range | the headline is recomputed for the selected hire years (D-90) | e.g. BG 2025: 31 of 33 |

## 7. Wording rules (D-63)

**Never:** "Spearman proves there is no relationship", "no significant correlation means no relationship",
"GDP causes retention", "unemployment drives turnover".
**Say:** "The exploratory analysis did not show a clear association", "these results are associative, not
causal", "small samples and repeated observations limit inference". Every correlation shown with its effect,
interval, n and (formal tests) Holm p, plus the causation caveat. Unverified exits are "unverified", never
"fake" or "placeholder" (D-57).

## 8. Limitations

Population since 2020 and the early-2021 ramp-up (D-23); unconfirmed assumptions (D-10, D-13, D-14);
fixed-lag approximations and revised values (D-29, D-58); small, dependent samples (7–29 hires per
country-quarter) and exploratory intervals (D-56); unweighted rows (D-80); a discontinued HICP dataset (D-25);
Irish GDP (D-59); synthetic data.
