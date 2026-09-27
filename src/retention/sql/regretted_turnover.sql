-- regretted_turnover: trailing-twelve-month (TTM) regretted turnover per month-end (D-20, D-21).
--
-- Input view : employees  (canonical/employees.parquet)
-- Parameters : $report_start  first reported month (2021-01-01 -> first TTM value at 2021-01-31, D-23)
--              $as_of         last reported month-end (2025-12-31)
--
-- rate at month-end M = regretted exits in the 12 months ending M  /  average of 13 month-end headcounts
--   exits window    : termination_date in (month-end 12 months before M, M]          e.g. (2023-12-31, 2024-12-31]
--   13 headcounts   : that earlier month-end + the 12 month-ends of the window        (D-20)
--   headcount at D  : hire_date <= D  AND (no termination OR termination_date > D)    (D-20)
--
-- Variants:
--   primary                 INCLUDED employees; numerator = regretted_exit TRUE only           (D-12)
--   with_unverified_exits   + QUARANTINED employees in headcount and exits (their regretted
--                           value is UNKNOWN, so only the denominator changes)                (D-22)
--   unknown_as_regretted    INCLUDED employees; numerator = TRUE + UNKNOWN (worst case)        (D-12)
--
-- Scopes: 'company' (all countries incl. 'Unknown', D-08) and one row per country.

WITH variants AS (
    SELECT 'primary' AS variant
    UNION ALL SELECT 'with_unverified_exits'
    UNION ALL SELECT 'unknown_as_regretted'
),

population AS (
    SELECT v.variant, e.*
    FROM employees e
    CROSS JOIN variants v
    WHERE e.metric_status = 'INCLUDED'
       OR (v.variant = 'with_unverified_exits' AND e.metric_status = 'QUARANTINED')
),

scopes AS (
    SELECT 'ALL' AS country_code
    UNION ALL
    SELECT DISTINCT country_code FROM employees WHERE country_code <> 'Unknown'
),

-- Every month-end from 12 months before the first report month to the as-of date.
-- (the first TTM value needs the 12 earlier month-ends for its average headcount)
month_ends AS (
    SELECT last_day(CAST(month_start AS DATE)) AS month_end
    FROM range(CAST($report_start AS DATE) - INTERVAL 12 MONTH, CAST($as_of AS DATE) + INTERVAL 1 DAY,
               INTERVAL 1 MONTH) AS t(month_start)
),

grid AS (
    SELECT v.variant, s.country_code, m.month_end,
           last_day(m.month_end - INTERVAL 1 MONTH) AS previous_month_end   -- 2024-03-31 -> 2024-02-29
    FROM variants v CROSS JOIN scopes s CROSS JOIN month_ends m
),

-- Per month: headcount at the month-end and regretted exits during the month.
monthly AS (
    SELECT
        g.variant,
        g.country_code,
        g.month_end,
        count(p.employee_id) FILTER (
            WHERE p.hire_date <= g.month_end
              AND (p.termination_date IS NULL OR p.termination_date > g.month_end)
        ) AS headcount,
        count(p.employee_id) FILTER (
            WHERE p.termination_date > g.previous_month_end                -- exit during this month
              AND p.termination_date <= g.month_end
              AND (p.regretted_exit = 'TRUE'
                   OR (g.variant = 'unknown_as_regretted' AND p.regretted_exit = 'UNKNOWN'))
        ) AS regretted_exits_in_month,
        count(p.employee_id) FILTER (
            WHERE p.termination_date > g.previous_month_end
              AND p.termination_date <= g.month_end
              AND p.regretted_exit = 'UNKNOWN'
        ) AS unknown_regretted_in_month
    FROM grid g
    LEFT JOIN population p
           ON p.variant = g.variant
          AND (g.country_code = 'ALL' OR p.country_code = g.country_code)
    GROUP BY g.variant, g.country_code, g.month_end
),

-- Roll up 12 months of exits and 13 month-end headcounts (rows are consecutive months).
ttm AS (
    SELECT
        variant,
        country_code,
        month_end,
        CAST(sum(regretted_exits_in_month) OVER last_12_months AS BIGINT)   AS regretted_exits,
        CAST(sum(unknown_regretted_in_month) OVER last_12_months AS BIGINT) AS unknown_regretted_exits,
        avg(headcount) OVER last_13_month_ends                 AS avg_headcount,
        count(*) OVER last_13_month_ends                       AS headcount_points,
        headcount                                              AS headcount_at_month_end
    FROM monthly
    WINDOW
        last_12_months     AS (PARTITION BY variant, country_code ORDER BY month_end
                               ROWS BETWEEN 11 PRECEDING AND CURRENT ROW),
        last_13_month_ends AS (PARTITION BY variant, country_code ORDER BY month_end
                               ROWS BETWEEN 12 PRECEDING AND CURRENT ROW)
)

SELECT
    variant,
    CASE WHEN country_code = 'ALL' THEN 'company' ELSE 'country' END  AS scope,
    country_code,
    month_end,
    month(month_end) = 12                                             AS is_year_end,   -- D-37 test points
    regretted_exits,
    unknown_regretted_exits,
    avg_headcount,
    headcount_points,
    headcount_at_month_end
FROM ttm
WHERE month_end >= $report_start
ORDER BY variant, scope, country_code, month_end
