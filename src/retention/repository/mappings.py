"""Load the mapping tables in config/mappings (D-08, D-13)."""

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
