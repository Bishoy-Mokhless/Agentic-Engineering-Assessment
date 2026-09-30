# External Signals × Workforce Retention

A small, defensible data product for the (fictional) company **Asteria Consumer Products**: it measures
three workforce-retention objectives across six European countries (GR, RO, PL, IT, IE, BG) and places them
next to four official labour-market and economic signals, showing what can and cannot be learned from them.

- **Emphasis:** Software (maintainable layers, API, packaging, tests across service and UI, accessible dashboard).
- **Stack:** Python 3.11, pandas, DuckDB (SQL on Parquet), FastAPI, plain HTML/JS + Chart.js, pytest + Playwright.
- **Every decision** (options, choice, reason) is recorded in [`docs/decision_log.md`](docs/decision_log.md)
  as D-00 … D-95; code comments point to those numbers.

---

## 1. The problem and the chosen scope

Leaders asked whether external conditions help explain retention. Before building, the question was narrowed
(see [`docs/requirements_refinement.md`](docs/requirements_refinement.md)):

| Objective | Target | Our definition (decision) |
|---|---|---|
| `NEW_HIRE_6M` new-hire six-month retention | ≥ 86% | Share of hires still employed 6 **calendar** months after hire; any exit on or before that date counts (D-16, D-17). Hires whose window ends after 2025-12-31 are *not yet measurable* and left out of the rate (D-18). |
| `SENIOR_HIRE_12M` senior-hire twelve-month retention | ≥ 90% | Same with 12 months; senior = `Senior Leader` (D-14), a setting in `config/settings.yaml` (D-94). |
| `REGRETTED_TURNOVER_12M` trailing-12-month regretted turnover | ≤ 7.5% | Confirmed regretted exits in the 12 months to each month-end ÷ average of 13 month-end headcounts (D-20, D-21); verdicts on December values only (D-37). |

**Verdicts are uncertainty-aware (D-75):** 95% Wilson interval; *met* / *not met* only when the whole interval
is on one side of the target, otherwise *inconclusive*. Verdicts per year and for the selected period;
quarters and months are trend lines only (D-76).

**External signals (4 indicators, 2 providers, D-24…D-27):**

| Lens | Indicator | Provider / dataset | Frequency |
|---|---|---|---|
| Labour supply | Unemployment rate | Eurostat `une_rt_m` | monthly |
| Cost of living | HICP inflation | Eurostat `prc_hicp_manr` | monthly |
| Labour demand | Job vacancy rate | Eurostat `jvs_q_nace2` | quarterly |
| Economic cycle | GDP growth | World Bank `NY.GDP.MKTP.KD.ZG` | annual |

Details, licences and limitations: [`docs/source_register.md`](docs/source_register.md).

**Out of scope (deliberate cuts):** CI pipeline (D-51, D-64), per-employee survival models, historical data
vintages, a production deployment. Next steps are listed in section 8.

**Clarification questions:** five questions were prepared (D-04/D-05, D-13, D-14, D-10, D-23) but not
submitted, because each needed a decision in the code regardless. Each was handled with a documented
assumption, and verdicts were checked against the assumption where possible (e.g. D-94: the senior verdict
stays *not met* even if Managers count as senior).

---

## 2. Architecture

Two flows that share only files on disk:

```text
 FLOW A  retention run  (batch job)                     FLOW B  retention serve  (web app)
 ────────────────────────────────────                     ─────────────────────────────────
 Eurostat API ─┐                                          Browser: dashboard/index.html + app.js
 World Bank API┼─> ingest  ──> data/raw/                              │ GET /api/...
 HR CSV files ─┘   (client/)   untouched snapshots                    ▼
                               │                           api/routers/*.py        (controllers)
                               ▼ curate (service/)                    ▼
                 data/curated/source_shaped/  provider-shaped  service/dashboard_queries.py (service)
                               ▼                                      ▼
                 data/curated/canonical/      cleaned + flags  repository/curated_store.py (repository)
                               ▼ metrics (sql/ + service/)            ▼
                 data/curated/analytical/     objectives,      ─────> reads data/curated/*
                                              time join, tests
```

| Layer | Folder | Holds |
|---|---|---|
| Raw | `data/raw/` | Provider payloads byte-for-byte, one folder per fetch, with `metadata.json` (URL, time, SHA-256) and a `latest.json` pointer; the HR pack as delivered (checksums verified) (D-41, D-48, D-66) |
| Source-shaped | `data/curated/source_shaped/` | Flattened tables, provider codes and text unchanged (D-71) |
| Canonical | `data/curated/canonical/` | Standard codes, typed values, quality flags and `metric_status`, one long indicator table, `quality_report.json` (D-72, D-73) |
| Analytical | `data/curated/analytical/` | `hire_outcomes`, `retention_cohorts`, `regretted_turnover`, `aligned_observations`, `association_results` |

**Reliability:** every run builds in `data/.tmp/<run_id>/` and is swapped into `data/curated/` only if every
step succeeds (D-48); raw snapshots are never overwritten; each layer has a `_build.json` lineage record
(run id, inputs and outputs with SHA-256, D-74); `data/curated/run_summary.json` records each run and each
source's status (fresh / replayed / stale / unavailable, D-62, D-68). A fixed random seed makes reruns
byte-identical (D-48).

**Code layout** (`src/retention/`, organised by layer, D-40):

| Package | Role |
|---|---|
| `cli.py`, `config.py` | entry point; typed, validated settings from `config/settings.yaml` |
| `client/` | adapters for Eurostat, World Bank, the HR files; HTTP timeouts and retries (D-47) |
| `pipeline/` | the batch job and its steps (ingest, curate, metrics, analyse), lineage, run summary |
| `domain/` | schema contracts (Pandera), quality flags, periods, source status, errors |
| `repository/` | raw snapshots, curated layers, DuckDB SQL runner, mapping tables |
| `service/` | business rules: HR curation, indicator parsing/curation, metrics, statistics, time alignment, association, API queries |
| `sql/` | the metric and join queries (`hire_outcomes`, `retention_cohorts`, `regretted_turnover`, `as_of_join`) |
| `api/` | FastAPI app, routers, dependency injection, error handling |

Production mapping (ADF, Databricks lakehouse, Power BI, secrets, scheduling, observability, access,
promotion): [`docs/architecture.md`](docs/architecture.md).

---

## 3. Prerequisites

- Python **3.11+** (developed with 3.11.9)
- No database server, no cloud account, no internet needed for the default run (saved snapshots are in the repo)
- Chromium for the browser tests only (installed once with Playwright, below)

## 4. Install (once)

```bash
git clone https://github.com/Bishoy-Mokhless/Agentic-Engineering-Assessment.git
cd Agentic-Engineering-Assessment
python -m venv .venv
# Windows (cmd):         .venv\Scripts\activate.bat
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# macOS / Linux:         source .venv/bin/activate
pip install -e ".[dev]"
python -m playwright install chromium        # only for the UI tests
```

The `pyproject.toml` ranges allow newer versions. To install the exact versions this project was built and tested with, use
`pip install -r requirements.lock` followed by `pip install -e . --no-deps`.

## 5. Run

```bash
retention run              # the whole pipeline, offline from the committed snapshots (default)
retention run --refresh    # fetch fresh data from Eurostat and the World Bank first, then run
retention serve            # dashboard at http://127.0.0.1:8000/   API docs at http://127.0.0.1:8000/docs
```

`retention run` takes under a minute and logs every step, the headline verdicts and the formal test results.
If a source cannot be fetched with `--refresh`, the last good snapshot is used and the source is marked
*stale*; the run only stops if a source has no usable data at all.

## 6. Tests and checks

```bash
pytest                   # everything: 186 tests (unit, API, browser)
pytest -m "not ui"       # without the browser tests
ruff check .             # lint
ruff format --check .    # formatting
```

| Suite | What it covers |
|---|---|
| `tests/unit` | HR cleaning rules, indicator parsing and curation, the metric SQL on hand-made tables, Wilson intervals and verdicts, time alignment (no future information), association statistics, schemas, ingest statuses, config |
| `tests/api` | every endpoint through FastAPI's TestClient on data built by the real offline pipeline; error codes 400 / 404 / 503 |
| `tests/ui` | Playwright against the real server: views, filters, empty and error states, API outage, keyboard navigation, chart table twins, findings |

## 7. Outputs and the dashboard

**Generated evidence (committed):** `data/curated/` (all layers, `quality_report.json`, `run_summary.json`,
`_build.json` lineage) and dashboard screenshots in [`docs/screenshots/`](docs/screenshots/).

**Dashboard views** and how they map to the brief:

| Brief | Dashboard | What it shows |
|---|---|---|
| Explore | **Explore › Objective detail** | one objective for a country, years, workforce segment (combinable) and data treatment: verdict, year table, quarterly trend, exit reasons, segment stability, "what would settle this" |
| Understand | **Explore › Market signals** | all three verdicts next to an official signal, each at its own frequency |
| Challenge | **Explore › Relationships** | the 12 formal within-country tests with n, bootstrap interval, Holm p; pooled and time-adjusted views as descriptive context; caveats |
| Trust | **Evidence** | sources, freshness, licence and attribution; reconciliation 2,407 rows → 2,400 employees; quality flags with their decision; sensitivity; coverage; methodology |
| (decision view) | **Overview** | the three objectives, one trend, market context, key findings |

**Key findings (company, hires 2021–2025):**

1. **Senior-hire retention is not met:** 78.2% (208/266, 95% CI 72.9–82.7%) against ≥ 90%, and not met in
   every hire year 2021–2024. It holds in all 6 segments and if Managers counted as senior (81.3%).
2. **New-hire retention is inconclusive:** 87.5% (1,579/1,804, CI 85.9–89.0%) against ≥ 86%. It is *met* for
   Permanent (88.0%) and Manager (91.1%) hires; 148 of 225 early leavers left voluntarily.
3. **Regretted turnover is met but rising:** 5.11% in 2025 (82 exits / 1,603 average headcount) against ≤ 7.5%,
   up from 3.30% in 2024; 2025 country values RO 6.7%, IE 6.3%, BG 6.1% are inconclusive.
4. **Non-finding:** none of the 12 formal within-country tests shows a clear association after Holm
   correction. Example: turnover vs inflation has raw p = 0.03 but Holm p = 0.12. Unemployment trends
   strongly with time (ρ −0.71), so time is a plausible confounder (D-79).
5. **Data health does not drive the answers:** 12 unverified 90-day exits are quarantined and 10 records
   excluded; counting them, or counting unknown "regretted" values as regretted, changes no verdict.

Associations are descriptive, never causal (D-63).

---

## 8. Known limitations and next steps

- **Population:** the HR file appears to contain only employees hired since 2020 (D-23). Headcounts in early
  2021 are small, so early trailing-12-month turnover is high (a ramp-up effect, not a verdict).
- **Assumptions:** `Sr Mgmt` = Senior Leader (D-13); senior = Senior Leader (D-14, now a setting, D-94);
  exits exactly 90 days after hire with a blank type are unverified and quarantined (D-10, D-57).
- **Publication lags** are conservative fixed approximations (monthly +2, quarterly +3, annual +7 months)
  measured from source availability, not exact historical release dates; today's APIs return **revised**
  values, not historical vintages (D-29, D-58).
- **Statistics:** small country-period samples (7–29 hires per country-quarter); rows are not independent, so
  bootstrap intervals are exploratory (D-56); each row counts once regardless of size (D-80).
- **Sources:** Eurostat `prc_hicp_manr` is discontinued (successor `prc_hicp_minr`, D-25); Irish GDP is
  distorted by multinational accounting, so Ireland is left out of the GDP test and this is reported (D-59).
- **Next steps:** confirm the assumptions with HR; exit reasons (interviews, surveys) to explain *why* hires
  leave; a longer history per country; a model that controls for time; data vintages; CI; the production
  deployment in `docs/architecture.md`.

---

## 9. Documentation map

| Document | Content |
|---|---|
| [`docs/brief/`](docs/brief/) | the original assessment brief (open the HTML file in a browser) |
| [`docs/decision_log.md`](docs/decision_log.md) | every decision with options, choice, reason, evidence; implementation log per step |
| [`docs/requirements_refinement.md`](docs/requirements_refinement.md) | questions, assumptions, metric definitions, acceptance criteria, rejected scope |
| [`docs/source_register.md`](docs/source_register.md) | providers, datasets, licences, units, cadence, lags, mappings, limitations |
| [`docs/methodology.md`](docs/methodology.md) | metrics, time alignment, association method, wording rules |
| [`docs/architecture.md`](docs/architecture.md) | production architecture view |
| [`AI_USAGE.md`](AI_USAGE.md) | how AI tools were directed and verified |
| [`presentation/`](presentation/) | the 16-slide deck for the 15-minute presentation: `deck.pdf` and `deck.pptx` (same slides; the PowerPoint file also has speaker notes with decision numbers and file paths) |

**Effort:** about 30 hours over 4 days.

*Asteria Consumer Products, its employees and targets are fictional; the workforce data is synthetic.*
