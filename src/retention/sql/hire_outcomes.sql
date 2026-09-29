-- hire_outcomes: one row per hire and hire-retention objective (the hire-level feature table, D-77).
--
-- Input view : employees  (canonical/employees.parquet)
-- Parameters : $report_start  first hire date that counts (2021-01-01, D-23)
--              $as_of         data as-of date (2025-12-31); windows ending after it are immature (D-18)
--              $senior_levels career levels that count as senior (settings.yaml, D-94)
--
-- Rules:
--   D-16  observation_date = hire_date + 6 (or 12) CALENDAR months.
--         DuckDB moves impossible dates to the month end: 2021-08-31 + 6 months = 2022-02-28.
--   D-17  a termination ON or BEFORE the observation date = not retained, whatever its type.
--   D-18  observation date after the as-of date = immature (no outcome yet, not in the rate).
--   D-14  SENIOR_HIRE_12M = the career levels in $senior_levels; today 'Senior Leader' only
--         (Sr Mgmt already mapped, D-13). D-94: a setting, so the business can change it.
--   D-73  INCLUDED rows are the primary population; QUARANTINED rows (unverified exits) are kept
--         here with their status, so the sensitivity variant can add them back (D-10).
--         EXCLUDED rows have no usable hire date (D-09) and never appear.

WITH hires AS (
    SELECT *
    FROM employees
    WHERE metric_status IN ('INCLUDED', 'QUARANTINED')
      AND hire_date >= $report_start
),

-- One row per hire and objective: every hire is a new hire; only the senior levels are senior hires.
hire_objectives AS (
    SELECT h.*, 'NEW_HIRE_6M' AS objective_id, CAST(6 AS BIGINT) AS window_months
    FROM hires h
    UNION ALL
    SELECT h.*, 'SENIOR_HIRE_12M' AS objective_id, CAST(12 AS BIGINT) AS window_months
    FROM hires h
    WHERE list_contains($senior_levels, h.career_level)
),

with_dates AS (
    SELECT *,
           CAST(hire_date + to_months(window_months) AS DATE) AS observation_date      -- D-16
    FROM hire_objectives
)

SELECT
    objective_id,
    employee_id,
    metric_status,
    country_code,
    business_unit,
    job_family,
    career_level,
    employment_type,
    hire_date,
    CAST(year(hire_date) AS VARCHAR)                                AS hire_year,
    year(hire_date) || '-Q' || quarter(hire_date)                   AS hire_quarter,    -- e.g. 2023-Q1
    window_months,
    observation_date,
    termination_date,
    CASE
        WHEN observation_date > $as_of                  THEN 'immature'                -- D-18
        WHEN termination_date IS NOT NULL
             AND termination_date <= observation_date   THEN 'not_retained'            -- D-17
        ELSE 'retained'
    END                                                             AS outcome,
    CASE
        WHEN observation_date <= $as_of
             AND termination_date IS NOT NULL
             AND termination_date <= observation_date   THEN termination_type          -- for the type breakdown
    END                                                             AS exit_type_in_window
FROM with_dates
ORDER BY objective_id, employee_id
