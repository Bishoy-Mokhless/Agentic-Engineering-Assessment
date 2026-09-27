-- retention_cohorts: hire-retention counts per objective, variant, scope and period.
--
-- Input view : hire_outcomes  (output of hire_outcomes.sql, possibly pre-filtered by the API, D-77)
-- Output     : counts only. Rates, Wilson CIs, targets and status are added in Python (service/metrics.py).
--
-- Variants (D-10, D-73):
--   primary                 INCLUDED hires only
--   with_unverified_exits   INCLUDED + QUARANTINED hires (unverified 90-day exits treated as valid exits)
--
-- Periods (D-19, D-36, D-76): every hire is counted once per grain:
--   quarter  '2023-Q1'    (trend only, no verdict)
--   year     '2023'       (verdict)
--   period   '2021-2025'  (verdict: the objective's effective period)
--
-- Scopes (D-08): 'company' = all hires, including the 'Unknown' country;
--                'country' = one row per country; 'Unknown' is dropped there (it cannot be a country view).

WITH variants AS (
    SELECT 'primary' AS variant
    UNION ALL
    SELECT 'with_unverified_exits'
),

population AS (
    SELECT v.variant, h.*
    FROM hire_outcomes h
    CROSS JOIN variants v
    WHERE h.metric_status = 'INCLUDED'
       OR v.variant = 'with_unverified_exits'
),

-- Each hire appears once per grain, with the period label for that grain.
by_grain AS (
    SELECT p.*, 'quarter' AS grain, hire_quarter AS period FROM population p
    UNION ALL
    SELECT p.*, 'year' AS grain, hire_year AS period FROM population p
    UNION ALL
    SELECT p.*, 'period' AS grain, $period_label AS period FROM population p
),

counted AS (
    SELECT
        objective_id,
        variant,
        grain,
        period,
        CASE WHEN GROUPING(country_code) = 1 THEN 'company' ELSE 'country' END  AS scope,
        CASE WHEN GROUPING(country_code) = 1 THEN 'ALL' ELSE country_code END    AS country_code,
        count(*) FILTER (WHERE outcome IN ('retained', 'not_retained'))          AS n,        -- mature hires
        count(*) FILTER (WHERE outcome = 'retained')                              AS retained,
        count(*) FILTER (WHERE outcome = 'immature')                              AS immature_hires,   -- D-18
        -- Why people were not retained (D-17 dashboard breakdown)
        count(*) FILTER (WHERE exit_type_in_window = 'Voluntary')                 AS exits_voluntary,
        count(*) FILTER (WHERE exit_type_in_window = 'Involuntary')               AS exits_involuntary,
        count(*) FILTER (WHERE exit_type_in_window = 'End of Contract')           AS exits_end_of_contract,
        count(*) FILTER (WHERE exit_type_in_window = 'Unknown')                   AS exits_unknown_type
    FROM by_grain
    GROUP BY GROUPING SETS (
        (objective_id, variant, grain, period),                 -- company
        (objective_id, variant, grain, period, country_code)    -- per country
    )
)

SELECT *
FROM counted
WHERE country_code <> 'Unknown'
ORDER BY objective_id, variant, grain, scope, country_code, period
