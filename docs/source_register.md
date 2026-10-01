# Source register and contracts

Every input the product uses: provider evidence, licence, indicator, unit, dimensions, cadence, lag, canonical
mapping and limitations. Decisions: D-24…D-27 (choice), D-29/D-58 (lags), D-59 (Ireland), D-65/D-69 (HR pack),
D-47/D-48/D-62/D-68 (ingestion and status). All values below were read from the committed raw snapshots and
the canonical quality report, not written from memory.

## Summary

| Indicator | Lens | Provider · dataset | Frequency | Unit | Coverage in snapshot | Lag rule |
|---|---|---|---|---|---|---|
| `unemployment` | labour supply | Eurostat `une_rt_m` | monthly | % of labour force | 2019-01 → 2026-07 (IE → 2026-08), 547 values | +2 months |
| `inflation` | cost of living | Eurostat `prc_hicp_manr` | monthly | % annual rate of change | 2019-01 → 2025-12, 504 values | +2 months |
| `job_vacancy` | labour demand | Eurostat `jvs_q_nace2` | quarterly | % of jobs vacant | 2019-Q1 → 2025-Q4, 168 values | +3 months |
| `gdp_growth` | economic cycle | World Bank `NY.GDP.MKTP.KD.ZG` | annual | % annual growth (constant prices) | 2019 → 2025, 42 values | +7 months |
| `hr_pack` | workforce | Assessment starter pack | snapshot | - | hires 2020 → 2025, as of 2025-12-31 | - |

Brief minimum: ≥ 2 providers (Eurostat, World Bank), ≥ 3 indicators (4), ≥ 2 lenses (4), ~3 years of history
(7 years). All 6 countries have **no missing periods** in any indicator (quality report, coverage section).

---

## 1. Eurostat: unemployment rate (`une_rt_m`)

| Field | Value |
|---|---|
| Provider | Eurostat (European Commission), dissemination API 1.0, JSON-stat 2.0 |
| Request | `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/une_rt_m?s_adj=SA&age=TOTAL&sex=T&unit=PC_ACT&geo=EL&geo=RO&geo=PL&geo=IT&geo=IE&geo=BG&sinceTimePeriod=2019-01` |
| Dimensions used | `s_adj=SA` (seasonally adjusted), `age=TOTAL`, `sex=T` (both), `unit=PC_ACT` (% of labour force), `geo`, `time` (`YYYY-MM`) |
| Snapshot | `data/raw/eurostat/une_rt_m/20260927T120052Z/` (fetched 2026-09-27 12:00:52 UTC; 547 observations; latest period 2026-08) |
| Why this indicator | Tight labour market (low unemployment) = easier to leave; the most direct "can employees find another job?" signal (D-24) |
| Observed publication lag | ~2 months after the month ends (on 2026-09-27 the newest value was 2026-07 for most countries) |

## 2. Eurostat: HICP inflation (`prc_hicp_manr`)

| Field | Value |
|---|---|
| Request | `.../data/prc_hicp_manr?coicop=CP00&geo=EL&geo=RO&geo=PL&geo=IT&geo=IE&geo=BG&sinceTimePeriod=2019-01` |
| Dimensions used | `coicop=CP00` (all items), `unit` = annual rate of change, `geo`, `time` (`YYYY-MM`) |
| Snapshot | `data/raw/eurostat/prc_hicp_manr/20260927T120053Z/` (504 observations; latest 2025-12) |
| Why | Cost-of-living pressure may push people to seek better pay; large variation between countries (D-25) |
| Observed lag | ~1–1.5 months (2025-12 present in the 2026-02-06 update); the +2 rule is slightly conservative |
| **Schema evolution** | The dataset is **discontinued** (frozen in Feb 2026, label "(1997-2025)"): Eurostat moved HICP to ECOICOP v2 in **`prc_hicp_minr`**, with dimension `coicop18` instead of `coicop`. The old dataset fully covers our 2019–2025 window. **Migration path:** point the adapter to `prc_hicp_minr`, map `coicop18` = all items, and re-verify history depth. |

## 3. Eurostat: job vacancy rate (`jvs_q_nace2`)

| Field | Value |
|---|---|
| Request | `.../data/jvs_q_nace2?nace_r2=B-S&sizeclas=TOTAL&indic_em=JVR&s_adj=NSA&geo=EL&geo=RO&geo=PL&geo=IT&geo=IE&geo=BG&sinceTimePeriod=2019-Q1` |
| Dimensions used | `nace_r2=B-S` (industry, construction and services), `sizeclas=TOTAL`, `indic_em=JVR` (vacancy **rate**), `s_adj=NSA`, `geo`, `time` (`YYYY-Qn`) |
| Snapshot | `data/raw/eurostat/jvs_q_nace2/20260927T120053Z/` (168 observations; latest 2025-Q4) |
| Why | Labour demand: more open jobs = more chances to be recruited away (D-26) |
| Observed lag | ~3 months after the quarter ends (2025-Q4 present in the 2026-03-20 update) |
| Notes | **Not seasonally adjusted** (the version with complete coverage), so seasonal patterns remain. **Provisional values:** 14 rows carry status `p` (BG 12, IE 1, IT 1); the flag is kept in the canonical and aligned tables. The dataset label "(2001-2025)" suggests it may also be frozen by a classification change. **Verification:** the first guessed code `JOBRATE` returned HTTP 200 with zero values; the dataset's real dimension list gave `JVR` (now "HTTP 200 with no observations" is a failure in code). |

## 4. World Bank: GDP growth (`NY.GDP.MKTP.KD.ZG`)

| Field | Value |
|---|---|
| Provider | World Bank, World Development Indicators, API v2 (JSON) |
| Request | `https://api.worldbank.org/v2/country/GRC;ROU;POL;ITA;IRL;BGR/indicator/NY.GDP.MKTP.KD.ZG?format=json&date=2019%3A2025&per_page=1000` |
| Dimensions used | country (ISO alpha-3), `date` (year) |
| Snapshot | `data/raw/worldbank/NY.GDP.MKTP.KD.ZG/20260927T120053Z/` (42 observations; latest 2025; source last updated 2026-07-13) |
| Why | Adds the economic-cycle lens and satisfies the two-provider rule (D-27) |
| Observed lag | ~6.5 months (2025 present in the 2026-07-13 update) |
| **Ireland** | Irish GDP is distorted by multinational accounting (2023 −2.5%, 2025 +12.3%). IE data is **kept and shown** everywhere; it is excluded only from the GDP association tests, and the exclusion is reported next to each result (D-59, `exclude_from_analysis: [IE]`). |
| Frequency integrity | One value per year. When a newer cohort needs GDP, the latest published annual value is **carried forward with its own period, frequency and age** (e.g. "2022, annual, 19 months old"); it is never presented as a new quarterly or monthly value (D-31). |

## 5. HR starter pack (assessment data)

| Field | Value |
|---|---|
| Files | `employee_lifecycle_events.csv` (2,407 rows), `retention_objectives.csv` (3 rows), `data_dictionary.csv`, `assessment_data_manifest.json` |
| Location | `data/raw/hr/2025-12-31/` (named after the as-of date, D-69); moved there from the delivered folder (D-65) |
| Integrity | SHA-256 of each file checked against the manifest on **every** run; a mismatch makes the source *unavailable* and stops the run |
| Status | always `replayed` (delivered once, never fetched, D-68) |
| Nature | synthetic and fictional; seed 20260831; intentionally imperfect (see the quality report and `docs/requirements_refinement.md`) |

---

## Licences and attribution

Checked on the providers' own pages on 2026-09-28 (not written from memory). Shown in the dashboard's Evidence
view (`/api/sources`) and the page footer.

| Provider | Licence / terms | Attribution used |
|---|---|---|
| Eurostat | Reuse permitted under Commission Decision 2011/833/EU (editorial content CC BY 4.0) · <https://ec.europa.eu/eurostat/help/copyright-notice> | "Source: Eurostat. Reuse requires acknowledging the source and indicating changes made." Changes: filtered to 6 countries and the dimensions above. |
| World Bank | Creative Commons Attribution 4.0 (CC BY 4.0) · <https://datacatalog.worldbank.org/public-licenses> | "Source: World Bank, World Development Indicators. Changes: filtered to 6 countries, 2019-2025." |
| HR pack | Provided for the assessment; all people, events and targets are fictional | "Asteria Consumer Products assessment data pack v1.0 (synthetic)." |

## Contracts: canonical mapping

Each indicator becomes rows of one canonical table, `data/curated/canonical/indicators.parquet`
(`service/indicator_curation.py`, schema in `domain/schemas.py`):

| Column | Meaning |
|---|---|
| `indicator`, `provider`, `dataset`, `lens` | what the value is and where it came from |
| `country_code` / `source_country_code` | canonical ISO alpha-2 / the provider's code, kept |
| `period`, `frequency`, `period_start`, `period_end` | the value's **own** period (`2024-04`, `2024-Q1`, `2022`) |
| `value`, `unit` | the number and its unit |
| `obs_status`, `obs_status_label` | provider status flag, e.g. `p` = provisional |
| `source_snapshot`, `loaded_at`, `source_last_updated` | lineage: raw folder, fetch time, provider update date |

**Country codes** (`config/mappings/country_codes.csv`): Eurostat `EL` → `GR`; World Bank `GRC, ROU, POL, ITA,
IRL, BGR` → `GR, RO, PL, IT, IE, BG`; HR `EL` → `GR`, `ROM` → `RO`. An unknown code stops the run with
"add a mapping row" instead of being guessed.

**Publication lag contract** (`config/settings.yaml`, D-29, D-58): a value is usable from
`last_day(period_end + lag)`, with monthly +2, quarterly +3, annual +7 months. These are conservative fixed
approximations measured from source availability, not exact historical release dates.

## Ingestion behaviour

| Mode | Behaviour | Status |
|---|---|---|
| `retention run` (default, offline) | uses the snapshot named in `latest.json`; no network | `replayed` |
| `retention run --refresh`, success | new dated snapshot folder (never overwrites); `latest.json` moves to it only after the whole run succeeded (D-96) | `fresh` |
| `--refresh`, fetch failed or unreadable body | timeouts + 3 retries with backoff (D-47); an HTTP 200 with a changed or broken structure counts as a failure (D-97); then the last good snapshot | `stale` (run continues, warning) |
| no snapshot at all | - | `unavailable` (run stops, previous outputs kept) |

## Known limitations of the sources

- **No vintages:** the APIs return today's **revised** values, not the values published at the time; the
  as-of join approximates "what was known then" (D-58).
- **Lags are fixed per frequency,** not exact per-release dates.
- **`prc_hicp_manr` is discontinued** (successor documented above); `jvs_q_nace2` may be frozen too.
- **Job vacancies are not seasonally adjusted** and include provisional values. The provisional flag is the
  status in today's API answer, not the status on each cohort's as-of date (no vintages).
- **Irish GDP** is not a local economic-cycle measure (handled as above).
- **The HR data is synthetic.** Inspecting how the brief's generator builds it shows retention depends on hire
  year, country, business unit, level and contract type, not on these indicators, so a non-finding is the
  expected, honest result (see `docs/methodology.md`).
