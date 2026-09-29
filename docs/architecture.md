# Production architecture view

How this local, laptop-sized solution would map to an Azure Data Factory (ADF) + Databricks lakehouse +
Power BI setup. The local design was built to make this mapping direct: the same layers, the same rules, the
same SQL. This is a design view; nothing here is deployed.

## 1. Local → production mapping

| Concern | Local (this repo) | Production |
|---|---|---|
| Orchestration | `retention run` → `pipeline/job.py` runs ingest → curate → metrics → analyse | **ADF pipeline** (or Databricks Workflows) calling one Databricks job task per step, with dependencies and retries |
| Ingestion | `client/` adapters (Eurostat, World Bank, HR files), timeouts + retries, status per source | ADF **Copy activity** (REST connector) or a Databricks notebook running the same adapter code; HR extract dropped by the HR system into a landing container |
| Raw layer | `data/raw/<provider>/<dataset>/<fetch-time>/payload.json` + `metadata.json` + `latest.json` | **ADLS Gen2 `landing/`** container, immutable, same folder convention; ingestion metadata in a control table |
| Source-shaped | `data/curated/source_shaped/*.parquet` | **Bronze** Delta tables (provider shape, append-only, `_snapshot` column) |
| Canonical | `data/curated/canonical/*.parquet` (+ quality flags, `quality_issues`) | **Silver** Delta tables with schema enforcement; quality flags as columns; issues table |
| Analytical | `data/curated/analytical/*.parquet` | **Gold** Delta tables (`retention_cohorts`, `regretted_turnover`, `hire_outcomes`, `aligned_observations`, `association_results`) |
| SQL | DuckDB running `sql/*.sql` on Parquet | the same SQL on **Databricks SQL / Spark SQL** (the queries use standard CTEs, window functions and `GROUPING SETS`; the `ASOF JOIN` becomes a window/range join) |
| Schema contracts | Pandera checks before each write (`domain/schemas.py`) | Delta schema enforcement + expectations (e.g. **Delta Live Tables expectations** or Great Expectations) with the same rules |
| All-or-nothing publish | build in `data/.tmp/<run_id>/`, swap only if every step succeeds | write Gold in one transaction per table, or build into staging tables and swap / `RESTORE` on failure (Delta time travel) |
| Lineage | `_build.json` per layer (run id, inputs, outputs, SHA-256) | **Unity Catalog lineage** + a run-audit table with the same fields |
| Serving | FastAPI (`api/`) reading Parquet | **Power BI** on the Gold tables (Direct Lake / import); the API remains optional for other consumers |
| Dashboard | HTML + Chart.js (`dashboard/`) | **Power BI report** with the same views: Overview, Objective detail, Market signals, Relationships, Evidence |

## 2. Diagram

```text
  Eurostat API ─┐       ┌──────────── Azure Data Factory (schedule + orchestration) ─────────────┐
  World Bank API┼──────>│ 1 ingest     2 curate          3 metrics          4 analyse             │
  HR system ────┘       │ (copy/REST)  (Databricks job)  (Databricks SQL)   (Databricks job)       │
                        └────┬─────────────┬──────────────────┬───────────────────┬───────────────┘
                             v             v                  v                   v
  ADLS Gen2 + Unity Catalog: landing/ ──> bronze ──────────> silver ──────────> gold
                             (immutable)   (source-shaped)    (canonical,         (objectives, joins,
                                                               flags, issues)      tests, audit)
                                                                                    │
                                                         Power BI semantic model <──┘
                                                         (RLS by country/role) ──> Power BI report
  Key Vault (secrets) · Log Analytics / Azure Monitor (logs, alerts) · Git + CI/CD (dev → test → prod)
```

## 3. Secrets

- Today there are **no secrets**: both APIs are public and the HR pack is a file.
- Production: the HR extract's credentials and any API keys live in **Azure Key Vault**; ADF linked services
  and Databricks secret scopes read them at run time. Nothing in code, config files or Git. Access is through
  **managed identities**, not personal accounts.

## 4. Scheduling

| Source | Cadence | Schedule |
|---|---|---|
| HR extract | daily or monthly snapshot | after the HR system's export (event trigger on the landing container) |
| Eurostat monthly (unemployment, HICP) | monthly, ~1–2 months lag | weekly refresh; picks up new months as they appear |
| Eurostat quarterly (job vacancies) | quarterly, ~3 months lag | weekly refresh |
| World Bank GDP | a few updates per year | monthly refresh |

Reruns are idempotent (the same inputs give identical outputs; raw is never overwritten), so a failed or
repeated run is safe. The local `--offline` mode becomes "reprocess from existing landing snapshots" for
backfills.

## 5. Observability

- **Run audit table** (today `run_summary.json`): run id, mode, outcome, step row counts, each source's status
  (fresh / replayed / stale / unavailable) and error.
- **Logs** from ADF and Databricks into **Log Analytics**; **alerts** on: a failed run, a source *stale* for
  longer than its expected cadence, a quality-flag count jumping (e.g. new unmapped country codes, which stop
  the run by design), a schema change from a provider (e.g. the discontinued HICP dataset).
- **Data freshness** shown to users, as the dashboard's Evidence view and health badge do today.

## 6. Storage

- **ADLS Gen2** with containers `landing`, `bronze`, `silver`, `gold`; Delta format from bronze on.
- **Raw is immutable** (the local rule "never overwrite a snapshot" becomes write-once / immutability policies
  on `landing`); retention of raw snapshots per the data-retention policy.
- **Time travel** on Delta tables replaces the local temp-folder swap for rollback.
- Partitioning is not needed at this size (a few thousand rows); at scale, partition bronze by source and fetch
  date, and silver HR by snapshot date.

## 7. Access control

- **Unity Catalog** permissions per layer: engineers write bronze/silver/gold through the pipeline identity
  only; analysts read gold; raw HR data restricted to the data team.
- **Personal data:** real employee records are personal data. In production, silver would hold pseudonymised
  employee ids; gold holds aggregates only.
- **Small-group suppression:** groups under 5 people would be hidden (today only a warning under 10, because the
  data is synthetic, D-78).
- **Power BI row-level security** by country or business unit for HR partners.

## 8. Promotion between environments

- Code (Python, SQL, notebooks), ADF pipelines (ARM/Bicep or ADF Git integration), Databricks jobs (Asset
  Bundles) and Power BI reports (deployment pipelines) all in **Git**.
- **dev → test → prod** with separate workspaces, storage accounts and Key Vaults; the same code, different
  configuration (today `config/settings.yaml` becomes one config per environment).
- **CI on every change:** lint (`ruff`), unit and API tests on replay fixtures (never live APIs, as locally),
  schema checks; the browser tests run against the test environment. Promotion to prod only after test passes
  and an approval.
- **Test environment runs on the committed replay snapshots**, so results can be compared byte-for-byte with the
  previous release before promoting.

## 9. What would change, and what stays

- **Stays the same:** the layer boundaries, the cleaning rules, the metric SQL, the as-of rule with publication
  lags, the statistics, the quality flags and the status vocabulary. They are all independent of where they run.
- **Changes:** DuckDB → Spark SQL, Parquet folders → Delta tables, the temp-folder publish → Delta
  transactions, FastAPI + HTML → Power BI (FastAPI optional), `run_summary.json` → an audit table.
- **At scale:** the HR table grows to many snapshots; incremental (per snapshot date) processing in silver and
  gold replaces the full rebuild used today (a full rebuild is fine at a few thousand rows).
