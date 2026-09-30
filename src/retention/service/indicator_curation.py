"""Source-shaped indicator rows -> one canonical long table for all indicators.

Canonical grain (the key): one row per (indicator, country_code, period).
Each row keeps what the brief asks for: source, indicator, unit, frequency, period,
load time and publication status, plus the raw snapshot it came from (lineage, D-74).

Example row:
    indicator=job_vacancy  country_code=BG  source_country_code=BG  period=2023-Q1  frequency=quarterly
    period_start=2023-01-01  period_end=2023-03-31  value=0.9  unit="% of jobs vacant"
    obs_status=p  obs_status_label=provisional  source_snapshot=eurostat/jvs_q_nace2/20260927T120053Z
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from retention.config import IndicatorSettings
from retention.domain.errors import CurationError
from retention.domain.periods import period_bounds

INDICATOR_COLUMNS = [
    "indicator",
    "provider",
    "dataset",
    "lens",
    "country_code",
    "source_country_code",
    "period",
    "frequency",
    "period_start",
    "period_end",
    "value",
    "unit",
    "obs_status",
    "obs_status_label",
    "source_snapshot",
    "loaded_at",
    "source_last_updated",
]

# Which source-shaped column holds the country, the period and the status, per provider.
PROVIDER_COLUMNS = {
    "eurostat": {"country": "geo", "period": "time", "status": "status", "status_label": "status_label"},
    "worldbank": {
        "country": "countryiso3code",
        "period": "date",
        "status": "obs_status",
        "status_label": None,
    },
}


@dataclass(frozen=True)
class SourceLineage:
    snapshot: str  # raw snapshot used, e.g. "eurostat/une_rt_m/20260927T120052Z"
    loaded_at: str | None  # when we fetched it (from metadata.json)
    source_last_updated: str | None  # when the provider last updated the dataset


@dataclass
class IndicatorCurationResult:
    rows: pd.DataFrame
    source_rows: int
    missing_values_dropped: int


def provider_last_updated(provider: str, data: dict | list) -> str | None:
    """The provider's own "last updated" stamp.

    Eurostat: data["updated"]   World Bank: data[0]["lastupdated"]
    """
    if provider == "eurostat":
        return data.get("updated")
    return data[0].get("lastupdated")


def curate_indicator(
    source: pd.DataFrame,
    name: str,
    indicator: IndicatorSettings,
    country_codes: dict[str, str],
    lineage: SourceLineage,
) -> IndicatorCurationResult:
    """Map one indicator's source-shaped rows onto the canonical columns.

    - country: provider code -> our code through country_codes.csv (EL -> GR, GRC -> GR)   D-08
    - period:  label kept, plus real start/end dates                                        D-31
    - value:   rows without a value are dropped here and counted (source-shaped keeps them)
    """
    columns = PROVIDER_COLUMNS[indicator.provider]
    rows = []
    missing = 0

    for record in source.to_dict("records"):
        # 1. Skip empty observations (e.g. a World Bank null), but count them for the coverage report.
        value = record["value"]
        if value is None or pd.isna(value):
            missing = missing + 1
            continue

        # 2. Country code: provider's code -> canonical code.
        source_code = record[columns["country"]]
        if source_code not in country_codes:
            raise CurationError(
                f"{name}: {indicator.provider} country code '{source_code}' has no row in "
                "config/mappings/country_codes.csv (D-08)"
            )

        # 3. Period label -> real dates; the label and frequency stay with the value (D-31).
        period = record[columns["period"]]
        start, end = period_bounds(period, indicator.frequency)

        # 4. Publication status exactly as the provider sent it (e.g. "p" = provisional).
        status = _text_or_none(record.get(columns["status"]))
        status_label = None
        if columns["status_label"]:
            status_label = _text_or_none(record.get(columns["status_label"]))

        rows.append(
            {
                "indicator": name,
                "provider": indicator.provider,
                "dataset": indicator.dataset,
                "lens": indicator.lens,
                "country_code": country_codes[source_code],
                "source_country_code": source_code,
                "period": period,
                "frequency": indicator.frequency,
                "period_start": start,
                "period_end": end,
                "value": float(value),
                "unit": indicator.unit,
                "obs_status": status,
                "obs_status_label": status_label,
                "source_snapshot": lineage.snapshot,
                "loaded_at": lineage.loaded_at,
                "source_last_updated": lineage.source_last_updated,
            }
        )

    table = pd.DataFrame(rows, columns=INDICATOR_COLUMNS)
    return IndicatorCurationResult(rows=table, source_rows=len(source), missing_values_dropped=missing)


def combine_indicators(tables: list[pd.DataFrame]) -> pd.DataFrame:
    """Stack all indicators into one table, sorted by its key so reruns give identical files."""
    combined = pd.concat(tables, ignore_index=True)
    combined = combined.sort_values(["indicator", "country_code", "period_start"]).reset_index(drop=True)
    for column in ["obs_status", "obs_status_label", "loaded_at", "source_last_updated"]:
        combined[column] = combined[column].astype("string")
    return combined


def _text_or_none(value: object) -> str | None:
    """Missing / NA / "" -> None; anything else -> text."""
    if value is None or pd.isna(value) or value == "":
        return None
    return str(value)
