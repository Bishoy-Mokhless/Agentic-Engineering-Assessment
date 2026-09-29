# Requirements refinement

The brief is "deliberately incomplete". This page records how the open question was narrowed before building:
the decision the product supports, the questions and assumptions, the metric definitions, the acceptance
criteria, the rejected scope and the consequences. Decision numbers (D-xx) point to
[`decision_log.md`](decision_log.md), which holds the options and reasons for each.

## 1. The decision the product supports

> **Leaders want to know whether each retention objective is on track, and whether external labour-market and
> macroeconomic conditions add useful context, without over-claiming.**

So the product must: (1) give an auditable, uncertainty-aware status for each of the three objectives, by
country, time and workforce segment; (2) place official signals next to them without using future
information; (3) test whether they move together, honestly; (4) show what the numbers rest on (sources,
freshness, exclusions, method).

It does **not** forecast attrition, explain individual exits, or claim causes (D-63).

## 2. Questions and how each was resolved

Five questions were prepared for the one clarification round. They were **not submitted**: each one needed a
decision in the code regardless, so each was resolved with a documented assumption, and the verdicts were
checked against the assumption where possible.

| # | Question | Assumption taken | Evidence it does not drive the result |
|---|---|---|---|
| Q1 | Is an HTML/JS dashboard served by a small local API acceptable as the "HTML" experience layer? | Yes: plain HTML + JS + Chart.js, fed by FastAPI (D-04, D-05) | The brief lists HTML as an option; nothing depends on a paid tool |
| Q2 | Is `Sr Mgmt` the same level as `Senior Leader`? | Yes, a label variant (10 rows, D-13) | Mapping kept visible (`career_level_source`); in `config/mappings/career_levels.csv` |
| Q3 | Which career levels count as senior hires? | `Senior Leader` only (D-14), a setting since D-94 | Senior + Manager gives 81.3% vs 78.2%: **not met either way** (D-94) |
| Q4 | Is an exit exactly 90 days after hire, with a blank type, a real exit or a system default? | Unverified: quarantined from the primary numbers, added back in a sensitivity variant (D-10, D-57) | **No verdict changes** when they are counted |
| Q5 | Does the events file hold the full workforce or only people hired since 2020? | Only hires since 2020 (earliest hire 2020); reporting starts 2021 (D-23) | Stated as a limitation; explains the early-2021 turnover ramp-up |

The objectives' own business notes were treated as requirements: *address incomplete observation windows*
(→ D-18), *document which career levels qualify* (→ D-14), *state the denominator and average-headcount
convention* (→ D-20).

## 3. Data assumptions (the data is intentionally imperfect)

| Issue in the HR file | Rows | Rule | Decision |
|---|---|---|---|
| Repeated employee rows | 7 | keep the latest `record_updated_at`; log the removed row | D-07 |
| Non-standard country codes `EL`, `ROM` | 8 | map to `GR`, `RO`; keep the original | D-08 |
| Blank country | 9 | `Unknown`: company totals only, no country view or join | D-08 |
| Career level `Sr Mgmt` | 10 | → `Senior Leader` | D-13 |
| Missing hire date | 5 | excluded from metrics, listed | D-09 |
| Termination before hire | 5 | excluded, listed | D-09 |
| Blank exit type, exactly 90 days after hire | 12 | `UNVERIFIED_EXIT`, quarantined, sensitivity variant | D-10, D-57 |
| Blank exit type, other tenure | 1 | type `Unknown`, kept | D-11 |
| Blank `regretted_exit` on an exit | 2 | `UNKNOWN`, never imputed; worst-case variant | D-12, D-72 |

**Principle (from D-10 and D-12):** uncertain data is preserved, flagged and quarantined from the primary KPI;
it is never deleted or imputed; its impact is shown through sensitivity analysis. Result: 2,407 rows →
2,400 employees (2,378 included, 12 quarantined, 10 excluded).

## 4. Metric definitions

| | `NEW_HIRE_6M` | `SENIOR_HIRE_12M` | `REGRETTED_TURNOVER_12M` |
|---|---|---|---|
| Target | ≥ 86% | ≥ 90% | ≤ 7.5% |
| Population | hires from 2021-01-01, INCLUDED (D-23, D-73) | same, career level in `senior_levels` (D-14, D-94) | INCLUDED employees |
| Cohort | hire quarter (D-19); verdicts per hire year and for the selected years (D-76) | same; formal test at year grain (D-36) | each month-end 2021-01 … 2025-12 (D-21); verdicts on December values (D-37) |
| Window | hire date + 6 **calendar** months (D-16) | + 12 months | the 12 months ending at the month-end |
| Numerator | still employed at the window end; any exit on or before it counts as not retained, whatever the type (D-17) | same | exits with `regretted_exit = TRUE` in the window (D-12) |
| Denominator | mature hires only; windows ending after 2025-12-31 are "not yet measurable" (D-18) | same | average of 13 month-end headcounts (D-20) |
| Censoring | immature hires reported separately | same | - |
| Invalid records | EXCLUDED never enter; QUARANTINED only in the sensitivity variant | same | same; quarantined people out of headcount and exits (D-22) |
| Uncertainty and status | 95% Wilson interval (D-33); met / not met only if the whole interval is on one side, else inconclusive (D-75) | same | same (headcount as n: an approximation) |
| Small samples | `small_sample` warning when n < 10, still shown (D-78) | same | same |

## 5. Acceptance criteria

Each criterion is checkable, and where it is verified is named.

| # | Criterion | Verified by |
|---|---|---|
| AC-1 | One documented command runs the whole pipeline offline from committed snapshots (`retention run`) | README; `tests/api` and `tests/ui` build data with the real offline pipeline |
| AC-2 | Reruns are deterministic: same inputs → identical outputs (checksums in `_build.json`, fixed seed) | lineage records; D-48, D-74 |
| AC-3 | Raw snapshots are never overwritten; a failed run leaves `data/curated/` unchanged | `tests/unit/test_raw_and_hr.py` (existing snapshot never overwritten), `test_curate_step.py` (failed run keeps previous outputs) |
| AC-4 | A source that cannot be fetched falls back to its last good snapshot and is marked *stale*; with no snapshot the run stops with a clear message | `tests/unit/test_ingest.py` |
| AC-5 | Every HR row is accounted for: 2,407 rows = 7 repeats + 2,400 employees, each with a status and flags that name their decision | quality report; `tests/unit/test_hr_curation.py` |
| AC-6 | All three objectives have n, rate, 95% interval and status per year and for the period; quarters and months have no verdict | `tests/unit/test_metrics.py`, `tests/api` |
| AC-7 | No aligned row uses an indicator value published after the cohort's as-of date; carried-forward values keep their own period, frequency and age | `tests/unit/test_alignment.py`; schema contract |
| AC-8 | Formal association tests are within-country, 4 per objective, Holm-corrected; pooled and time-adjusted views are labelled descriptive; wording is associative only | `tests/unit/test_association.py`; `tests/ui` |
| AC-9 | The dashboard offers country, time, objective and (combinable) workforce-segment filters; views for Explore, Understand, Challenge and Trust | `tests/ui/test_dashboard_ui.py` |
| AC-10 | Empty and error states are shown, not blank pages (no data slice, bad filter → 400 message, API outage) | `tests/ui` |
| AC-11 | Basic accessibility: labelled controls, keyboard tabs, a table twin for every chart, status as icon + word | `tests/ui` |
| AC-12 | Each table passes its schema contract before it is written | `domain/schemas.py`; `tests/unit/test_schemas.py` |

## 6. Rejected scope (deliberate cuts) and consequences

| Not done | Why | Consequence |
|---|---|---|
| Streamlit / Power BI front end (D-04) | brief's HTML option; version control and testability | a hand-built page with its own tests |
| Static JSON feed (D-05) | filters must combine freely | a small read-only API |
| Conditions **during** the 6-month window as the join (D-28, option C) | uses hindsight | only "as known at hire" values; named as a next step |
| Per-employee as-of dates (D-28) | complex, barely different | one as-of date per cohort |
| Labour cost index; World Bank unemployment / CPI (D-26, D-27) | provisional values; duplicate lenses; more tests | 4 indicators, 4 lenses |
| Logistic regression, Kaplan–Meier, block bootstrap (D-32, D-18, D-56) | time; small samples | descriptive and rank-based methods, caveats stated |
| Privacy suppression of groups under 5 (D-78) | data is synthetic | warning under 10; noted for production |
| CI with GitHub Actions (D-51, D-60, D-64) | timebox | tests run locally |
| A dashboard filter for the senior definition (D-94) | not needed for the verdict | a setting instead |
| Excluding probation exits from new-hire retention | would redefine the business's metric | kept "any exit counts"; a question for the business |

## 7. Consequences to keep in mind

- **Population since 2020:** early headcounts are small; early-2021 turnover is high (ramp-up, not a verdict).
- **Revised data:** today's API values are revised; "as known then" is approximated with fixed lags (D-58).
- **Small, dependent samples:** 7–29 hires per country-quarter; bootstrap intervals are exploratory (D-56).
- **Synthetic data:** the brief's generator makes retention depend on workforce attributes, not on the
  indicators, so a non-finding is the expected honest result.
