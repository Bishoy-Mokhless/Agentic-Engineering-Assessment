-- as_of_join: give every analysis unit the indicator values that were ALREADY PUBLISHED on its
-- as-of date (no future information, D-28..D-31, D-38).
--
-- Input views : analysis_units  one row per objective x country x period, with its anchor_date (as-of date)
--               indicators      canonical/indicators.parquet (one row per indicator x country x period)
-- Parameters  : $lag_monthly, $lag_quarterly, $lag_annual   publication lags in months (D-29, D-58)
--
-- Rules:
--   D-29/D-58  a value becomes usable at  available_from = last day of (period_end + lag months)
--              e.g. unemployment 2022-10 (ends 2022-10-31) + 2 months -> usable from 2022-12-31.
--              These are conservative fixed-lag approximations based on observed source availability,
--              not exact historical release dates; today's APIs return revised values (no vintages).
--   D-30       monthly indicator -> the latest single available month (not an average)
--   D-31       annual GDP is carried forward, but keeps its own period, frequency and age:
--              it is never presented as a new quarterly value.
--   ASOF JOIN  = for each unit, the indicator row with the LATEST available_from that is <= anchor_date.
--              ASOF LEFT JOIN keeps units with no value yet (value stays NULL, visible, not dropped).

WITH availability AS (
    SELECT
        i.*,
        CASE i.frequency
            WHEN 'monthly'   THEN $lag_monthly
            WHEN 'quarterly' THEN $lag_quarterly
            WHEN 'annual'    THEN $lag_annual
        END AS lag_months
    FROM indicators i
),

available AS (
    SELECT
        *,
        CAST(last_day(period_end + to_months(lag_months)) AS DATE) AS available_from
    FROM availability
),

-- Every unit needs one value per indicator.
unit_indicators AS (
    SELECT u.*, names.indicator
    FROM analysis_units u
    CROSS JOIN (SELECT DISTINCT indicator FROM indicators) AS names
)

SELECT
    u.objective_id,
    u.analysis_set,
    u.grain,
    u.country_code,
    u.period,
    u.anchor_date,
    u.outcome_rate,
    u.cohort_n,
    u.indicator,
    a.lens,
    a.value,
    a.unit,
    a.period                                           AS source_period,       -- e.g. 2021 for GDP (D-31)
    a.frequency                                        AS source_frequency,    -- e.g. annual
    a.available_from,
    date_diff('month', a.period_end, u.anchor_date)    AS age_months,          -- how old the value was
    a.obs_status,                                                              -- e.g. p = provisional
    a.source_snapshot
FROM unit_indicators u
ASOF LEFT JOIN available a
       ON  u.country_code = a.country_code
      AND  u.indicator    = a.indicator
      AND  u.anchor_date >= a.available_from
ORDER BY u.objective_id, u.analysis_set, u.indicator, u.country_code, u.anchor_date
