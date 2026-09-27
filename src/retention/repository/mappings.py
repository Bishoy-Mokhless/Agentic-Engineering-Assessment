"""Load the mapping tables in config/mappings (D-08, D-13).

The tables are plain CSV files so anyone can see (and review in git) exactly which codes are changed.
"""

from __future__ import annotations

import csv
from pathlib import Path


def source_country_codes(mappings_dir: Path, source: str, countries: list[str]) -> list[str]:
    """Translate our country codes into one provider's codes.

    Example: source="eurostat", countries=["GR", "RO"]  ->  ["EL", "RO"]
    """
    # 1. Read the mapping table and keep only the rows for this provider.
    #    Build a lookup: our code -> provider's code, e.g. {"GR": "EL", "RO": "RO", ...}
    lookup = {}
    with open(mappings_dir / "country_codes.csv", encoding="utf-8") as file:
        # Each row is a dict, e.g. {"source": "eurostat", "source_code": "EL", "canonical_code": "GR"}
        for row in csv.DictReader(file):
            if row["source"] == source:
                lookup[row["canonical_code"]] = row["source_code"]

    # 2. Translate each of our countries, failing clearly if one has no mapping.
    result = []
    for country in countries:
        if country not in lookup:
            raise ValueError(f"No {source} code mapped for country {country} in country_codes.csv")
        result.append(lookup[country])
    return result


def country_lookup(mappings_dir: Path, source: str) -> dict[str, str]:
    """The other direction: a provider's code -> our canonical code.

    Example: source="eurostat"  ->  {"EL": "GR", "RO": "RO", ...}
             source="hr"        ->  {"GR": "GR", "EL": "GR", "ROM": "RO", ...}
    """
    lookup = {}
    with open(mappings_dir / "country_codes.csv", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            if row["source"] == source:
                lookup[row["source_code"]] = row["canonical_code"]
    return lookup


def career_level_lookup(mappings_dir: Path) -> dict[str, str]:
    """Reported career-level label -> canonical label (D-13).

    Example: {"Manager": "Manager", "Sr Mgmt": "Senior Leader", ...}
    """
    lookup = {}
    with open(mappings_dir / "career_levels.csv", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            lookup[row["source_label"]] = row["canonical_label"]
    return lookup
