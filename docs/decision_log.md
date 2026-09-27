# Decision Log

Every decision taken during the assessment, recorded as it happened.
Each entry lists the options the AI agent (Claude Code, model Opus 5.5) proposed, what I chose, and why.

This log is the source for:
- `docs/requirements_refinement.md` (assumptions, metric definitions, rejected scope)
- `AI_USAGE.md` (what the agent did, what I decided, suggestions I rejected or changed)
- the final presentation (problem refinement and tradeoffs)

**Legend**
- ⭐ = option the agent recommended
- ✅ = my choice
- ✏️ = I wrote my own answer instead of picking an option (agent suggestion changed or rejected)

---

## Summary

| ID | Round | Topic | Decision | Agent's recommendation followed? |
|---|---|---|---|---|
| D-00 | 0 | Way of working | Decision-driven: every part is an MCQ that I decide | ✏️ My own process change |
| D-01 | 1 | Emphasis track | Software emphasis | ❌ Changed (agent recommended Data) |
| D-02 | 1 | Data processing | pandas | ✅ Yes |
| D-03 | 1 | SQL engine | DuckDB | ✅ Yes |
| D-04 | 1 | Dashboard technology | Basic HTML (HTML + plain JS + Chart.js) | ✏️ Changed (agent recommended Streamlit) |
| D-05 | 1b | Dashboard data feed | Small Python API (FastAPI) | ❌ Changed (agent recommended static JSON) |
| D-06 | 2 | Evidence before decisions | Show real data rows before each data decision | ✏️ My own process change |
| D-07 | 2 | Duplicate rows | Keep latest by `record_updated_at` | ✅ Yes |
| D-08 | 2 | Country codes | EL→GR, ROM→RO, blank→`Unknown` | ✅ Yes |
| D-09 | 2 | Invalid dates | Exclude from metrics, list in report | ✅ Yes |
| D-10 | 2 | 90-day exits with blank type | Quarantine + sensitivity analysis | ✏️ Materially changed |
| D-11 | 3 | ACP002047 (13th blank-type exit) | Real exit, type `Unknown` | ✅ Yes |
| D-12 | 3 | Blank `regretted_exit` | Preserve `UNKNOWN`, count only TRUE, worst-case sensitivity | ✏️ Materially changed |
| D-13 | 3 | `Sr Mgmt` label | Map to `Senior Leader` | ✅ Yes |
| D-14 | 3 | Senior hire definition | `Senior Leader` only | ✅ Yes |
| D-15 | 0b | Decision log | Record every decision/discussion in this file | ✏️ My own process change |
| D-16 | 4a | Retention window | Calendar months (hire + 6 / + 12 months) | ✅ Yes |
| D-17 | 4a | Which exits count as "not retained" | Any valid termination on/before observation date; type doesn't matter | ✏️ Extended into a full rule set |
| D-18 | 4a | Immature hires | Exclude until window complete | ✅ Yes |
| D-19 | 4a | Cohort grain | Hire quarter | ✅ Yes |
| D-20 | 4b | Turnover denominator | Average of 13 month-end headcounts | ✅ Yes |
| D-21 | 4b | TTM reporting frequency | Every month-end (2021-01 → 2025-12) | ✅ Yes |
| D-22 | 4b | Quarantined records in headcount | Exclude entirely; add back in sensitivity run | ✅ Yes |
| D-23 | 4b | No hires before 2020 | Report from 2021-01; document as limitation | ✅ Yes |
| D-24 | 5 | Labour supply indicator | Eurostat `une_rt_m` (monthly unemployment) | ✅ Yes |
| D-25 | 5 | Cost-of-living indicator | Eurostat `prc_hicp_manr` (discontinued) + document successor `prc_hicp_minr` | ✅ Yes |
| D-26 | 5 | Labour demand indicator | Eurostat `jvs_q_nace2` job vacancy rate (`JVR`) | ✅ Yes |
| D-27 | 5 | Second provider / economic cycle | World Bank `NY.GDP.MKTP.KD.ZG` + Ireland caveat | ✅ Yes |
| D-28 | 6 | Time anchor for the join | As known on the first day of the hire quarter | ✅ Yes |
| D-29 | 6 | Publication lag rule | Fixed per frequency: monthly +2m, quarterly +3m, annual +7m | ✅ Yes |
| D-30 | 6 | Monthly → quarterly cohort | Latest single available month | ✅ Yes |
| D-31 | 6 | Annual GDP → quarterly cohort | As-of carry-forward with original period, frequency and age columns | ✅ Yes |
| D-32 | 7a | Association method | Spearman: pooled + within-country | ✅ Yes |
| D-33 | 7a | Uncertainty | Wilson CI on rates + bootstrap CI on correlations | ✅ Yes |
| D-34 | 7a | Multiple comparisons | Holm correction | ✅ Yes |
| D-35 | 7a | Which objectives are tested | NEW_HIRE_6M primary + SENIOR_HIRE_12M and REGRETTED_TURNOVER_12M as secondary sensitivity analyses | ✏️ My own option 4 |
| D-36 | 7b | Senior secondary analysis grain | Both: quarter shown (to illustrate noise), year tested | ❌ Changed (agent recommended year only) |
| D-37 | 7b | TTM overlap in the test | Non-overlapping year-end (December) points only | ✅ Yes |
| D-38 | 7b | Turnover as-of anchor | Start of the 12-month window | ✅ Yes |
| D-39 | 7b | Holm family | One family per objective | ✅ Yes |
| D-40 | 8a | Code/repo layout | Brief's suggested shape, tweaked for our decisions; `src/` organised by layer (Spring-style) | ✏️ My own answer |
| D-41 | 8a | Data layer storage | Raw as-is + Parquet (canonical, analytical), queried by DuckDB | ✅ Yes |
| D-42 | 8a | Dependency management | `pyproject.toml` + venv + pip | ✅ Yes |
| D-43 | 8a | One-command run | CLI: `retention run` / `retention serve` | ✅ Yes |
| D-44 | 8b | API shape | Resource-style REST endpoints | ✅ Yes |
| D-45 | 8b | UI tests | Playwright (Python) smoke tests | ✅ Yes |
| D-46 | 8b | Schema & quality enforcement | Pandera schemas | ✅ Yes |
| D-47 | 8b | External API resilience | requests + urllib3 Retry + timeouts; partial-failure handling | ✅ Yes |
| D-48 | 8c | Re-run behaviour | Raw kept per fetch date + "latest" pointer; curated layers fully rebuilt each run | ✅ Yes |
| D-49 | 8c | Logging & observability | Python `logging` + `run_summary.json` per run | ✅ Yes |
| D-50 | 8c | Code quality tools | ruff + type hints | ✅ Yes |
| D-51 | 8c | Continuous integration | No CI for now; maybe later | ✏️ Deferred (agent recommended GitHub Actions) |
| D-52 | 9 | Implementation pace | One step at a time + recap linking code to decisions after every step | ✏️ Extended |
| D-53 | 9 | Git commits | Agent never commits; it warns and provides a commit message, I commit | ✏️ My own answer |
| D-54 | 10 | Formal vs descriptive view | Within-country = formal test; pooled = descriptive context only (refines D-32) | ✏️ My critical review |
| D-55 | 10 | Holm families | 4 tests per objective (4 indicators × within-country) (**supersedes D-39**) | ✏️ My critical review |
| D-56 | 10 | Bootstrap caveats | Bootstrap CIs are exploratory; dependence not fully solved (refines D-33) | ✏️ My critical review |
| D-57 | 10 | 90-day exits wording | Flag renamed `UNVERIFIED_EXIT`; never called fake/placeholder (refines D-10) | ✏️ My critical review |
| D-58 | 10 | Lag wording | "Conservative fixed-lag approximations", not exact release dates (refines D-29) | ✏️ My critical review |
| D-59 | 10 | GDP explained + Ireland explicit | GDP defined; IE data kept, GDP-test exclusion reported (refines D-27) | ✏️ My critical review |
| D-60 | 10 | CI | ~~Small GitHub Actions workflow~~ (**reversed by D-64**) | ✏️ My critical review |
| D-61 | 10 | Pandera vs business rules | Pandera = structure only; business rules in Python (refines D-46) | ✏️ My critical review |
| D-62 | 10 | Source status + run lineage | Status record per source; run_id + raw snapshot refs (refines D-47, D-48) | ✏️ My critical review |
| D-63 | 10 | Statistical language | Associative wording only; banned phrases listed | ✏️ My critical review |
| D-64 | 10b | CI reversed | No GitHub Actions; local tests run manually; CI may be added later (**reverses D-60, restores D-51**) | ✏️ My own answer |
| D-65 | 11 | HR starter files location | Move `assessment_files/` into `data/raw/hr/`; verify checksums vs manifest | ❌ Changed (agent recommended copy, keep original) |
| D-66 | 11 | Replay data in git | Commit one real refresh of raw snapshots | ✅ Yes |
| D-67 | 11 | 90-day flag name | `UNVERIFIED_EXIT` (confirms D-57) | ✅ Yes |
| D-68 | 11 | Source status in offline mode | New 4th status `replayed` | ✅ Yes |
| D-69 | 11 | HR snapshot folder name | Pack as-of date: `data/raw/hr/2025-12-31/` | ✅ Yes |
| D-70 | 11 | Code style | Simple, explainable style everywhere: plain loops, one idea per line, commented steps | ✅ Yes |

---

## Round 0: How we work

### D-00: Decision-driven workflow
- **Context:** The agent analysed the brief and data, then produced a full execution plan with its own default choices (stack, cleaning rules, metric definitions).
- **What I said:** The plan is good, but I want every part presented as a multiple-choice question so I make the decision (data handling, stack, sources, structure, etc.).
- **Why:** I must be able to explain and defend every choice in the interview. I'm new to this stack, so I want to understand each tradeoff rather than accept defaults.
- **Effect:** The agent stops choosing defaults silently and asks before each part. Decisions are grouped into rounds of up to 4 questions.

---

## Round 1: Focus track and core stack

### D-01: Emphasis track
| Option | Notes |
|---|---|
| Data emphasis ⭐ | Graded more on pipeline quality; dashboard can stay simple |
| **Software emphasis** ✅ | Graded more on code structure, API handling, packaging, UI tests, accessible dashboard |

- **Rationale:** My choice. Both tracks still require the full vertical slice.
- **Consequence:** Must show clear adapters/boundaries, resilient API handling, tests across service and UI, and accessible empty/error states.

**What it means (plain language):**
Both tracks build the same thing: research → ingest → clean → analyse → dashboard. The track only decides where reviewers look **deeper**:
- *Data emphasis:* is the data pipeline dependable (re-runs, schemas, lineage, quality gates)?
- *Software emphasis:* is the product **well-built and usable**? That means clear code boundaries ("adapters": one module per external source, so swapping a source doesn't break the rest), configuration outside the code, handling of API failures, packaging, tests on both the backend and the UI, and an accessible dashboard with proper empty/error messages.

**Why chosen:** My choice, based on where I want to show depth.

**Not chosen and why:** Data emphasis was recommended by the agent as the lighter path for a simple dashboard. I preferred to be evaluated on software structure and usability.

**Effect on later decisions:** This is why D-05 chose a real API service (FastAPI) instead of a static file. It gives a service boundary that can be tested.

### D-02: Data processing library
| Option | Notes |
|---|---|
| **pandas** ⭐ ✅ | Most popular, most examples, fast enough for ~2,400 rows |
| Polars | Faster, newer, fewer beginner examples |
| PySpark (local) | Matches Databricks story but heavy (Java on Windows), overkill |

- **Rationale:** Easiest to learn and explain; data size is small.

### D-03: How to demonstrate SQL
| Option | Notes |
|---|---|
| **DuckDB** ⭐ ✅ | pip install only, SQL directly on CSV/Parquet, returns pandas tables |
| SQLite | Built-in, but weak date functions |
| No separate SQL | Simplest, weak on "demonstrate SQL" requirement |

- **Rationale:** Metric logic lives in readable `.sql` files. No server needed.

**What it means (plain language):**
DuckDB is a small database engine that runs **inside Python**, with no server to install or start. It can run SQL directly on files: `SELECT * FROM 'data/curated/employees.parquet'`. Results come back as pandas tables, so Python and SQL work together.

**Why chosen:**
- The brief explicitly asks to "demonstrate SQL concepts". With DuckDB, the retention metrics are written as real SQL (`GROUP BY`, `CASE WHEN`, window functions, date arithmetic), not hidden inside Python.
- SQL is easy for a reviewer to read and audit: "which rows are in the denominator?" is visible in one query.
- It has good date functions (e.g. add 6 months to a date), which our retention windows need.
- Its SQL is close to Databricks SQL, which helps the production-architecture story.

**Not chosen and why:** SQLite (built-in, but weak date handling makes "hire + 6 calendar months" awkward). No SQL at all (fails the brief's SQL expectation).

### D-04: Dashboard technology
| Option | Notes |
|---|---|
| Streamlit ⭐ | Pure Python; risk: brief says "Power BI or HTML" |
| Static HTML report (Plotly) | Strict HTML, weak multi-filter support |
| Power BI Desktop | Allowed, harder to version-control/test |
| **✏️ My answer: "Can we try basic HTML?"** ✅ | |

- **Discussion:** I rejected the first set of options and asked for basic HTML. The agent explained the approach (pipeline → data → `index.html` + `app.js`) and the tradeoff (requires writing plain JavaScript, ~250 lines). Follow-up question:

| Option (follow-up) | Notes |
|---|---|
| **HTML + plain JS + Chart.js** ⭐ ✅ | Dropdown filters re-draw charts live |
| Python-generated HTML (Plotly) | Almost no JS, but limited to one filter at a time |
| HTML + plain JS, no chart library | Zero dependencies, no real line/scatter charts |

- **Rationale:** Most literal match to the brief ("Power BI or HTML"), clear separation between data and UI, easy to make accessible.
- **AI_USAGE note:** Agent's original recommendation (Streamlit) was **rejected**.

**What it means (plain language):**
- **HTML** = the page structure (dropdowns, headings, chart areas).
- **Plain JavaScript** = the code in the browser that reacts when a filter changes: it asks for new data and redraws the charts. "Plain" means no framework like React, just standard browser code.
- **Chart.js** = a free, widely used library loaded with one `<script>` line that draws line, bar and scatter charts from arrays of numbers.

**Why chosen:**
- The brief says the experience layer should be "Power BI Desktop, or HTML". A hand-built HTML page is the most literal and safest match.
- UI and data stay separate, which fits Software emphasis.
- Accessibility is easier to control: real `<label>` + `<select>` elements, keyboard navigation, text alternatives for charts.
- Several filters work together (country + time + objective + segment), which the brief requires. The Plotly-only option could only handle one filter at a time.

**Not chosen and why:** Streamlit (Python-only and easiest, but not literally "HTML" and gives less control over accessibility). Plotly-generated HTML (weak multi-filter support). No chart library (no proper trend or scatter charts). Power BI (hard to version-control and test).

**Tradeoff accepted:** I must learn and explain ~250 lines of basic JavaScript.

### D-05: How the dashboard gets its data
| Option | Notes |
|---|---|
| Static JSON file ⭐ | Pipeline exports `data.json`, served by `python -m http.server` |
| **Small Python API (FastAPI)** ✅ | Endpoints like `/api/retention?country=GR`; real service boundary |

- **Rationale:** Fits Software emphasis: a service boundary that can be covered by API tests. FastAPI can also serve the HTML page, so one command starts everything.
- **Consequence:** More code to explain; need API tests and error handling.

**What it means (plain language):**
FastAPI is a Python library for building a small web **API**: a set of URLs that return data instead of pages. The browser page (D-04) asks e.g. `GET /api/retention?objective=NEW_HIRE_6M&country=GR`, and the API reads the curated data and returns JSON (numbers the JavaScript can chart).
```
Browser (index.html + app.js)  ──HTTP request──►  FastAPI (Python)  ──reads──►  curated data (DuckDB/Parquet)
                               ◄──JSON response──
```

**Why chosen:**
- **Software emphasis** (D-01): a real service boundary between backend and UI is something the brief grades ("clear adapters, domain boundaries", "automated tests across service and UI boundaries").
- **Testable:** we can write automated tests like "the endpoint returns 404 for an unknown country" or "empty filter returns an empty list, not an error".
- **Error handling is visible:** the API can return clear error messages, and the page shows friendly empty/error states (a Software-emphasis requirement).
- FastAPI **auto-generates documentation** at `/docs`, so reviewers can try the endpoints.
- FastAPI can also serve the HTML page, so **one command** starts the whole dashboard.

**Not chosen and why:** Static JSON file (simpler, no server code, but no service boundary or API tests, so weaker for Software emphasis). It was the agent's recommendation. I chose the API for stronger engineering evidence.

---

## Round 2: Data quality handling (part 1)

### D-06: See evidence before deciding
- **Context:** The agent asked data-handling MCQs based on counts only.
- **What I said:** Before each data decision, show me the actual rows or examples so I can decide.
- **Effect:** The agent printed the real problem rows for each issue before asking.
- **Discovery from this step:** Looking at the actual rows revealed that **12 of 13 exits with blank `termination_type` are exactly 90 days after hire**, a pattern the counts-only view had hidden (see D-10).

### Evidence shown (from `employee_lifecycle_events.csv`, 2,407 rows)

| Issue | Rows | Example |
|---|---|---|
| Exact duplicates | 7 pairs | `ACP000045 BG IC 2020-12-27 … HCM_B 2025-12-29` appears twice, identical |
| Country `EL` | 4 | `ACP000073 EL Senior Leader 2023-01-26` (EL = Greece's Eurostat code) |
| Country `ROM` | 4 | `ACP000405 ROM Senior Leader 2021-01-17` |
| Country blank | 9 | `ACP000864 (blank) Senior Leader 2020-02-03 → 2024-01-22 Voluntary true` |
| Missing hire date | 5 | `ACP000560 RO IC (blank) → 2024-04-27 Voluntary false` |
| Termination before hire | 5 | `ACP000206 GR hire 2023-10-04, term 2023-09-24` (gaps 10/16/22/28/34 days, not typos) |
| Exit with blank type | 13 | 12 exactly hire + 90 days, e.g. `ACP000089 GR 2021-10-07 → 2022-01-05` |
| Voluntary, regretted blank | 2 | `ACP000534 BG Manager 2024-09-04 → 2024-11-26 Voluntary (blank)` |

### D-07: Duplicate rows
| Option | Notes |
|---|---|
| **Keep latest by `record_updated_at`** ⭐ ✅ | Same result here; rule still works if future copies differ |
| Keep first copy, log the rest | Simplest; correct here |
| Drop all copies | Loses 7 real employees |

- **Rationale:** Production-ready rule; removed copies logged in the quality report.

### D-08: Non-standard country codes
| Option | Notes |
|---|---|
| **Map EL→GR, ROM→RO; blank→`Unknown`** ⭐ ✅ | Blanks count in company totals, not per-country views or external joins |
| Map EL/ROM; exclude blanks everywhere | Loses 9 people incl. 4 real leavers |
| Exclude all 17 rows | Strictest, drops fixable data |

- **Rationale:** EL is the official EU code for Greece; ROM is an old Romania code. Mapping via a table keeps it auditable.

**What it means (plain language):**
- The standard 2-letter country codes (ISO 3166) are GR, RO, PL, IT, IE, BG. But the **EU/Eurostat** uses `EL` for Greece (from "Ellada"), and `ROM` is an old 3-letter code for Romania. Same countries, different spelling.
- A **mapping table** is a small file listing `source code → canonical code` (e.g. `EL → GR`). The pipeline applies it and counts how many rows each rule changed. Anyone can open the file and see exactly what was changed.
- **Canonical** = the one agreed standard version used everywhere after cleaning.
- `Unknown` rows (blank country) are still real employees, so they count in **company-wide** numbers. They can't appear in per-country views or be joined to a country's external data.

**Why chosen:**
- EL and ROM are not guesses: both are known codes for those countries. Excluding them would throw away valid people.
- Keeping blanks as `Unknown` avoids undercounting the company (4 of the 9 are real leavers).
- Handy link to Round 5: Eurostat itself returns Greece as `EL`, so the same mapping table is needed to join external data. One table solves both problems.

**Not chosen and why:** Excluding blanks (undercounts company totals). Excluding all 17 rows (throws away fixable data).

### D-09: Invalid dates (missing hire date, termination before hire)
| Option | Notes |
|---|---|
| **Exclude from metrics, list in report** ⭐ ✅ | Flag `MISSING_HIRE_DATE` / `TERM_BEFORE_HIRE`; show in dashboard Trust view |
| Exclude, but keep active ones in headcount | More complete, more complex |
| Fail the pipeline | Too strict; would never pass |

- **Rationale:** Cannot place these people in a cohort or measure tenure. Gaps are not consistent with simple typos, so no repair.

**What it means (plain language):**
- Each bad row gets a **quality flag** (a reason code such as `MISSING_HIRE_DATE` or `TERM_BEFORE_HIRE`). The row is kept in the data, but the metric calculations skip flagged rows.
- The **quality report** lists every excluded row with its reason, and the dashboard's "Trust" view shows the counts. Nothing disappears silently.

**Why chosen:**
- Every retention metric needs the hire date: to assign the hire quarter (cohort), to compute "hire + 6 months", and to know if someone was employed on a date. Without it, the row can't be placed.
- Termination before hire is impossible. We could "fix" it by swapping the dates, but the gaps (10, 16, 22, 28, 34 days) don't look like typing mistakes, so any fix would be a guess.
- Excluding 10 rows out of ~2,400 has a tiny effect, and it's fully reported.

**Not chosen and why:** Keeping active rows in headcount (more complete but more complex, for ≤ 5 people). Failing the whole pipeline (the data would never pass, and one bad row shouldn't block all reporting).

### D-10: 13 exits with blank `termination_type` (12 exactly 90 days after hire) ✏️
> 🔁 **Refined by D-57:** the flag is renamed `UNVERIFIED_EXIT`; the decision itself (quarantine + sensitivity) is unchanged.
| Option | Notes |
|---|---|
| Suspect: exclude from main metric + sensitivity ⭐ | Agent framed them as likely placeholders |
| Count as real exits, type `Unknown` | Face value |
| Treat employee as still active | Assume date is placeholder |
| **✏️ My own answer** ✅ | See below |

**My decision (verbatim intent):**
- Do not delete or automatically mark these exits as invalid.
- A 90-day exit could be a legitimate probation-period exit, so the 90-day pattern alone **does not prove** the dates are placeholders.
- Classify the 12 records as `SUSPECT_PLACEHOLDER_EXIT` (unverified exit) and keep them in the raw data.
- Exclude them from the **primary** retention/turnover metrics, because their exit status cannot be confidently established from the available fields.
- Run a **sensitivity analysis** treating them as genuine exits and show how the metrics change.
- Review the 13th record separately (it does not follow the 90-day pattern), and don't auto-classify it as a placeholder (see D-11).
- Document this as a data-quality limitation, **not** a claim that the dates are fake.

**Reason:** The dataset does not provide enough evidence to distinguish a legitimate 90-day probation exit from a system-generated placeholder. Quarantining preserves the uncertainty while preventing potentially invalid records from silently changing the primary KPI. The sensitivity analysis shows the business impact if they are genuine exits.

- **AI_USAGE note:** Agent's suggestion was **materially changed**. The agent had described the pattern as "statistically impossible" and leaned toward treating them as placeholders. I corrected the framing: the pattern is suspicious, not proof.

**What the key terms mean (plain language):**
- **Placeholder date:** a default value a system fills in automatically when the real value is missing, e.g. "end of probation = hire + 90 days". It looks like real data but isn't.
- **Probation period:** a trial period at the start of a job (often ~3 months), during which either side can end the contract easily. That makes a real 90-day exit plausible.
- **Quarantine:** the records are kept and marked, but not used in the main number until verified. It's like putting them aside rather than throwing them away.
- **Primary metric:** the main number shown to leaders, calculated only from records we trust.
- **Sensitivity analysis:** recalculating the metric under the other assumption ("what if these 12 exits are real?") to show how much the answer depends on that uncertain data. If the two results are close, the uncertainty doesn't matter much. If they're far apart, leaders should know.

**Why this matters for the metric:** a 90-day exit counts as a **failure** in NEW_HIRE_6M. If these 12 exits are fake, counting them would make new-hire retention look worse than it really is. If they're real, ignoring them would make it look better. We can't know which, so we report the trusted number and show the range.

---

## Round 3: Data quality handling (part 2) and senior definition

### Evidence shown
- **ACP002047:** `IE IC hire 2022-01-08 → term 2024-08-08 (~2.6 years), type (blank), regretted false`. Normal tenure, not the 90-day pattern.
- **Regretted vs termination type across all exits:**

| termination_type | regretted | count |
|---|---|---|
| Voluntary | true | 241 |
| Voluntary | false | 249 |
| Voluntary | (blank) | 2 |
| Involuntary | false | 153 |
| End of Contract | false | 122 |
| (blank) | (blank) | 12 |
| (blank) | false | 1 |

→ "Regretted" is only ever TRUE for voluntary exits, roughly 50/50.
- **Career levels:** Individual Contributor 1221, Manager 803, Senior Leader 373, **Sr Mgmt 10**. The 10 `Sr Mgmt` rows are spread across the same countries and units as Senior Leader.

### D-11: ACP002047 (blank type, plausible exit)
| Option | Notes |
|---|---|
| **Real exit, type `Unknown`** ⭐ ✅ | Warning flag `MISSING_TERMINATION_TYPE`, not quarantine; regretted=false kept |
| Quarantine with the other 12 | Consistent, but loses a legitimate-looking record |
| Real exit, regretted = unknown | Don't trust the `false` |

- **Rationale:** The date is plausible and regretted was filled in, so there is evidence of a real exit.

### D-12: Blank `regretted_exit` on 2 voluntary exits ✏️
| Option | Notes |
|---|---|
| Unknown → show low/high range ⭐ | Primary counts as not regretted |
| Assume not regretted | Single number |
| Assume regretted | Worst case |
| **✏️ My own answer** ✅ | See below |

**My decision:**
- Treat blank `regretted_exit` as `UNKNOWN`, not TRUE or FALSE. Preserve `UNKNOWN` in the canonical data.
- Primary regretted-turnover metric: numerator counts **only confirmed `regretted_exit = TRUE`**.
- Report the number of `UNKNOWN` voluntary exits separately.
- Sensitivity calculation: treat all `UNKNOWN` as regretted to show the maximum impact.
- **Do not impute** missing values.
- Document that the source data does not provide enough evidence to determine whether those exits were regretted.

- **AI_USAGE note:** Agent's recommendation **changed**. The agent's option implied converting unknown to "not regretted" in the primary number. I required preserving `UNKNOWN` as a distinct value in the canonical layer.

**What the key terms mean (plain language):**
- **Regretted exit:** someone who left voluntarily whom the company **wanted to keep** (e.g. a high performer). The REGRETTED_TURNOVER_12M objective counts only these.
- **Impute:** filling in a missing value with a guess (e.g. "probably false"). I decided **not** to do this.
- **Canonical data:** the cleaned, standard version of the data that all metrics read from. Keeping `UNKNOWN` there means every later step sees that the value is missing. It isn't hidden as a fake `FALSE`.
- **Numerator:** the top part of the fraction (regretted exits) in *regretted exits ÷ average headcount*.

**Why this rule:**
- A blank is **not** the same as "no". Converting it to `FALSE` would be a silent guess that makes the metric look better.
- The evidence (Round 3 table) shows voluntary exits are about 50% regretted, so a blank could honestly be either.
- Counting only confirmed `TRUE` gives a number we can fully defend. The separate `UNKNOWN` count plus the worst-case sensitivity shows leaders how much it could change: here at most 2 exits, so the impact is small but visible.
- This is consistent with D-10: uncertain data is kept, labelled and measured, never guessed.

### D-13: `Sr Mgmt` label
| Option | Notes |
|---|---|
| **Map `Sr Mgmt` → `Senior Leader`** ⭐ ✅ | Label variant via mapping table; log count; add to clarification questions |
| Keep as separate level | Tiny 10-person segment |
| Exclude the 10 rows | Shrinks an already small cohort |

- **Rationale:** Same pattern as EL→GR: a naming variant, handled by an auditable mapping.

**Why chosen (more detail):**
- The 10 `Sr Mgmt` rows look like normal senior employees: same countries, units and job families as `Senior Leader`. Nothing suggests a separate level.
- If left separate, these 10 people would fall out of the "senior hire" metric (D-14), shrinking an already small cohort.
- It's an **assumption**, so it's written down, the count is logged, and it goes into the clarification questions for the business to confirm.

### D-14: Which levels count as "senior hires" (SENIOR_HIRE_12M)
| Option | Notes |
|---|---|
| **`Senior Leader` only** ⭐ ✅ | Literal match; ~380 people over 5 years, so show sample size and uncertainty |
| Senior Leader + Manager | Bigger cohort, harder to defend |
| Senior Leader primary, +Manager as sensitivity | Most thorough, more work |

- **Rationale:** Matches the business label literally. The small sample must be shown in the dashboard.

**What it means (plain language):**
The objective says "Senior hires" but doesn't say which levels count. This decision defines it: only people whose career level is `Senior Leader` (including the 10 mapped from `Sr Mgmt`, D-13) are in this cohort. Managers are not.

**Why chosen:**
- "Senior" most naturally means the top level. Calling a Manager "senior" would be a stretch that's hard to defend.
- Including Managers would triple the cohort and make the numbers more stable, but then the metric wouldn't measure what the business asked for.

**Consequence: small samples.** ~380 senior hires over 5 years, about 3–4 per country per quarter. At that size one person leaving changes the rate by 25–30 points. So the dashboard must show **n** (number of people) and **uncertainty** (a confidence range) next to every senior value, and warn when n is small.

**Not chosen and why:** Senior + Manager (bigger but off-definition). Senior primary with Manager as sensitivity (more thorough, but extra work for a definition question the business should answer, so it goes to the clarification questions instead).

---

### D-15: Record every decision (process)
- **Context:** After round 3, I pointed the agent to section 06 of the brief ("Agentic work": show your operating loop, which decisions remained yours, suggestions rejected or changed, how outputs were verified).
- **What I said:** Record each decision and discussion in an .md file with the available choices, what I chose, and any custom answers, to use in the presentation and `AI_USAGE.md`. Do it retroactively for rounds 0–3 and for every part from now on.
- **Effect:** This file was created and is updated after every round.

---

## Round 4a: Hire-retention metric definitions (NEW_HIRE_6M, SENIOR_HIRE_12M)

The same rules apply to both objectives: 6 months for new hires, 12 months for senior hires.

### Evidence shown
(Illustrative clean with D-07…D-14 applied.)

**Example people:**
```
ACP000126 | IC | Fixed Term | hire 2021-07-10 | left 2021-09-26 (day 78)  Voluntary       → clearly NOT retained
ACP000015 | IC | Fixed Term | hire 2021-08-05 | left 2022-03-02 (day 209) Voluntary       → retained (left after 6m)
ACP000001 | IC | Permanent  | hire 2024-09-04 | still employed                            → retained
ACP000003 | IC | Permanent  | hire 2025-09-21 | still employed                            → window incomplete at 2025-12-31
ACP000053 | IC | Permanent  | hire 2025-08-04 | left 2025-12-28 (day 146) End of Contract → window incomplete, but already failed
```

**Boundary cases (24 exits fall between day 175 and 195):**
```
ACP002320 | hire 2021-10-27 | left 2022-04-28 = day 183 → calendar months: window ends 2022-04-27 → retained
ACP001818 | hire 2024-10-14 | left 2025-04-12 = day 180 → calendar months: window ends 2025-04-14 → NOT retained
```

**Exits within first 6 months (hires 2021-01 to 2025-06):** Voluntary 147, Involuntary 47, End of Contract 30.

**Observation window:** 1,966 valid hires since 2021. 1,804 have a complete 6-month window by 2025-12-31; 162 (hired after 2025-06-30) do not.

**Cohort size:** ~400 hires/year → ~100 per quarter → ~17 per country per quarter.

### D-16: How to measure the 6 / 12 month window
| Option | Notes |
|---|---|
| **Calendar months** ⭐ ✅ | Window ends same day-of-month 6/12 months later, e.g. 2021-10-27 → 2022-04-27 |
| Fixed 183 / 365 days | Same length for everyone, differs slightly from calendar months |
| Fixed 180 / 360 days | "30-day month" convention, ~3 days shorter |

- **Rationale:** Matches how the business reads "six months".
- **Definition:** observation date = hire_date + 6 calendar months (or + 12).

**What it means (plain language):**
"6 calendar months" means the same day number, 6 months later: hired 27 October → checked on 27 April. The alternative "183 days" counts days, which drifts by 1–3 days depending on which months are crossed (February is short).

**Why chosen:**
- It's how a manager or HR person would naturally read "six-month retention", so the number matches what leaders expect.
- The boundary matters: **24 exits** happen between day 175 and 195, so the choice changes real results (e.g. ACP001818 left on day 180 → NOT retained under calendar months, but borderline under "180 days").
- Easy to compute in SQL/pandas with "add 6 months" functions.

**Edge case to handle in code:** hires on the 29th–31st, e.g. 31 August + 6 months = 28 February (no 31 February). Standard date libraries move it to the last day of the month. This will be tested.

**Not chosen and why:** Fixed 183/365 days (same length for all, but doesn't match the business wording). 180/360 days (shorter than a real 6 months).

### D-17: Which exits count as "NOT retained" ✏️
| Option | Notes |
|---|---|
| All exits ⭐ | Any exit in window counts; breakdown by type in dashboard |
| Voluntary only | Measures only people choosing to leave |
| Exclude End of Contract only | Planned contract ends not counted as failures |
| **✏️ My own answer** ✅ | See below |

**My decision (full rule set):**
- Retention is defined purely by whether the employee remained employed through the observation date.
- Any **valid** termination **on or before** the observation date → **NOT RETAINED**.
- No valid termination by the observation date → **RETAINED**.
- Termination type does not change the outcome: Voluntary, Involuntary and End of Contract all count as exits.
- Immature hires (observation date not yet reached) → excluded from the primary denominator (see D-18).
- Suspicious/unverified exits already quarantined (D-10) → excluded from the primary metric, handled through sensitivity analysis.
- Dashboard breaks down non-retention by termination type so reviewers can distinguish voluntary, involuntary and end-of-contract exits.

- **AI_USAGE note:** Same direction as the agent's recommendation, but I made it precise: the boundary rule "on or before" the observation date, and explicit integration with the quarantine (D-10) and maturity (D-18) rules.

**What it means (plain language):**
The metric answers one simple question: **"Was this person still employed after their 6 (or 12) months?"** It doesn't matter *why* they left: resigned (Voluntary), let go (Involuntary), or contract ended (End of Contract). All three count as "not retained". The dashboard then shows the reasons split out, so leaders can see e.g. "most early exits are voluntary".

**Why chosen:**
- "Retention" literally means keeping people. Anyone who left was not retained.
- One clear definition avoids arguments about which exit types are "fair" to count.
- The type breakdown in the dashboard still gives the detail, so no information is lost.
- **"On or before"** removes ambiguity at the boundary: leaving on exactly the observation date counts as not retained.
- It explicitly ties together the rules already agreed (quarantine D-10, immature hires D-18), so there's no gap in the logic.

**Not chosen and why:** Voluntary only (hides involuntary and contract exits, which also cost the business). Excluding End of Contract (needs an extra rule about what happens to those people, and fixed-term hires would look artificially good).

### D-18: Hires whose window hasn't finished by 2025-12-31
| Option | Notes |
|---|---|
| **Exclude until window complete** ⭐ ✅ | Only hires ≤ 2025-06-30 (6m) / ≤ 2024-12-31 (12m) enter the metric |
| Include known leavers, exclude the rest | Uses more data but biases retention downward |
| Survival analysis (Kaplan-Meier) | Most rigorous, advanced to explain |

- **Rationale:** Unbiased and simple to explain. Recent hires are shown in the dashboard as a "not yet measurable" count.

**What it means (plain language):**
- A hire is **mature** once their observation date (hire + 6 months) has passed by the data's as-of date (2025-12-31). Only mature hires are in the metric.
- **Censoring** is the statistics term for "we stopped watching before we know the outcome". Someone hired in September 2025 might still leave before March 2026, and we can't know yet.

**Why chosen (the bias problem):**
Take the recent hires (after 2025-06-30). The ones who **already left** have a known outcome (failure). The ones still employed have an **unknown** outcome, since they could still leave. If we counted only the known leavers, recent cohorts would contain *only* failures, and retention would look falsely bad. Waiting until the window is complete treats everyone the same.

**Not chosen and why:** Include known leavers (biased downward, as explained above). Kaplan-Meier survival analysis (the statistically "correct" way to use partial data, but advanced to explain; could be mentioned as a next step).

### D-19: Cohort time grain
| Option | Notes |
|---|---|
| **Hire quarter** ⭐ ✅ | ~100/quarter company-wide, ~17 per country; aligns with quarterly external data |
| Hire year | Stable, but only 5 points per country |
| Hire month | ~6 per country per month; extremely noisy |

> Note: for SENIOR_HIRE_12M the formal test later uses hire **year** (see D-36), because senior quarterly cohorts are too small.

- **Rationale:** Balance between detail and stability.
- **Consequence:** Every point must show sample size (n) and uncertainty; small-n warnings in the dashboard.

**What it means (plain language):**
A **cohort** is a group of people who started in the same period. "Hire quarter" groups everyone hired in e.g. 2023-Q1 (Jan–Mar) together, and calculates their 6-month retention as one number. The **grain** is the level of detail of each row: here, one row = one country × one hire quarter.

**Why chosen:**
- **Detail vs noise tradeoff:** monthly cohorts are too small (~6 people per country, where one leaver swings the rate by ~17 points). Yearly cohorts are stable but give only 5 points per country, too few to see trends or compare with external data.
- Quarterly gives ~20 points per country, enough to see trends.
- **Matches external data:** the job vacancy rate is quarterly (D-26), and monthly indicators can be summarised per quarter. Aligned periods make the later join simpler.

**What "n and uncertainty" means:** each point shows how many people it's based on (n), and a **confidence interval**: a range saying "the true rate is probably between X% and Y%". Small n means a wide range, which tells the reader not to over-trust that point.

**Not chosen and why:** Hire year (too few points). Hire month (too noisy).

---

## Round 4b: Regretted turnover definition (REGRETTED_TURNOVER_12M, target ≤ 7.5%)

Formula: regretted exits in trailing 12 months ÷ average headcount (numerator rule already set in D-12: only confirmed `TRUE`).

### Evidence shown
(Illustrative clean with D-07…D-14 applied, quarantined records excluded.)

**Discovery: the workforce starts from zero in 2020.** Earliest hire is 2020-01-02; there is nobody hired before 2020.
```
Headcount at   2019-12-31:    0
               2020-12-31:  367
               2021-12-31:  705
               2022-12-31:  997
               2023-12-31: 1257
               2024-12-31: 1532
               2025-12-31: 1617
```
→ The file most likely contains only employees hired from 2020 onward (a truncated extract), not the full workforce.

**Denominator conventions compared (year-end snapshots):**
```
period end | regretted exits (12m) | unknown | (start+end)/2      | avg of 13 month-ends
2021-12-31 |  23                   |   0     | 4.3%  (HC ≈ 536)   | 4.4%  (HC ≈ 523)
2022-12-31 |  32                   |   1     | 3.8%  (HC ≈ 851)   | 3.8%  (HC ≈ 846)
2023-12-31 |  38                   |   0     | 3.4%  (HC ≈ 1127)  | 3.4%  (HC ≈ 1131)
2024-12-31 |  46                   |   1     | 3.3%  (HC ≈ 1394)  | 3.3%  (HC ≈ 1395)
2025-12-31 |  82                   |   0     | 5.2%  (HC ≈ 1574)  | 5.1%  (HC ≈ 1603)
```
→ Conventions differ by at most 0.1 pt. All years under the 7.5% target, but 2025 jumps (46 → 82 regretted exits). Preliminary figures; to be reproduced by the real pipeline.

### D-20: Average headcount convention
| Option | Notes |
|---|---|
| **Average of 13 month-end headcounts** ⭐ ✅ | Month-end before window + 12 month-ends in it; common HR standard |
| (Start + End) / 2 | Simplest; same result here within 0.1 pt |
| Daily average headcount | Most precise; negligible difference here |

- **Definition:** headcount at date D = employees with hire_date ≤ D and (no termination or termination_date > D).
- **Rationale:** Standard convention, robust to mid-year spikes.

**What it means (plain language):**
- **Turnover rate** = how many left ÷ how many people we had. But the workforce size changes during the year, so "how many we had" must be an **average**.
- **Denominator** = the bottom of the fraction (average headcount).
- **Average of 13 month-end headcounts:** count employees on the last day of each month. For the 12 months ending Dec 2024, that's 31 Dec 2023, 31 Jan 2024, …, 31 Dec 2024 (13 counts: the starting point + 12 month-ends). Then average them.
- **Headcount rule:** someone counts on date D if they were hired on or before D and hadn't left yet (no exit, or exit after D).

**Why chosen:**
- It's a **common HR reporting convention**, so leaders and HR analysts will recognise it.
- It follows the workforce through the year. Our headcount grows fast (367 → 1,617), so a simple start-and-end average could miss mid-year changes.
- The evidence showed all conventions give nearly the same result here (≤ 0.1 point difference), so this choice is about **correctness and explainability**, not about changing the answer.

**Not chosen and why:** (Start+End)/2 (simplest, but blind to mid-year changes). Daily average (most precise, but more computation for no visible gain).

### D-21: TTM reporting frequency
| Option | Notes |
|---|---|
| **Every month-end** ⭐ ✅ | 60 points, 2021-01 → 2025-12; shows when changes develop |
| Every quarter-end | 20 points, aligns with hire-quarter cohorts |
| Year-end only | 5 points, hides timing |

**What it means (plain language):**
**TTM = Trailing Twelve Months**, i.e. "the last 12 months ending on this date". At each month-end we calculate: regretted exits in the previous 12 months ÷ average headcount over those months. Then the window moves forward one month. The result is a **rolling** line with 60 points (Jan 2021 → Dec 2025).

**Why chosen:**
- It's the natural way to report a "trailing 12-month" KPI. Leaders see the latest value every month, not once a year.
- It shows **when** changes start. The evidence showed a big jump in 2025 (46 → 82 regretted exits). A monthly line shows which month the rise began; a year-end number only shows it happened.
- Each point already covers 12 months of data, so it isn't noisy even though it's reported monthly.

**Note:** consecutive points share 11 of 12 months of data, so they are **not independent**. This matters in the analysis round: we must not treat 60 monthly points as 60 separate observations when testing for relationships.

**Not chosen and why:** Quarter-end (fewer points, hides timing within quarters). Year-end only (5 points, hides timing).

### D-22: Quarantined 90-day records in the headcount
| Option | Notes |
|---|---|
| **Exclude entirely; include in sensitivity** ⭐ ✅ | Consistent with D-10; out of numerator and denominator in primary metric |
| Count employed from hire until suspect exit | Partly trusts the doubtful exit date |
| Count as still employed | Contradicts D-10 ("not proven fake") |

- **Rationale:** Consistency with the quarantine principle. Impact ≤ 12 people out of 1,000+.

**What it means (plain language):**
In the main turnover number, these 12 records are left out completely: not counted as leavers (numerator) and not counted as employees (denominator). In the sensitivity run they are added back as real employees who really left on those dates, and the result is compared.

**Why chosen:**
- **Consistency:** D-10 said "we can't trust these records' exit status". Half-using them (count the person, but stop counting on the doubtful exit date) would quietly rely on the very date we said we don't trust.
- Their `regretted_exit` is blank, so they could never add to the regretted numerator anyway. Only the denominator is affected, by at most 12 out of 1,000+ people, i.e. under ~1% effect.

**Not chosen and why:** Count them until the suspect exit (partly trusts the doubtful date). Count them as still employed (assumes the date is fake, which contradicts D-10's "not proven fake").

### D-23: No employees hired before 2020
| Option | Notes |
|---|---|
| **Report from 2021-01; document as limitation** ⭐ ✅ | Target period starts 2021; 2020 provides history only |
| Report from 2022-01 only | Skips ramp-up year, loses a target year |
| Flag 2021 values as low-confidence | Visual warning on 2021 points |

- **Rationale:** Matches the objective's effective period.
- **Consequence:** State that population = "employees hired since 2020"; early-period denominators are small; add to clarification questions.

**What it means (plain language):**
- The data has **no one hired before 2020**, so headcount starts at 0 and grows. A real company wouldn't have zero staff in 2019, so the file is probably an **extract** containing only people hired from 2020, not the full workforce.
- A **limitation** is a known weakness in the data or method that we state openly, so readers know how far to trust the results.
- **Ramp-up:** in 2021 the headcount is still small and growing fast, so each exit weighs more in the rate.

**Why chosen:**
- The objective's own effective period is **2021-01-01 → 2025-12-31**, so reporting from 2021 matches the business definition. The 2020 data is only needed as history for the first trailing-12-month windows.
- Skipping 2021 would drop a year the business explicitly asked for. Instead we're honest about its weakness.
- Asking the business ("is this the full workforce?") is the proper way to resolve it, so it's in the clarification questions.

**Why it matters for the interview:** "All employees" in the objective really means "all employees **hired since 2020**" in our data. Long-tenured staff (who usually leave less) are missing, so turnover may be **overstated** compared with the real company. Saying this shows critical reading of the data.

**Not chosen and why:** Start in 2022 (loses a target year). Flag 2021 as low-confidence (reasonable, but the limitation note already covers it; can be added later).

---

## Round 5: External sources

Brief minimum: ≥ 2 authoritative providers, ≥ 3 indicators, ≥ 2 lenses, ~3 years of history.

### How the evidence was produced
Instead of naming datasets from memory, the agent **called the live APIs** (Eurostat dissemination API, World Bank API v2) for our 6 countries from 2019 onward, on 2026-09-27, and reported coverage, latest values and last-update dates. Probe scripts were kept out of the repo (scratch only); the real ingestion code will be written in the implementation phase.

### Evidence shown
| # | Provider · dataset | Lens | Frequency | Coverage (6 countries) | Last updated |
|---|---|---|---|---|---|
| A | Eurostat `une_rt_m`, unemployment rate | Labour supply | Monthly | 2019-01 → 2026-07, complete | 2026-09-22 |
| B | Eurostat `prc_hicp_manr`, HICP inflation | Cost of living | Monthly | 2019-01 → 2025-12, complete; **discontinued** (label "(1997-2025)") | 2026-02-06 |
| B2 | Eurostat `prc_hicp_minr`, HICP ECOICOP v2 | Cost of living | Monthly | Successor; new schema (`coicop18` dimension); history depth unverified | 2026-09-17 |
| C | Eurostat `jvs_q_nace2`, job vacancy rate | Labour demand | Quarterly | 2019-Q1 → 2025-Q4, complete | 2026-03-20 |
| D | Eurostat `lc_lci_r2_q`, labour cost index | Wage pressure | Quarterly | 2019-Q1 → 2026-Q2; provisional (`p`) flags | 2026-09-16 |
| E | World Bank `NY.GDP.MKTP.KD.ZG`, GDP growth | Economic cycle | Annual | 2019 → 2025 | 2026-07-13 |
| F | World Bank `SL.UEM.TOTL.ZS`, unemployment (ILO modelled) | Labour supply | Annual | 2019 → 2025 | 2026-07-13 |
| G | World Bank `FP.CPI.TOTL.ZG`, CPI inflation | Cost of living | Annual | 2019 → 2025 | 2026-07-13 |

### Findings from the probe
1. **Agent's schema guess was wrong and caught by verification.** The first job-vacancy query used indicator code `JOBRATE` (the agent's guess) and returned **0 values** for all countries. Listing the dataset's real dimensions showed the valid codes are `JOBVAC, JOBOCC, JVR, JVRCH_Q`; with `JVR` all 6 countries return 28/28 quarters. → Direct example of the brief's warning "do not treat generated schemas as facts without checking".
2. **Source schema evolution.** `prc_hicp_manr` was frozen in Feb 2026 when Eurostat moved HICP to the ECOICOP v2 classification (`prc_hicp_minr`, dimension `coicop18` instead of `coicop`). The old dataset still fully covers our 2019–2025 window.
3. **Ireland GDP distortion.** World Bank IE GDP growth: 2023 = -2.5%, 2024 = 2.6%, 2025 = 12.3%; Eurostat IE quarterly 2026-Q1 = -13.4% y/y. Other countries sit between -2% and +5%. Irish GDP is known to be distorted by multinational accounting.

### D-24: Labour supply indicator
| Option | Notes |
|---|---|
| **Eurostat monthly (A)** ⭐ ✅ | Monthly, complete, freshest |
| World Bank annual (F) | Too coarse for quarterly cohorts |
| Both (A + F) | Cross-provider reconciliation, more work |

**What it means (plain language):**
The unemployment rate is the % of people who want a job and are looking for one but don't have one. We use Eurostat's **monthly** figure per country (seasonally adjusted, all ages, both sexes).

**Why this indicator (the retention logic):**
- **High unemployment** → jobs are hard to find → employees are less likely to quit → retention should be **higher**.
- **Low unemployment** → a "tight" labour market with many alternatives → employees find it easier to leave → retention should be **lower**.
- It is the most direct "can my employees easily get another job?" signal.

**Why this source/option:**
- **Monthly** data gives about 3 values per hire quarter, so it fits our quarterly cohorts (D-19). The World Bank version is annual only: 5 points per country, too coarse.
- **Complete coverage:** all 6 countries, 2019 → 2026-07, no gaps in our window.
- **Freshest:** updated 2026-09-22.
- **Seasonally adjusted** (`SA`): the regular yearly pattern (e.g. summer tourism jobs) is removed, so month-to-month changes reflect real movement, not the calendar.
- Eurostat uses the same method in every EU country, so the 6 countries are comparable.

**Not chosen and why:** World Bank unemployment (annual, and a "modelled" ILO estimate, so less direct). Using both would add a cross-check but more work, with no new lens.

### D-25: Cost-of-living indicator
| Option | Notes |
|---|---|
| **Eurostat old HICP (B) + document successor** ⭐ ✅ | Complete for 2019–2025; documented as schema-evolution case |
| Eurostat new HICP (B2) | Future-proof, unverified history, different schema |
| World Bank annual CPI (G) | Too coarse |
| Skip inflation | — |

**What it means (plain language):**
HICP = *Harmonised Index of Consumer Prices*, the EU's official inflation measure. We use the **annual rate of change** each month, e.g. "prices in Romania in 2025-12 were 8.6% higher than in 2024-12". Category `CP00` = all items (the overall basket, not just food or energy). "Harmonised" means every EU country calculates it the same way, so countries are comparable.

**Why this indicator (the retention logic):**
- **High inflation** → the salary buys less → employees feel pressure to look for a better-paying job → retention may **fall**.
- It represents the **cost-of-living** lens the brief lists as an example.
- It varies a lot between our countries (2025-12: Romania 8.6% vs Italy 1.2%), so there is real variation to compare.

**Why this source/option (the old dataset):**
- It covers our **entire window (2019-01 → 2025-12) with no gaps**, which is all we need because the workforce data ends 2025-12-31.
- The new dataset (`prc_hicp_minr`) has a different structure and we haven't verified how far back it goes. Switching would add risk for no benefit to this analysis.

**What "discontinued + document successor" means:**
In early 2026 Eurostat stopped updating `prc_hicp_manr` and moved inflation to a new product classification (ECOICOP version 2), in a new dataset with a renamed column (`coicop` → `coicop18`). We use the old one, but **write down** in the source register that it's frozen, what replaced it, and how we'd migrate. This is a real example of **schema evolution**, a topic the brief grades under Data/Software engineering: sources change over time, and the pipeline must be ready for it.

- **Consequence:** Source register must state the dataset is discontinued, name the successor, and describe the migration path (in production, the adapter would switch to `prc_hicp_minr` with a `coicop18` mapping).

**Not chosen and why:** New HICP (unverified history, schema change). World Bank CPI (annual only, too coarse). Skipping inflation would lose the cost-of-living lens.

### D-26: Labour demand indicator
| Option | Notes |
|---|---|
| **Job vacancy rate (C)** ⭐ ✅ | Quarterly, complete; most plausible retention-related signal |
| Labour cost index (D) | Wage pressure; provisional values |
| Both (C + D) | More multiple comparisons |
| Skip | — |

- **Filter used:** `nace_r2=B-S` (industry, construction and services), `sizeclas=TOTAL`, `indic_em=JVR`, `s_adj=NSA`.

**What it means (plain language):**
The job vacancy rate is the % of all jobs that are **open and being recruited for**. Formula: vacancies ÷ (occupied jobs + vacancies). E.g. Italy 2025-Q4 = 1.6% means about 1.6 of every 100 jobs were unfilled and advertised.

**Why this indicator (the retention logic):**
- **More open jobs** → more employers competing for workers → more chances for our employees to be recruited away → retention may **fall**.
- It measures the **labour demand** side (how much employers want workers). Unemployment measures the **supply** side (how many people are looking). Together they describe the job market from both ends.
- Of all candidates, this is the most direct link to "someone else wants to hire our people".

**Why this source/option:**
- **Quarterly**, which matches our hire-quarter cohorts (D-19) exactly, one value per cohort.
- **Complete:** all 6 countries, 2019-Q1 → 2025-Q4 (28/28 quarters).
- The labour cost index (wage growth) is also relevant, but some of its values are *provisional* (may be revised later). Adding both would mean more statistical tests, which raises the chance of a false "finding" by luck (the multiple comparisons problem).

**What the filters mean:**
- `nace_r2=B-S`: the whole business economy (industry, construction, services), excluding agriculture. This is the broadest sector group available, because our company spans Supply Chain, Sales, Finance and Digital.
- `sizeclas=TOTAL`: companies of all sizes.
- `indic_em=JVR`: the job vacancy **rate** (%), not the raw count of vacancies, so small and large countries are comparable.
- `s_adj=NSA`: *not* seasonally adjusted, because that's the version with complete coverage for our countries. To note in the source register: seasonal patterns remain in this series.

**Verification story:** the agent first guessed the code `JOBRATE`, which returned 0 values. Checking the real list of codes found `JVR`. See "Findings from the probe", item 1.

**Not chosen and why:** Labour cost index (provisional values, and adds another test). Both (more multiple comparisons). Skipping would lose the demand lens.

### D-27: Second provider / economic cycle
> 🔁 **Refined by D-59:** Ireland's GDP data is kept; only the GDP association test excludes IE, and that exclusion is reported with the results.
| Option | Notes |
|---|---|
| **World Bank GDP growth (E) + Ireland caveat** ⭐ ✅ | Adds cycle lens; satisfies 2-provider rule |
| World Bank unemployment (F) | Cross-check only, no new lens |
| World Bank CPI (G) | Cross-check only, no new lens |

- **Consequence:** Ireland is flagged; GDP-based analysis excludes IE (or shows it separately). Annual values must never be spread across months or quarters as if newly measured (brief's frequency-integrity rule).

**What it means (plain language):**
GDP (Gross Domestic Product) is the total value of everything a country produces in a year. **GDP growth** is the % change from the previous year, adjusted for inflation ("real" growth, the `KD` in the code means constant prices). E.g. Poland 2025 = 3.6% means the economy produced 3.6% more than in 2024.

**Why this indicator (the retention logic):**
- **Strong growth** → companies expand and hire → more outside opportunities → retention may **fall**.
- **Weak growth or recession** → hiring freezes, job security matters more → retention may **rise**.
- It adds the **economic cycle** lens (boom vs slowdown), a different angle from the three labour-market and price indicators.

**Why this source/option:**
- **Satisfies the "2 providers" rule.** Our other three indicators all come from Eurostat, so at least one must come from somewhere else.
- The World Bank is an authoritative, free, well-documented API with the same codes for every country.
- GDP adds a **new lens**. World Bank unemployment or CPI would only duplicate lenses we already have from Eurostat.
- It's **annual**, which lets us demonstrate the brief's **frequency integrity rule**: an annual value is one measurement per year and must **never** be presented as 4 quarterly or 12 monthly "new" values.

**What the "Ireland caveat" means:**
Ireland's GDP swings wildly (2023 = -2.5%, 2025 = +12.3%) because large multinational companies book profits and intellectual property there. This inflates GDP without reflecting the real local job market. If we compared Irish retention with Irish GDP, we could "find" a pattern that is really caused by multinational accounting. So Ireland is **flagged**, and GDP-based analysis either **excludes IE** or shows it separately with a warning.

**Not chosen and why:** World Bank unemployment or CPI would satisfy the provider rule but add no new lens. They would only cross-check Eurostat.

### Final indicator set
| Indicator | Provider | Lens | Frequency |
|---|---|---|---|
| Unemployment rate | Eurostat | Labour supply | Monthly |
| HICP inflation (annual rate of change) | Eurostat | Cost of living | Monthly |
| Job vacancy rate | Eurostat | Labour demand | Quarterly |
| GDP growth | World Bank | Economic cycle | Annual |

→ 2 providers, 4 indicators, 4 lenses, 3 different frequencies (this makes temporal alignment a real design problem, to be decided in a later round).

**Why this set works as a whole:**
| Lens | Question it answers for retention | Indicator |
|---|---|---|
| Labour supply | How many people are looking for work? (harder to leave if many compete for jobs) | Unemployment rate |
| Labour demand | How many employers are trying to hire? (easier to leave if many open jobs) | Job vacancy rate |
| Cost of living | Is pay losing value? (pressure to seek higher pay) | HICP inflation |
| Economic cycle | Is the economy booming or slowing? (overall hiring climate) | GDP growth |

**Important reminder for the analysis and presentation:** each "retention logic" above is a **hypothesis**, not a fact. Our workforce data is synthetic, and inspecting how it was generated shows retention there depends on hire year, country, business unit, level and contract type, **not** on these indicators. So any correlation we find must be presented as an association, never as a cause.

**Still to verify (source register):** licence/terms pages for Eurostat and the World Bank, and the publication lag of each indicator. These will be checked against the providers' own pages, not stated from memory.

---

## Round 6: Temporal alignment

The brief: *"Join workforce outcomes to external signals without future information."* Also: *"Do not present an annual observation as twelve newly measured monthly values. If you carry a value forward, preserve its original period, publication status, and age, and explain the rule."*

### Evidence shown
**Example cohort: Greece, hired 2023-Q1 (Jan–Mar 2023).** 6-month outcome known Jul–Sep 2023. Real values from the APIs (fetched 2026-09-27):
```
Unemployment % (monthly):  2022-10=11.8  2022-11=11.6  2022-12=12.1 | 2023-01=10.5  2023-02=11.1  2023-03=11.4 | 2023-04..09 ≈ 11.4→10.9
Inflation %    (monthly):  2022-10=9.5   2022-11=8.8   2022-12=7.6  | 2023-01=7.3   2023-02=6.5   2023-03=5.4  | 2023-06=2.8 ...
Job vacancy %  (quarterly): 2022-Q3=1.1  2022-Q4=0.9                 | 2023-Q1=1.5                               | 2023-Q2=1.6
GDP growth %   (annual):    2021=8.7     2022=5.5                    | 2023=2.1
                            ─────── known BEFORE hire ───────────────  ── during hire quarter ──────────────────  ── during 6m window ──
```

**Publication lag, measured from the API responses:**
| Indicator | Evidence | Observed lag |
|---|---|---|
| Unemployment (monthly) | On 2026-09-27 the latest value is 2026-07 for most countries | ~2 months after month end |
| HICP (monthly) | 2025-12 present in the 2026-02-06 update | ~1–1.5 months |
| Job vacancy (quarterly) | 2025-Q4 present in the 2026-03-20 update | ~3 months after quarter end |
| GDP (annual, World Bank) | 2025 present in the 2026-07-13 update | ~6.5 months after year end |

**The same cohort under three approaches:**
| | A: As known at quarter start (2023-01-01), with lags | B: Same period, ignoring lag | C: During 6-month window |
|---|---|---|---|
| Unemployment | 11.8 (2022-10) | 11.0 (avg Jan–Mar 2023) | ~11.4 |
| Inflation | 9.5 (2022-10) | 6.4 | ~4.9 |
| Job vacancy | 1.1 (2022-Q3) | 1.5 (2023-Q1) | ~1.6 |
| GDP growth | 8.7 (2021) | 2.1 (2023, published mid-2024) | 2.1 |
| Future information? | No | Yes | Yes (hindsight) |

→ The approaches give very different values (GDP 8.7 vs 2.1; inflation 9.5 vs 6.4), so this choice directly changes any relationship found.

**Side finding:** `jvs_q_nace2` is also labelled "(2001-2025)", like the discontinued HICP dataset, so it is likely frozen too (Eurostat classification change). It fully covers our window. To be recorded in the source register.

**Limitation (revisions/vintages):** the APIs return today's **revised** values, not the values actually published at the time (historical "vintages"). Even approach A approximates what was known back then.

### D-28: Time anchor for the join
| Option | Notes |
|---|---|
| **A: As known at start of hire quarter** ⭐ ✅ | Only values already published on the quarter's first day |
| A + C as sensitivity | Adds a labelled "hindsight" view |
| As known at each employee's hire date | Per-person join; more complex, barely different |
| B: Same period, ignore lag | Uses unpublished values |

**What it means (plain language):**
Each cohort gets a single **as-of date**: the first day of its hire quarter (e.g. 2023-01-01 for 2023-Q1). It only sees indicator values that had **already been published** by then. It's like asking "what did the job market look like, based on the information available when these people were hired?"

**Why chosen:**
- It follows the brief's "no future information" rule literally. There is no **data leakage** (accidentally using information from after the event).
- One as-of date per cohort is simple to explain, compute and test.
- Per-person dates would give almost the same result, since hires in one quarter are at most 3 months apart, for much more complexity.

**Tradeoff accepted:** conditions during the 6-month window (option C) may matter more for whether someone quits. But using them means hindsight, so they are left out of the primary analysis. This can be named as a next step.

**Not chosen and why:** B (breaks the no-future-information rule, e.g. uses 2023 GDP that wasn't published until mid-2024). A + C (richer, more work). Per-hire date (complex, little gain).

### D-29: Publication lag rule
> 🔁 **Refined by D-58:** wording. The lags are *conservative fixed-lag approximations based on observed source availability*, not exact historical release dates.
| Option | Notes |
|---|---|
| **Fixed lag per frequency from evidence** ⭐ ✅ | Monthly +2m, quarterly +3m, annual +7m |
| Fixed lag per indicator | Slightly more precise |
| No lag | Leaks future information |

**What it means (plain language):**
A value becomes "usable" a fixed time **after its period ends**:
- Monthly (unemployment, HICP): end of month + 2 months. E.g. October 2022 (ends 31 Oct) is usable from 31 Dec 2022.
- Quarterly (job vacancy): end of quarter + 3 months. E.g. 2022-Q3 (ends 30 Sep) is usable from 30 Dec 2022.
- Annual (GDP): end of year + 7 months. E.g. 2021 is usable from 31 Jul 2022.

**Why chosen:**
- The lags come from **measured evidence** (table above), not memory, and are **rounded up**, i.e. conservative. If a value is actually published a bit earlier, we just use it slightly later, and we never accidentally use it too early.
- One rule per frequency is simple. HICP (observed ~1.5m) gets +2m like unemployment, which is slightly conservative.
- The lags live in a **config file**, so they're easy to change and are covered by tests.

**Not chosen and why:** Per-indicator lags (more precise, but the difference is small here). No lag (leakage).

### D-30: Monthly indicator → quarterly cohort
| Option | Notes |
|---|---|
| **Latest single available month** ⭐ ✅ | e.g. 2022-10 value for GR 2023-Q1 |
| Average of latest 3 available months | Smoother, derived value |

**What it means (plain language):**
For monthly indicators, the cohort gets the **most recent month that was published** by its as-of date: one real number from one source row, kept with its original period (e.g. "2022-10") and its **age** (how many months old it was at the as-of date).

**Why chosen:**
- It's a pure "as-of" lookup (the latest value known on that date), the same logic used for all frequencies.
- **Lineage** stays simple: each value traces back to exactly one source record. Lineage means being able to show where every number came from.
- The monthly series are fairly smooth (e.g. Greek unemployment moves ~0.3 points per month), so averaging would add little.

**Not chosen and why:** 3-month average (less noise, but a derived value with 3 source periods, harder to trace and explain).

### D-31: Annual GDP → quarterly cohorts (frequency integrity)
| Option | Notes |
|---|---|
| **As-of carry-forward + period & age columns** ⭐ ✅ | Latest published annual value with its original year and age |
| Use GDP only in yearly analysis | ~5 points per country |
| Drop GDP from relationship analysis | Loses the cycle lens |

**What it means (plain language):**
GDP is measured **once a year**. With the as-of rule, all 4 hire quarters from Aug 2022 to Jul 2023 see the same value (2021 GDP, the latest published). **Carry-forward** means reusing the latest known value until a newer one is published. The joined table stores, next to the value:
- `source_period` = `2021` (the year it actually measures)
- `source_frequency` = `annual`
- `age_months` = months between the end of 2021 and the cohort's as-of date

So nobody can mistake it for a new quarterly measurement.

**Why chosen:**
- The brief explicitly allows carrying a value forward **if** its original period, status and age are kept and the rule is explained. This option does exactly that.
- It keeps the economic-cycle lens in the same quarterly analysis as the other indicators.

**Consequence for the analysis (Round 7):** GDP has only ~5 distinct values per country, even though it appears in ~20 cohort rows. The analysis must not treat repeated GDP values as independent observations. Ireland is excluded from GDP analysis (D-27).

**Not chosen and why:** Yearly-only analysis (too few points). Dropping GDP (loses a lens).

### Open item for later
The regretted-turnover KPI (monthly TTM, D-21) also needs an alignment rule. The natural extension is the same as-of logic, anchored at the start of each 12-month window or at the month-end. To be decided in Round 7 together with the analysis method.

---

## Round 7a: Analysis method

### How the evidence was produced
The agent built a **preview** of the analysis table in a scratch script (not in the repo), applying D-07…D-31 in simplified form: cleaning rules, NEW_HIRE_6M definition, country × hire-quarter cohorts, as-of join with lags. It then computed Spearman correlations in plain Python (scipy wasn't installed yet). The numbers are preliminary and will be reproduced by the real pipeline.

### Evidence shown
**Analysis table preview (NEW_HIRE_6M):**
```
country cohort    n  retained | unemp (from)     infl (from)     vacancy (from)   GDP (from)
BG      2021-Q1   12   100%   |  6.4 (2020-10)   0.6 (2020-10)   0.8 (2020-Q3)    3.8 (2019)
BG      2021-Q2   17    94%   |  6.0 (2021-01)  -0.3 (2021-01)   0.7 (2020-Q4)    3.8 (2019)
BG      2021-Q4   20    85%   |  5.0 (2021-07)   2.2 (2021-07)   0.8 (2021-Q2)   -3.1 (2020)
RO      2025-Q1   15    93%   |  5.7 (2024-10)   5.0 (2024-10)   0.8 (2024-Q3)    2.3 (2023)
108 rows (6 countries × 18 quarters) | people per row: min 7, median 17, max 29
```

**Problem 1, small groups:** at n=17, one leaver moves the rate by ~6 points; the 95% range for a typical row (87%) is about ±16 points.

**Problem 2, first correlations (Spearman, significance threshold ≈ ±0.19 for 108 rows):**
```
indicator       all rows   within each country   indicator vs time
unemployment     -0.06          -0.10                 -0.21
inflation        -0.14          -0.12                  0.09
job_vacancy       0.03          -0.02                  0.23
gdp_growth        0.00           0.00                  0.21   (IE excluded, 90 rows)
```
→ No indicator is clearly related to 6-month retention (a candidate **non-finding**). Indicators trend with time (**confounding by time** risk).

**Problem 3, multiple comparisons:** 4 indicators × 3 objectives = 12 tests → ~46% chance of at least one false "significant" result at the 5% level.

**Problem 4, repeated/overlapping values:** GDP has only 5 distinct values per country across 18 rows. Monthly TTM turnover values share 11 of 12 months.

**Segment differences (company level, target 86%):** Fixed Term 85% vs Permanent 88%; Manager 91% vs IC/Senior 86%; RO 85% (lowest) … GR/PL 89%; hire year 2021 88%, 2022 87%, 2023 86%, 2024 88%, 2025 91% (H1 only). Small gaps, to be tested.

### D-32: Association method
> 🔁 **Refined by D-54:** within-country is the **formal** test; pooled is **descriptive context only**.
| Option | Notes |
|---|---|
| **Spearman: pooled + within-country** ⭐ ✅ | Rank correlation on country × quarter rows, two views |
| Logistic regression (employee level) | Controls confounders, harder to explain |
| High vs low buckets | Easiest visually, arbitrary cut-offs |

**What it means (plain language):**
- **Correlation** measures whether two things move together, from -1 (opposite) through 0 (unrelated) to +1 (together).
- **Spearman** correlation works on **ranks** (1st, 2nd, 3rd…) instead of raw values, so a few extreme values can't dominate it, and the relationship doesn't need to be a straight line.
- **Pooled:** all 108 country-quarter rows together.
- **Within-country:** each country is compared only with itself over time. We subtract each country's average from its values first, which removes permanent differences between countries (e.g. Greece always having higher unemployment than Poland).

**Why chosen:**
- Easy to explain in an interview and on a dashboard ("rank correlation, -1 to +1").
- Showing both views reveals whether a pattern is a real over-time relationship or just a "countries differ" effect.
- Works directly on the cohort table we already build.

**Known weakness, stated openly:** Spearman looks at one indicator at a time and doesn't control for other factors (contract type, business unit, time trend). This is why results are called **associations**, never causes. Logistic regression is named as a next step.

**Not chosen and why:** Logistic regression (the stronger method, but harder to explain and implement for a first version). Buckets (throw away information, and cut-off points are arbitrary).

### D-33: How uncertainty is shown
> 🔁 **Refined by D-56:** bootstrap CIs are exploratory; they do not fully solve the repeated-observation (dependence) problem.
| Option | Notes |
|---|---|
| **Wilson CI on rates + bootstrap CI on correlations** ⭐ ✅ | Standard, reliable at small n |
| Simple ± normal CI | Breaks at small n / near 100% |
| n only | Minimum only |

**What it means (plain language):**
- A **confidence interval (CI)** is a range such as "retention is 87%, probably between 71% and 96%". Smaller groups give wider ranges.
- **Wilson interval:** a standard formula for the CI of a percentage. Unlike the simple textbook formula, it stays sensible for small groups and for rates near 100% (it can never go above 100%). This matters here because many cohorts have ~17 people and rates around 85–100%.
- **Bootstrap:** to get a range for a correlation, we randomly re-draw the rows (with replacement) 1,000 times, recompute the correlation each time, and take the middle 95% of results. There's no complex formula, just repetition.

**Why chosen:** the brief's "Challenge" view requires sample size **or** uncertainty. Showing both, with methods that are correct at small n, makes the dashboard honest about how much each number can be trusted.

**Not chosen and why:** Normal approximation (can produce ranges above 100% for small groups). n only (meets the minimum but gives no sense of the range).

### D-34: Multiple comparisons
| Option | Notes |
|---|---|
| **Holm correction** ⭐ ✅ | Keeps chance of any false positive ≤ 5% |
| Benjamini-Hochberg (FDR) | Less strict, exploratory |
| No correction, label exploratory | Weak |

**What it means (plain language):**
Each test has a ~5% chance of a false alarm. Run many tests and false alarms become likely: 12 tests give ~46% chance of at least one. **Holm correction** raises the bar step by step. The strongest result must pass a strict threshold (5% ÷ number of tests), the next a slightly easier one, and so on. Overall, the chance of *any* false "significant" result stays at 5%.

**Why chosen:**
- The brief explicitly lists "multiple comparisons" as something to make explicit.
- Holm is a standard method, always at least as powerful as the simpler Bonferroni method, and easy to explain: "we raised the bar because we ran many tests."

**Open point:** exactly **which tests form the corrected set** (the "family") must be defined and documented. See Round 7b.

**Not chosen and why:** Benjamini-Hochberg (accepts some false positives, better for large exploratory screens). No correction (ignores the brief's explicit expectation).

### D-35: Which objectives go into the association analysis ✏️
| Option | Notes |
|---|---|
| NEW_HIRE_6M only; others descriptive ⭐ | Strongest data; others shown as trends only |
| NEW_HIRE_6M + turnover at year-end points | 30 non-overlapping points |
| All three objectives | Senior too small, turnover overlaps |
| **✏️ Option 4 (my answer): NEW_HIRE_6M primary + secondary sensitivity analyses for Objectives 2 and 3** ✅ | See below |

**My decision (full text, to be preserved in methodology/README):**

Use **NEW_HIRE_6M** as the **primary** external-indicator association analysis, because it has the strongest sample support (~1,800 mature employees and 108 country-quarter rows).

Also run **exploratory/sensitivity** association analyses for SENIOR_HIRE_12M and REGRETTED_TURNOVER_12M. The purpose of testing Objectives 2 and 3 is **not** to treat them as equally reliable evidence, but to **demonstrate how their data limitations affect the analysis**.

**For SENIOR_HIRE_12M:**
- Run the same general association approach where technically appropriate.
- Clearly show the very small cohort sizes (roughly ~3 senior hires per country-quarter).
- Show n and uncertainty.
- Clearly label the results as low-power / exploratory.
- Explain that one or two employees can cause a very large change in the retention rate.

**For REGRETTED_TURNOVER_12M:**
- Include an exploratory association analysis, but explicitly account for the fact that monthly TTM observations overlap heavily.
- Do not treat consecutive TTM observations as fully independent observations.
- Clearly explain this limitation in the methodology and dashboard.
- Consider whether a more conservative aggregation or sensitivity approach is appropriate rather than blindly treating all monthly points as independent.

**For all three objectives:**
- Keep the same transparent reporting structure where appropriate: effect/correlation, uncertainty, n, and caveats.
- Apply the chosen multiple-comparison correction consistently to the formal set of tests, and document exactly which tests are included.
- Do not describe a statistically weak/non-significant result as proof that no relationship exists.
- Do not present Objectives 2 and 3 with the same evidentiary strength as NEW_HIRE_6M.

**Dashboard/presentation must visually distinguish:**
1. Primary association analysis: NEW_HIRE_6M
2. Secondary sensitivity/exploratory analyses: SENIOR_HIRE_12M and REGRETTED_TURNOVER_12M

The goal is to show that we deliberately tested the other objectives to understand and demonstrate their limitations, rather than simply ignoring them.

**Labels to use:**
- "NEW_HIRE_6M — Primary association analysis"
- "SENIOR_HIRE_12M — Secondary sensitivity analysis (low power)"
- "REGRETTED_TURNOVER_12M — Secondary sensitivity analysis (overlapping TTM windows)"

**What the key terms mean (plain language):**
- **Low power:** with very few people per group, even a real relationship would probably not be detected. A "no result" here says little.
- **Overlapping TTM windows:** the Jan and Feb TTM values share 11 of 12 months of data, so they are almost the same measurement repeated. Treating 60 of them as independent would overstate how much evidence we have.
- **"Not significant ≠ no relationship":** failing to detect an effect is not proof the effect doesn't exist, especially with small samples.

- **AI_USAGE note:** Agent's recommendation (test only NEW_HIRE_6M, show others descriptively) was **materially changed**. I required testing all three with a clear hierarchy of evidence, so the limitations are demonstrated with data rather than just stated.
- **Follow-up needed (Round 7b):** conservative approach for TTM overlap, turnover alignment anchor, Holm test family definition, senior cohort grain.

---

## Round 7b: Secondary analyses details

### Evidence shown
(Preview script in scratch, same simplified cleaning as Round 7a.)

**SENIOR_HIRE_12M group sizes (266 mature senior hires, hired 2021-01 → 2024-12):**
```
Grain               rows   people per row
country × quarter    90    min 1, median 3, max 8   ← 41 of 90 rows have only 1–2 people
country × year       24    min 5, median 11, max 19

Quarter examples:  BG 2021-Q2: 1/1 = 100%   BG 2021-Q4: 2/4 = 50%   BG 2022-Q2: 1/3 = 33%
Year examples:     BG 2021: 11/15 = 73%     BG 2022: 10/15 = 67%    BG 2024: 10/12 = 83%
```
**Side finding:** senior 12-month retention is roughly **70–80% vs a 90% target**, so the objective appears to be failing. Candidate business finding, to be confirmed by the real pipeline.

**REGRETTED_TURNOVER_12M overlap (company level):**
```
2024-01: 44 / 1131 = 3.89%   2024-02: 44 / 1152 = 3.82%   2024-03: 45 / 1174 = 3.83%
2024-04: 46 / 1195 = 3.85%   2024-05: 48 / 1217 = 3.94%
```
→ Consecutive monthly values barely differ: they are nearly the same data.

**Per-country year-end values (non-overlapping):**
```
GR: 2021 5.5% | 2022 2.7% | 2023 0.5% | 2024 4.1% | 2025 3.9%
RO: 2021 8.3% | 2022 6.9% | 2023 6.4% | 2024 2.4% | 2025 7.1%
PL: 2021 6.1% | 2022 4.2% | 2023 3.1% | 2024 3.0% | 2025 3.8%
IT: 2021 5.2% | 2022 2.0% | 2023 4.8% | 2024 5.6% | 2025 5.1%
IE: 2021 2.8% | 2022 3.4% | 2023 5.0% | 2024 4.0% | 2025 7.2%
BG: 2021 4.9% | 2022 5.0% | 2023 2.7% | 2024 3.4% | 2025 6.2%
```
→ Per-country numerators are tiny (1–18 regretted exits per year). **RO 2021 (8.3%) is above the 7.5% target**, while the company total is below it: a candidate segment finding.

### D-36: SENIOR_HIRE_12M analysis grain
| Option | Notes |
|---|---|
| Country × hire year ⭐ | 24 rows, median 11 people |
| Country × hire quarter | Consistent with primary; 41/90 rows have 1–2 people |
| **Both: quarter shown, year tested** ✅ | Quarterly scatter illustrates noise; formal test at year grain |

**What it means (plain language):**
- The dashboard shows the **quarterly** senior view, deliberately, so a reviewer can *see* how noisy it is (rates jumping between 0%, 33%, 50% and 100%).
- The **formal** association test runs on **country × hire year** (24 rows, ~11 people each), with the as-of anchor on 1 January of the hire year and the same lag rules (D-29).

**Why chosen:**
- It follows D-35's goal directly: *demonstrate* how the data limitation affects the analysis, instead of just stating it.
- The year grain gives the formal test the best chance of being meaningful. It is still low power and labelled as such.

**Consequence:** the senior test uses a different grain from the primary analysis (year vs quarter). This deviation must be documented in the methodology.

- **AI_USAGE note:** Agent recommended year only; I chose to also show the quarterly view to make the limitation visible.

### D-37: Overlapping TTM values in the turnover test
| Option | Notes |
|---|---|
| **Non-overlapping year-end points** ⭐ ✅ | December values only: 5 per country, 30 rows |
| Year-end + monthly block-bootstrap sensitivity | More advanced |
| All monthly points, overlap only explained | Overstates evidence; contradicts D-35 |

**What it means (plain language):**
The formal test uses only the **December** TTM value of each year. Each one covers a separate Jan–Dec period, so no two test points share data. The full monthly line stays in the dashboard as a **trend view**, but it is not used as test data.

**Why chosen:**
- It fulfils D-35's instruction: "do not treat consecutive TTM observations as independent" and "consider a more conservative aggregation".
- Simple to explain: "one value per country per year, no overlap".
- Tradeoff: only 30 rows with small numerators, so low power. It is labelled as such.

**Not chosen and why:** Block bootstrap (statistically valid for overlapping data, but advanced; could be named as a next step). All monthly points (would overstate the evidence about 12-fold).

### D-38: As-of anchor for turnover
| Option | Notes |
|---|---|
| **Start of the 12-month window** ⭐ ✅ | Dec-2024 TTM gets values known on 2024-01-01 |
| End of the window | Partly reflects conditions after exits |
| Middle of the window | Hard to explain |

**What it means (plain language):**
The TTM for Jan–Dec 2024 is compared with indicator values **already published on 1 January 2024**, i.e. the job-market conditions known *before* any of those exits happened. It uses the same lag rules as D-29.

**Why chosen:** it's the same logic as the hire cohorts (D-28): conditions known at the start of the period being measured, with no information from after the events. One consistent rule across all three objectives is easier to explain and test.

**Not chosen and why:** Window end (the conditions partly come after the exits they're meant to explain). Middle (a compromise that is hard to justify).

→ Resolves the "open item" from Round 6.

### D-39: Holm correction family
> ⛔ **Superseded by D-55:** each family now has **4** tests (within-country only), not 8. The "one family per objective" principle is kept.
| Option | Notes |
|---|---|
| **One family per objective** ⭐ ✅ | Each objective's tests corrected together |
| One family for everything (24 tests) | Weak secondaries raise the bar for primary |
| Formal = within-country only | Pooled has no formal status |

**What it means (plain language):**
A **family** is the group of tests corrected together. Each objective gets its own:
- **NEW_HIRE_6M (primary):** 8 tests (4 indicators × pooled / within-country).
- **SENIOR_HIRE_12M (secondary):** 8 tests at year grain (GDP without IE).
- **REGRETTED_TURNOVER_12M (secondary):** 8 tests on year-end points (GDP without IE).

The exact list of tests in each family will be written in the methodology and output with the results.

**Why chosen:**
- Each objective answers a separate business question, so correcting within each question is the standard approach.
- The primary result isn't penalised by the weaker secondary analyses, which fits D-35's evidence hierarchy.

**Not chosen and why:** One big family (the strictest, but lets low-power secondary tests weaken the primary). Within-country only (simpler, but pooled results would have no formal status).

---

## Round 8a: Project structure and packaging

### Discussion: explain it in terms I know
- **Context:** The agent's first Round 8a questions used Python-specific terms (package, Parquet, venv, pyproject.toml, CLI, adapter).
- **What I said:** My background is backend Java / Spring Boot. Can the structure be explained in a way close to that?
- **Effect:** The agent produced a Spring Boot → Python translation table and re-asked the questions using those analogies. The table is kept here as a reference for the interview.

| Spring Boot | Python in this project |
|---|---|
| `pom.xml` / `build.gradle` | `pyproject.toml` |
| `mvn install` | `pip install -e .` |
| Per-project libs / JDK | venv (virtual environment) |
| `application.yml` + `@ConfigurationProperties` | `config/settings.yaml` + Pydantic `Settings` class |
| DTO / record | Pydantic model |
| Entity / domain object | dataclass / Pydantic model |
| `@RestController` | FastAPI router |
| `@Service` | service module |
| `@Repository` | repository class using DuckDB |
| Feign client / RestTemplate | client (adapter) using `requests` |
| `@Autowired` / constructor injection | FastAPI `Depends(...)` / constructor args |
| `@ControllerAdvice` | FastAPI exception handlers |
| `CommandLineRunner` | CLI (`retention run`) |
| Spring Batch job → steps | pipeline job → steps (ingest → curate → metrics → integrate → analyse) |
| JUnit 5 | pytest |
| MockMvc / `@WebMvcTest` | FastAPI TestClient |
| WireMock / `@MockBean` | saved API responses (fixtures) + monkeypatch |
| `resources/static/` | `dashboard/` served by FastAPI |

**Request flow:** Browser → router (controller) → service → repository (DuckDB on Parquet) → Pydantic DTO → JSON.
**Pipeline flow:** `retention run` → job → ingest step (clients → `raw/`) → curate step (→ `canonical/`) → metrics + integrate + analyse (→ `analytical/`).

### D-40: Code and repository layout ✏️
| Option | Notes |
|---|---|
| Spring-style layers ⭐ | domain / client / repository / service / pipeline / api / cli |
| Pipeline-stage folders | ingest / curate / metrics / integrate / analysis / api |
| Flat scripts | 01_ingest.py … weak boundaries |
| **✏️ My answer: use the brief's recommended shape, tweaked for our decisions** ✅ | See below |

**Final layout:**
```
Agentic-Engineering-Assessment/
├─ README.md  AI_USAGE.md               (brief)
├─ pyproject.toml                       tweak: packaging (D-42)
├─ config/                              tweak: settings.yaml (sources, filters, lags), mappings/ (D-08, D-13)
├─ docs/                                (brief) decision_log, requirements_refinement, source_register, methodology, architecture
├─ src/retention/                       (brief: src/) organised by layer:
│   ├─ domain/  client/  repository/  service/  pipeline/  api/  sql/
│   └─ cli.py
├─ tests/                               (brief) unit/, api/, ui/, fixtures/
├─ data/
│   ├─ raw/                             (brief: raw-or-fixtures) untouched source data + metadata; --offline replay
│   └─ curated/                         (brief)
│       ├─ canonical/                   tweak: cleaned, typed, flagged
│       └─ analytical/                  tweak: metrics, joined tables, analysis results
├─ dashboard/                           (brief) index.html, app.js, style.css
└─ presentation/                        (brief)
```

**What it means (plain language):**
The top level follows the brief's suggested repository shape exactly, so reviewers find what they expect. Inside `src/`, the code is split into layers the same way a Spring Boot app is (models, API clients, repositories, services, controllers). Every folder has one job.

**Tweaks from the brief's shape, and why:**
1. `config/`: settings and mapping tables live outside the code (like `application.yml`), so changing a lag or adding a country mapping doesn't need a code change.
2. `data/curated/` split into `canonical/` and `analytical/`: the brief requires "separate source-shaped and canonical records" and "a consumption-ready analytical product".
3. `src/` organised by layer: clear boundaries (a Software-emphasis grading point), and a structure I can explain from my Spring Boot experience.
4. `pyproject.toml`: required for packaging and the CLI command (D-42, D-43).

**Why chosen:** familiar to reviewers (brief's shape) and familiar to me (Spring-style layers inside).

### D-41: Data layer storage
| Option | Notes |
|---|---|
| **Raw as-is + Parquet, queried by DuckDB** ⭐ ✅ | raw = untouched; canonical/analytical = Parquet |
| One DuckDB database file | Binary, hard to inspect; single point of failure |
| CSV everywhere | Loses types; blank vs UNKNOWN ambiguous |

**What it means (plain language):**
- **raw/**: exactly what the source gave us (API JSON, HR CSV), plus a metadata file per fetch (URL, time, status). It's never modified. It doubles as the replay data for `--offline` runs and tests.
- **Parquet**: a file format for tables that **keeps column types** (DATE stays DATE, INT stays INT) and is compact and fast. Think of it as a typed table dump.
- **DuckDB**: runs SQL directly on those Parquet files, like an embedded H2 database but built for analytics.

**Why chosen:**
- **Types matter for our rules:** `UNKNOWN` vs blank (D-12), dates for calendar-month windows (D-16). CSV would turn everything into text.
- Each layer is a set of separate files, easy to inspect and regenerate.
- It maps directly to the production **lakehouse** pattern: raw = bronze, canonical = silver, analytical = gold. That makes the production-architecture section easy to explain.

### D-42: Dependency management
| Option | Notes |
|---|---|
| **pyproject.toml + venv + pip** ⭐ ✅ | Standard, built-in tools |
| uv | Fast, lockfile, extra tool |
| requirements.txt only | Not a package, no CLI |

**What it means (plain language):**
`pyproject.toml` is Python's `pom.xml`: project name, version, dependencies (with version pins), and **dev extras** (test-only libraries, like Maven `test` scope). A **venv** is a project-local folder of libraries, so this project's versions don't clash with anything else on the machine. `pip install -e ".[dev]"` installs everything, including the `retention` command.

**Why chosen:** standard modern Python packaging with only built-in tools. It demonstrates "packaging, dependency management" (a Software-emphasis point) without adding a new tool.

**Not chosen and why:** uv (excellent, but another tool to install and explain). requirements.txt only (no installable package, no CLI command).

### D-43: One-command run
| Option | Notes |
|---|---|
| **CLI: `retention run` / `retention serve`** ⭐ ✅ | Subcommands; `--offline` / `--refresh` |
| Single script | Less polished |
| Makefile | Not native on Windows |

**What it means (plain language):**
Installing the project adds a `retention` command, like running a Spring Boot jar:
- `retention run --offline`: runs the whole pipeline using the saved raw data (no internet needed). This is the default for reviewers.
- `retention run --refresh`: calls the live APIs first, saves new raw data, then runs the pipeline.
- `retention serve`: starts the API and the dashboard at `http://localhost:8000`.

**Why chosen:** the brief requires "one documented command for the core workflow". Subcommands keep the pipeline and the server separate but equally easy to run. `--offline` gives reviewers network-independent, reproducible runs (a brief requirement).

---

## Round 8b: API, tests and reliability

### Evidence shown: proposed endpoints
```
GET /api/health                  → status, data as-of date, last pipeline run
GET /api/filters                 → countries, quarters, objectives, segments (dropdown values)
GET /api/retention/cohorts       ?objective&country&from&to&segment → cohort, n, rate, ci_low, ci_high, target, status
GET /api/retention/turnover      ?country&from&to → month, regretted, avg_headcount, rate, target, unknown_count
GET /api/retention/sensitivity   ?objective → primary vs "if quarantined exits are real"
GET /api/indicators              ?country&indicator → period, value, source_period, age_months, provider
GET /api/association             ?objective → indicator, view, rho, ci_low, ci_high, p_holm, n, label
GET /api/quality                 → exclusions by reason, quarantined count, coverage, freshness
GET /api/sources                 → provider, dataset, licence, cadence, access date
Errors: 400 invalid filter · 404 unknown country/objective · 503 data not built yet
```

### D-44: API shape
| Option | Notes |
|---|---|
| **Resource-style REST, as listed** ⭐ ✅ | One endpoint per resource, query-param filters, clear error codes |
| One "dashboard" endpoint (BFF) | Fewer calls, one big response |
| Fewer, coarser endpoints | Mixes concerns |

**What it means (plain language):**
Like normal Spring `@RestController`s: each kind of data (retention, indicators, association results, quality, sources) has its own URL, and filters are query parameters. Errors use standard HTTP codes with a clear message:
- **400** = your filter is invalid (e.g. `from` after `to`)
- **404** = unknown country/objective
- **503** = data not built yet ("run `retention run` first")

FastAPI generates interactive API docs at `/docs`, the equivalent of Swagger / springdoc.

**Why chosen:**
- Each endpoint maps to one dashboard area (Explore, Understand, Challenge, Trust) from the brief.
- Each can be tested on its own (like MockMvc tests per controller).
- Clear error codes make the dashboard's empty/error states easy to implement (Software-emphasis requirement).
- `/api/health` gives observability: is the data built, and how fresh is it?

**Not chosen and why:** Single BFF endpoint (simpler JavaScript, but one large response and blurred boundaries). Coarse endpoints (mixed concerns, harder to test).

### D-45: UI tests
| Option | Notes |
|---|---|
| **Playwright (Python) smoke tests** ⭐ ✅ | Real headless browser, written in pytest |
| JavaScript unit tests (Node + Jest) | Needs a second toolchain |
| API tests only + manual checklist | Weak on UI-test requirement |

**What it means (plain language):**
Playwright is a modern Selenium: it opens the dashboard in a real (invisible, "headless") browser and acts like a user. Our tests:
- the page loads and shows data
- changing a filter updates the chart/table
- a filter with no data shows a friendly "no data" message (empty state)
- an API error shows a friendly error message (error state)
- basic accessibility: every dropdown has a label

"Smoke test" means a few quick checks that the main paths work, not an exhaustive test of every pixel.

**Why chosen:**
- The brief explicitly asks for "automated tests across service and UI boundaries". Playwright tests the UI through the real API.
- Written in Python/pytest, the same as the other tests, so there is no second toolchain.

**Cost accepted:** a one-time browser download (~150 MB) via `playwright install chromium`.

**Not chosen and why:** Jest (needs Node.js). Manual checklist (not automated).

### D-46: Schema and quality enforcement
> 🔁 **Refined by D-61:** Pandera checks structure only; business-quality rules are separate Python code.
| Option | Notes |
|---|---|
| **Pandera schemas** ⭐ ✅ | Declarative column rules, clear per-row errors |
| Hand-written checks | More code, less standard |
| Great Expectations | Heavy for this size |

**What it means (plain language):**
Pandera is like **Bean Validation** (`@NotNull`, `@Pattern`) but for tables. We declare a schema class, e.g. `country_code` must be one of GR/RO/PL/IT/IE/BG/Unknown, `hire_date` is a date, `regretted_exit` ∈ {TRUE, FALSE, UNKNOWN}. Validation checks every row and reports exactly which rows break which rule.

**Why chosen:**
- It gives a **schema contract** per data layer (a brief requirement: "schema contracts").
- If a source changes shape (e.g. like the HICP dataset's `coicop` → `coicop18` change, D-25), the pipeline fails with a clear message instead of producing wrong numbers.
- It's declarative and readable, so it doubles as documentation of each table.

**How it fits our quality rules:** data problems we *expect* (D-07…D-14) are **flagged**, not failed. Pandera checks that the **output** of cleaning meets the contract, e.g. every row has a valid country or `Unknown`, and every flag is a known reason code.

**Not chosen and why:** Hand-written checks (more code to write and explain). Great Expectations (powerful, but many concepts and much setup for a small project).

### D-47: External API resilience
> 🔁 **Refined by D-62:** an explicit status record per source (fresh / stale / unavailable, error, retry count). Stale data is never shown as fresh.
| Option | Notes |
|---|---|
| **requests + urllib3 Retry + timeouts** ⭐ ✅ | Built-in retry with backoff; partial-failure handling |
| tenacity `@retry` decorator | ≈ `@Retryable`; extra library |
| Simple try/except, fail fast | Fails "safe partial-failure handling" |

**What it means (plain language):**
- **Timeout:** every HTTP call gives up after N seconds instead of hanging forever.
- **Retry with exponential backoff:** on temporary errors (429 "too many requests", 5xx server errors), wait and try again with growing waits (1s, 2s, 4s…), like Spring Retry's backoff policy.
- **Partial-failure handling:** if one source still fails after retries, the pipeline logs a clear error, **keeps the last good raw data** for that source, continues with the other sources, and marks that source as **stale** in the quality report and the dashboard's Trust view.

**Why chosen:**
- The brief requires "useful failure messages and safe partial-failure handling" and (Software emphasis) "resilient API handling and observable failures".
- Uses the retry support built into the `requests` stack, so there is no extra library.
- Keeping the last good raw data means one provider outage doesn't break the whole product.

**Not chosen and why:** tenacity (very readable, but an extra dependency for the same result). Fail fast (one outage would stop everything).

---

## Round 8c: Re-runs, logging, code quality, CI

### D-48: Re-run behaviour
> 🔁 **Refined by D-62:** every run records a `run_id` and the exact raw snapshot(s) it was built from (lineage).
| Option | Notes |
|---|---|
| **Raw kept by fetch date; curated fully rebuilt** ⭐ ✅ | Raw history never overwritten; curated deterministic |
| Raw overwritten; curated fully rebuilt | No raw history |
| Incremental upsert by period | Production-like, much more logic |

**What it means (plain language):**
- **Raw:** each `--refresh` saves source data in a **new dated folder**, e.g. `data/raw/eurostat/une_rt_m/2026-09-27/`, plus a small "latest" pointer file saying which fetch is current. Old fetches are never overwritten, so we keep a history.
- **Curated (canonical + analytical):** rebuilt **from scratch** from the latest raw data on every run. The new files are written to a temporary folder first and swapped in only when the whole run succeeds, so a failed run never leaves half-written tables.
- **Deterministic:** the same raw input always produces exactly the same output (the bootstrap uses a fixed random seed).
- **Idempotent:** running twice gives the same result as running once.

**Why chosen:**
- The brief requires "deterministic reruns and intentional overwrite/upsert behaviour". This is intentional: raw is **append-only**, curated is **full overwrite**.
- Raw history lets us replay any past fetch, and see what changed when a provider **revises** data (the vintages limitation from Round 6).
- A full rebuild is simple and correct at our size (~5,000 rows). In production, the same design would move to incremental processing (production-architecture doc).

**Not chosen and why:** Overwriting raw (loses history and replay). Incremental upsert (much more logic for no benefit at this size).

### D-49: Logging and observability
| Option | Notes |
|---|---|
| **Python logging + run summary file** ⭐ ✅ | Levels to console + `run_summary.json` |
| Plain print | No levels or structure |
| Structured JSON logs (structlog) | Production-style, extra library |

**What it means (plain language):**
- Python's built-in `logging` works like SLF4J/Logback: INFO / WARNING / ERROR levels, printed to the console.
- Each run also writes `run_summary.json`: run id, start/end time, each step's duration, rows in/out per step, exclusions by reason, and each source's status (fresh / stale / failed).
- `/api/health` and the dashboard's **Trust** view read this file, so freshness and data health are visible to users.

**Why chosen:** "observable failures" (Software emphasis) and "freshness, coverage, quality exclusions" (brief's Trust requirement) come from one simple file, with no extra library.

### D-50: Code quality tools
| Option | Notes |
|---|---|
| **ruff + type hints** ⭐ ✅ | Linter + formatter; typed function signatures |
| ruff + type hints + mypy | Enforced types, noisy with pandas |
| None | Weaker quality |

**What it means (plain language):**
- **ruff:** one fast tool that both **lints** (finds bugs and bad patterns, like Checkstyle/SpotBugs) and **formats** (consistent style, like Spotless).
- **Type hints:** function signatures declare types (`def cohort_rate(n: int, retained: int) -> float`), like Java types. Python doesn't enforce them at runtime, but they document the code and help the editor catch mistakes.

**Why chosen:** standard, very low setup, and improves readability, which matters because I have to explain every file.

**Not chosen and why:** mypy (a real type checker, but produces many warnings with pandas code; can be added later). None (weaker engineering signal).

### D-51: Continuous integration ✏️
> 🔁 **Briefly superseded by D-60, then restored by D-64:** no CI; tests are run locally by hand.
| Option | Notes |
|---|---|
| GitHub Actions: lint + tests ⭐ | Every push runs ruff + all tests offline |
| GitHub Actions: lint + unit/API only | Skips browser tests in CI |
| No CI | Local only |
| **✏️ My answer: no CI for now, maybe add later** ✅ | |

**What it means (plain language):**
CI (continuous integration) runs the tests automatically on a clean machine at every push. For now tests run **locally** only, with the exact commands documented in the README.

**Why:** focus time on the core vertical slice first. CI can be added at the end if time allows (a single workflow file).

**Consequence:** the README must give exact local test commands. "Add GitHub Actions" is listed as a next step / possible later addition.

- **AI_USAGE note:** Agent recommended CI; I deferred it to prioritise the core slice (a deliberate timebox decision, as the brief encourages).

---

## Carry into final docs (README / methodology)
Text that must be copied into the final deliverables, not only kept in this log:
- D-35 full rationale and the three analysis labels → `docs/methodology.md` and README "Analysis" section.
- D-10 / D-12 quarantine and UNKNOWN principle → `docs/requirements_refinement.md` and the dashboard Trust view.
- D-23 population limitation ("employees hired since 2020") → README "Known limitations".
- D-25 / Round 6 side finding (discontinued / frozen Eurostat datasets) → `docs/source_register.md`.
- Round 6 revisions/vintages limitation → `docs/methodology.md` and README "Known limitations".
- D-36 grain deviation (senior test at year grain) and D-55 exact test lists per family → `docs/methodology.md`.
- D-56 bootstrap/dependence caveat, D-57 standard wording for unverified exits, D-58 lag wording, D-59 GDP definition and Ireland handling, D-63 language rules → `docs/methodology.md`, README, dashboard text and presentation.
- Candidate findings spotted during previews (to be confirmed by the real pipeline): no clear indicator association for NEW_HIRE_6M (non-finding); senior 12m retention ~70–80% vs 90% target; RO 2021 regretted turnover above target; company regretted turnover jump in 2025.

---

## Recurring principle (emerged from D-10 and D-12)

**Uncertain data is preserved, flagged and quarantined from the primary KPI. It is never deleted or imputed. Its impact is shown through sensitivity analysis.**

---

## Clarification questions to submit (collected so far)
1. Is an HTML/JS dashboard served by a local FastAPI service acceptable for the "HTML" experience layer? (D-04, D-05)
2. Is `Sr Mgmt` the same level as `Senior Leader`? (D-13)
3. Which career levels count as "Senior hires"? (D-14)
4. Is an exit exactly 90 days after hire an expected probation-end pattern, or a system default? (D-10)
5. Does the events file contain the full workforce, or only employees hired since 2020? (D-23)

---

## Round 9: How we implement

### D-52: Implementation pace ✏️
| Option | Notes |
|---|---|
| **One step at a time, pause to review** ⭐ ✅ | Build → show → explain in Spring terms → wait for OK |
| Two to three steps per chunk | Faster, bigger reviews |
| Build everything, then walk through | Risky for "don't submit code you can't explain" |

**My addition:** after **every** step, the agent must also recap what we did and **re-explain the decisions it implements**, linking code to decisions (decision IDs in code comments), in simple words, because I will forget. If we discover something during development that changes a decision, it must be surfaced, discussed and logged.

**Why:** the brief says "do not submit code or analysis you cannot explain". Linking every piece of code to a decision makes both the code and the decisions easy to recall in the interview.

**How decision changes are recorded:** a new entry (e.g. D-60) with the evidence, marked "changes D-xx", and the original entry gets a note pointing to it. Nothing is silently rewritten.

### D-53: Git commits ✏️
| Option | Notes |
|---|---|
| Commit after each approved step ⭐ | Agent commits |
| Commit and push | Agent commits and pushes |
| No commits, I'll commit myself | Agent only changes files |
| **✏️ My answer: no commits from the agent; it warns me and provides a commit message after each major step, I do the rest** ✅ | |

**Why:** I stay in control of the repository history. Ready-made messages keep the history clean and consistent.

---

## Round 10: Critical review refinements (2026-09-27)

- **Context:** After Step 1, I did a critical review of the whole design and gave the agent superseding instructions (statistics emphasis, Holm structure, wording, CI, lineage). The agent first inspected the implementation, compared it against the review, and listed what was already correct, what must change and what could be simplified. Only Step 1 (skeleton) existed in code, so most changes are design refinements.
- **Confirmed unchanged by the review:** D-12…D-14 (regretted UNKNOWN, Sr Mgmt, senior definition), D-16…D-19 (calendar-month windows, exit rule, immature cohorts, quarterly cohorts), D-20…D-23 (turnover definition), D-30/D-31 (monthly and annual alignment), D-35…D-38 (analysis roles and grains).

### D-54: Within-country is the formal test; pooled is descriptive (refines D-32)
**What changed:** Before, pooled and within-country Spearman were both formal tests. Now **only within-country** is a formal (Holm-corrected) test. Pooled results are still shown, labelled *"Descriptive pooled context — not the primary formal test"*, with no p-value presented as formal evidence.

**Why:** A pooled correlation mixes two different things:
1. **Between-country differences:** e.g. Greece always has higher unemployment *and* maybe different retention than Poland, for many reasons unrelated to unemployment.
2. **Within-country changes:** when Greece's unemployment changes, does Greek retention change too?

The business question ("do external conditions help explain retention?") is about (2). Pooled correlation mostly captures (1).

**How it works:** for each country, subtract its own average from both the indicator and retention, then compute Spearman on these "deviations from the country's normal level". What's left is only the over-time movement inside each country.

**Config:** `analysis.formal_view: within_country`, `analysis.descriptive_views: [pooled]` (tested in `tests/unit/test_config.py`).

**Limitation to state:** demeaning removes each country's average, so the effective sample is a bit smaller than the row count (6 country means are "used up"). n is still reported as rows, with this caveat.

### D-55: Holm families = 4 tests per objective (supersedes D-39)
| Objective | Formal tests in its Holm family | Role |
|---|---|---|
| NEW_HIRE_6M | 4 = {unemployment, inflation, job vacancy, GDP} × within-country, on country × hire quarter | Primary |
| SENIOR_HIRE_12M | 4 × within-country, on country × hire year | Secondary (low power) |
| REGRETTED_TURNOVER_12M | 4 × within-country, on country × December TTM (2021–2025) | Secondary (overlapping TTM windows) |

**Why:** pooled is no longer formal (D-54), so it doesn't belong in the family. Fewer tests in a family means Holm raises the bar less, which is fairer to the primary analysis. GDP tests exclude IE (D-59), and that is reported with the result.

### D-56: Bootstrap caveats (refines D-33)
**Kept:** Wilson CIs for rates; bootstrap CIs for Spearman correlations.
**Added honesty:** our rows are **not independent**. The same country appears in many rows over time (repeated observations), and neighbouring periods are related. A standard row bootstrap assumes independence, so its CIs are likely **too narrow**. A country-cluster bootstrap would respect the country grouping, but with only **6 countries** it is itself unreliable. So bootstrap CIs are presented as **exploratory**, with this caveat in the methodology and dashboard.
- Removed from "possible later additions": block bootstrap (the caveat is the honest answer at this scope).

### D-57: 90-day exits: wording and flag name (refines D-10)
**Kept:** quarantine from primary metrics, keep in raw/source layers and quality reporting, sensitivity analysis treating them as valid exits.
**Changed:** the flag name `SUSPECT_PLACEHOLDER_EXIT` → **`UNVERIFIED_EXIT`**. The old name itself implied "placeholder", which we cannot prove. The termination date exists; the ambiguity is the **missing termination_type plus the repeated 90-day pattern**.
**Standard wording (use everywhere):**
> "Unverified exits are quarantined from the primary analysis because their termination classification is incomplete; a sensitivity analysis assesses the impact of treating them as valid exits."
- Note: the flag rename is the agent's interpretation of the review's wording rule, flagged to me for confirmation.

### D-58: Publication lags: correct wording (refines D-29)
**Kept:** monthly +2, quarterly +3, annual +7 months.
**Wording:** "conservative fixed-lag approximations based on observed source availability". They are **not** exact historical publication timestamps.
**Also documented:** current APIs return **revised** historical values, not necessarily the values available on the historical as-of date (no vintages).

### D-59: GDP explained; Ireland handled explicitly (refines D-27)
- **GDP** = Gross Domestic Product. **GDP growth** = % change in real economic output vs the previous year.
- Role: the **economic-cycle** lens, next to unemployment (labour supply), job vacancy rate (labour demand) and inflation (cost of living). No causal claim.
- **Ireland:** GDP data is **retained** in the raw, canonical and analytical layers and the dashboard. It is excluded only from the GDP association tests, because multinational accounting makes Irish GDP unsuitable as a local economic-cycle measure. The exclusion is **reported next to the result** (e.g. "GDP test: 5 countries, IE excluded — see caveat"), never silently removed.

### D-60: Small CI with GitHub Actions (supersedes D-51)
> ⛔ **Reversed by D-64:** the workflow was added and then removed; see D-64.
- `.github/workflows/ci.yml`: install → `ruff check .` → `ruff format --check .` → `pytest`.
- Uses only local replay fixtures; it must **never** call the live Eurostat/World Bank APIs.

### D-61: Pandera for structure, Python for business rules (refines D-46)
| Responsibility | Tool | Examples |
|---|---|---|
| **Structure** (schema contract) | Pandera | column exists, type is date/int/string, allowed values for enums (`TRUE/FALSE/UNKNOWN`, flag codes), canonical country in list |
| **Business quality** (semantic rules) | Plain Python functions in `service/` | duplicates (D-07), invalid dates (D-09), missing classification (D-11, D-12), unverified exits (D-57), maturity (D-18) |

**Why:** the starter data is **intentionally imperfect**. Business rules must **flag and keep** bad rows, not crash. If Pandera enforced business rules, it would either reject valid-but-imperfect data or need many exceptions. Pandera checks that the **output** of our rules has the promised shape.

### D-62: Source status record and run lineage (refines D-47, D-48)
**Per source, per run, recorded in `run_summary.json`:**
`provider`, `indicator`, latest `source_period`, `loaded_at` (load timestamp), `status` = `fresh` / `stale` / `unavailable`, `error` (if any), `retry_count`, `raw_snapshot` (path of the raw fetch used).

**Rules:**
- **fresh:** fetched successfully in this run.
- **stale:** fetch failed, last good snapshot used. Shown as stale in the API and dashboard, **never presented as fresh**.
- **unavailable:** no usable snapshot at all.
- Every run gets a `run_id`; curated outputs record the `run_id` and raw snapshot references they were built from. Build into a temp folder and swap on success (D-48).
- Local filesystem only; no platform.

### D-63: Statistical language rules (new)
**Never say:**
- "Spearman proves there is no relationship."
- "No significant correlation means there is no relationship."
- "GDP causes retention." / "Unemployment causes turnover."

**Say instead:**
- "The exploratory analysis did not show a clear association."
- "The analysis did not provide strong evidence of an association in this sample."
- "These results are associative, not causal."
- "Small sample sizes / repeated observations limit inference."

**Every correlation result shows:** correlation (effect), confidence interval, n, Holm-corrected p-value (formal tests only), and a "correlation does not imply causation" caveat.

**Dashboard labels (from D-35, confirmed):**
- "NEW_HIRE_6M — Primary association analysis"
- "SENIOR_HIRE_12M — Secondary sensitivity analysis (low power)"
- "REGRETTED_TURNOVER_12M — Secondary sensitivity analysis (overlapping TTM windows)"
- Pooled: "Descriptive pooled context — not the primary formal test"

### Implementation of Round 10
- `config/settings.yaml`: `formal_view`, `descriptive_views`, per-objective role and grain; lag and Ireland comments reworded.
- `src/retention/config.py`: typed fields for the above.
- `tests/unit/test_config.py`: 2 new tests (formal = within-country with 4 tests per family; only NEW_HIRE_6M is primary).
- `.github/workflows/ci.yml`: added, then removed again (D-64).
- Verified locally: `ruff check .` clean, `ruff format --check .` clean, `pytest`: 11 passed.

- **AI_USAGE note:** This round is a clear example of **human-directed correction** of the agent's earlier design. The agent had proposed 8-test families (pooled + within); my review changed that, tightened the statistical language, and required explicit lineage and source-status fields.

### D-64: CI reversed: local, manually executed tests only (reverses D-60, restores D-51) ✏️
- **What I said:** Rework the decisions: no GitHub Actions, only local tests run manually. CI is over-engineering at this stage; we can add it later.
- **What changed:** `.github/workflows/ci.yml` was deleted. D-51 ("no CI for now") is back in force.
- **How tests run:** by hand, from the project folder with the virtual environment active:
  ```
  ruff check .
  ruff format --check .
  pytest
  ```
  The README will list these exact commands.
- **Kept from the review:** tests must never call the live Eurostat/World Bank APIs. They use local replay fixtures, so they are deterministic and work offline.
- **Why:** scope discipline (review point 18: avoid features that don't strengthen the submission). CI adds a moving part to maintain and explain, and gives little extra value for a single-developer assessment.
- **Later:** CI remains on the "possible later additions" list.
- **AI_USAGE note:** Example of me reversing my own earlier review decision after weighing scope. Both steps are recorded rather than rewritten.

---

## Round 11: Ingestion decisions (Step 2)

### D-65: HR starter files location
| Option | Notes |
|---|---|
| Copy into `data/raw/hr/` after checksum check ⭐ | Keep `assessment_files/` as original drop |
| **Move `assessment_files/` into `data/raw/hr/`** ✅ | One copy only |
| Leave in place, read directly | HR outside the raw layer |

**What it means:** the supplied files now live in the raw layer like every other source. They are not duplicated. Git records the move as a **rename**, so history still shows the files as originally delivered (commit `b0b7993`) and then moved.
**Why:** a single copy avoids two versions drifting apart. The SHA-256 check against the manifest (verified: all 3 files match exactly in hash and byte size) proves the moved files are the ones supplied.
- **AI_USAGE note:** agent recommended copying and keeping the original; I preferred a single copy.

### D-66: Commit replay data
| Option | Notes |
|---|---|
| **Yes, commit one real refresh** ⭐ ✅ | `retention run --offline` works immediately for reviewers |
| No, only small test fixtures | Reviewers must fetch live data first |

**Why:** the brief asks for "replay data for network-independent review". With the snapshots committed, a reviewer gets exactly our numbers without internet. The files are small.

### D-67: Flag name `UNVERIFIED_EXIT` (confirms D-57)
Neutral name: the exit cannot be verified. It makes no claim that the date is a placeholder.

### D-68: Source status in offline mode: `replayed`
| Option | Notes |
|---|---|
| **New status `replayed`** ⭐ ✅ | fresh / replayed / stale / unavailable |
| Use `stale` | Mixes "failed" with "offline by choice" |
| Use `fresh` | Conflicts with "never present stale as fresh" |

**What it means (the 4 statuses):**
| Status | Meaning |
|---|---|
| `fresh` | Fetched successfully **in this run** (`--refresh`) |
| `replayed` | **Deliberately** loaded from a saved snapshot (`--offline`), shown with the snapshot's original fetch date |
| `stale` | A fetch **was attempted and failed**; the last good snapshot was used instead |
| `unavailable` | No usable data at all (fetch failed or offline, and no snapshot exists) |

**Why:** D-62 defined fresh/stale/unavailable for refresh runs, but the offline mode (the reviewers' default) fetches nothing *by design*. Calling that "stale" would make a normal replay look like a failure; calling it "fresh" would break the "never stale-as-fresh" rule. `replayed` is honest about both.

### D-69: HR snapshot folder name
| Option | Notes |
|---|---|
| **Pack as-of date: `2025-12-31`** ⭐ ✅ | The date the workforce data describes |
| Pack version: `v1.0` | Less clear what time it covers |
| No subfolder | Inconsistent with dated snapshots |

**Why:** API snapshots are named by fetch time; the HR pack was delivered, not fetched, so its natural "date" is the as-of date in the manifest. A future HR extract would get its own folder.

### D-70: Simple, explainable code style
- **Context:** Reviewing Step 2, I asked whether `repository/mappings.py` could be written more simply. The agent showed the compact version (list/dict comprehensions) next to a plain-loop version and its Java equivalent.
- **Decision:** apply the simple style **everywhere**, rewriting Step 1 and Step 2 code now and following it in all future steps:
  - plain `for` loops instead of comprehensions (Java-like)
  - one idea per line; intermediate variables with clear names
  - short numbered comments for the steps inside a function
  - docstring with an input → output example where it helps
  - error messages that say exactly what is wrong and where to fix it
- **Why:** the brief says "do not submit code you cannot explain". Slightly longer code that reads like my Java is easier to explain and defend in the interview.
- **Guarantee:** behaviour must not change. The same tests must pass before and after the rewrite.
- **Allowed exceptions:** very small, obvious one-liners where a loop would be noisier. Pandas/SQL code in later steps follows the library's normal style, with comments.

---

## Implementation log

### Step 1: Project skeleton (2026-09-27)
**Built:** `.gitignore`, `pyproject.toml`, `config/settings.yaml`, `config/mappings/*.csv`, `src/retention/` (config, CLI, empty layer packages), `tests/unit/` (9 tests), `.venv`.
**Decisions implemented:** D-40 (layout), D-42 (packaging), D-43 (CLI), D-49 (logging setup), D-50 (ruff), D-24…D-29 and D-33/34/48 (as config values), D-08/D-13 (mapping tables).
**Verified:** `retention --help` and `retention run` work; `pytest`: 9 passed; `ruff check`: clean (ruff caught one over-long line, auto-formatted).
**Issues met:** the first `pip install` hung silently for more than 10 minutes (quiet mode hid the output). It was stopped, pip connectivity was tested, then the install was re-run with visible output and succeeded.
**Installed versions:** pandas 2.3.3, pyarrow 25.0.1, duckdb 1.5.5, requests 2.34.2, pydantic 2.13.5, pandera 0.33.1, numpy 2.4.6, scipy 1.17.1, fastapi 0.141.1, uvicorn 0.54.0, pytest 9.1.1, pytest-playwright 0.9.0, ruff 0.16.9.
**Decision changes:** none at the time; Round 10 (D-54…D-64) later refined config and tests (11 tests).
**Review:** I ran the checks myself (activate venv in cmd with `activate.bat`, `retention --help`, `retention run`, `ruff check .`, `ruff format --check .`, `pytest` → 11 passed, `git status`). All passed; I confirmed and committed Step 1 myself.

### Step 2: Ingestion (2026-09-27)
**Built:**
- `client/http.py` (session with timeout + retry/backoff, `SourceError`)
- `client/eurostat.py`, `client/worldbank.py` (request building + response validation)
- `client/hr_files.py` (SHA-256 check vs manifest)
- `repository/raw_repository.py` (dated snapshots, `latest.json`, never overwrite)
- `repository/mappings.py` (provider country codes)
- `domain/source_status.py` (4 statuses)
- `pipeline/ingest.py`, `pipeline/run_summary.py`, `pipeline/job.py`; CLI `run` now calls the job
- Tests: `test_clients.py`, `test_raw_and_hr.py`, `test_ingest.py`, updated `test_cli.py` (30 tests total)

**Decisions implemented:** D-08, D-24…D-27, D-41, D-47, D-48, D-49, D-62, D-65, D-66, D-68, D-69.

**Verified:**
- `pytest`: 30 passed; `ruff check .` and `ruff format --check .` clean.
- `retention run --offline` before any fetch → all 4 indicators `unavailable` with the hint "run `retention run --refresh` first", exit code 1, HR pack `replayed`.
- `retention run --refresh` → all 4 `fresh`; latest periods: unemployment 2026-08, inflation 2025-12, job vacancy 2025-Q4, GDP 2025 (consistent with Round 5 research). Job vacancy: 168 observations = 6 countries × 28 quarters.
- `retention run` (offline) → all `replayed` from the saved snapshots, exit code 0.
- Raw API snapshots total ~40 KB.

**Issues met:**
- One test failed at first: the fake client reused the same timestamp, so the second run tried to write a snapshot folder with the same name, and the repository correctly refused to overwrite it (D-48). Fixed in the test (the fake clock now advances), not in the code.
- ruff fixed one import ordering.

**Rule added while coding:** an HTTP 200 response with **zero observations** is treated as a failure (`SourceError`). This comes straight from the Round 5 lesson, where the wrong code `JOBRATE` returned HTTP 200 with no data.

**Decision changes:** none.

**Open for later:** `data/curated/run_summary.json` changes on every run. Whether to commit generated curated outputs will be decided when Step 3 creates them.

**Style rewrite (D-70):**
- Files rewritten: `config.py` (Step 1), `repository/mappings.py`, `client/http.py`, `client/eurostat.py`, `client/worldbank.py`, `client/hr_files.py`, `repository/raw_repository.py`, `pipeline/ingest.py`, `pipeline/run_summary.py`, `pipeline/job.py`.
- What changed: comprehensions replaced by plain loops; numbered step comments; docstrings with examples; clearer names (e.g. `_use_latest_snapshot`, `_check_hr_pack`); keyword arguments when building status objects.
- Unchanged: `cli.py` and `domain/source_status.py` were already simple.
- Behaviour check: the same 30 tests pass; `retention run` gives the identical status table.

---

## Planning complete: next is implementation
All planning rounds (0–8c) are done. Implementation proceeds step by step; any new decision that comes up during coding is recorded here in the same format.
Possible later additions (deferred): CI with GitHub Actions (D-51, D-64), logistic regression (D-32), Kaplan-Meier (D-18), mypy (D-50). (Block bootstrap dropped in D-56.)
