"""Provider payloads -> source-shaped tables (D-71): one row per observation, provider's own codes.

Spring analogy: a response mapper that turns an external API's JSON into flat DTOs,
without translating anything yet (translation happens in indicator_curation).
"""

from __future__ import annotations

import pandas as pd

from retention.domain.errors import CurationError

# ---------------------------------------------------------------------------------------------
# Eurostat (JSON-stat)
# ---------------------------------------------------------------------------------------------


def flatten_eurostat(data: dict) -> pd.DataFrame:
    """Turn a JSON-stat payload into one row per value.

    JSON-stat stores the table as one flat list of values. Each value's position encodes all
    its dimensions, like the digits of a number (the LAST dimension changes fastest).
    Example with id = [geo, time], size = [2, 3]:
        position 4  ->  geo index = 4 // 3 = 1, time index = 4 % 3 = 1  ->  (geo[1], time[1])

    Output row example (job vacancy):
        {"freq": "Q", "s_adj": "NSA", ..., "geo": "EL", "time": "2023-Q1", "value": 1.5, "status": None}
    """
    dimension_names = data["id"]
    dimension_sizes = data["size"]

    # 1. For each dimension, a list of its codes in position order, e.g. geo -> ["BG", "IE", "EL", ...]
    codes_by_dimension = []
    for name in dimension_names:
        index = data["dimension"][name]["category"]["index"]  # {"BG": 0, "IE": 1, ...}
        codes = [None] * len(index)
        for code, position in index.items():
            codes[position] = code
        codes_by_dimension.append(codes)

    # 2. Values and status flags may arrive as a dict {"position": x} or as a plain list.
    values = _as_position_dict(data.get("value"))
    statuses = _as_position_dict(data.get("status"))
    status_labels = data.get("extension", {}).get("status", {}).get("label", {})  # {"p": "provisional"}

    # 3. Decode each position into its dimension codes.
    rows = []
    for key in sorted(values, key=int):
        remainder = int(key)
        row = {}
        for dim in reversed(range(len(dimension_names))):
            size = dimension_sizes[dim]
            row[dimension_names[dim]] = codes_by_dimension[dim][remainder % size]
            remainder = remainder // size
        row["value"] = float(values[key])
        row["status"] = statuses.get(key)
        row["status_label"] = status_labels.get(row["status"]) if row["status"] else None
        rows.append(row)

    # Keep the dimension columns in the provider's order, then value and status.
    columns = list(dimension_names) + ["value", "status", "status_label"]
    table = pd.DataFrame(rows, columns=columns)
    table["status"] = table["status"].astype("string")
    table["status_label"] = table["status_label"].astype("string")
    return table


def _as_position_dict(raw: dict | list | None) -> dict[str, object]:
    """{"0": 5.7, "1": 5.6} stays as is; [5.7, None, 5.6] -> {"0": 5.7, "2": 5.6}."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    result = {}
    for position, value in enumerate(raw):
        if value is not None:
            result[str(position)] = value
    return result


# ---------------------------------------------------------------------------------------------
# World Bank
# ---------------------------------------------------------------------------------------------


def flatten_worldbank(data: list) -> pd.DataFrame:
    """Turn [metadata, observations] into one row per observation.

    Output row example:
        {"indicator_id": "NY.GDP.MKTP.KD.ZG", "countryiso3code": "GRC", "date": "2021",
         "value": 8.7, "unit": None, "obs_status": None}
    Empty strings from the API ("unit": "", "obs_status": "") become None.
    A null value is kept here (source-shaped is faithful); curation decides what to do with it.
    """
    if not isinstance(data, list) or len(data) != 2:
        raise CurationError("World Bank payload is not [metadata, observations]")

    rows = []
    for observation in data[1]:
        value = observation.get("value")
        rows.append(
            {
                "indicator_id": observation["indicator"]["id"],
                "country_id": observation["country"]["id"],
                "countryiso3code": observation["countryiso3code"],
                "date": observation["date"],
                "value": None if value is None else float(value),
                "unit": observation.get("unit") or None,
                "obs_status": observation.get("obs_status") or None,
            }
        )

    columns = ["indicator_id", "country_id", "countryiso3code", "date", "value", "unit", "obs_status"]
    table = pd.DataFrame(rows, columns=columns)
    table = table.sort_values(["countryiso3code", "date"]).reset_index(drop=True)
    table["value"] = table["value"].astype(float)
    table["unit"] = table["unit"].astype("string")
    table["obs_status"] = table["obs_status"].astype("string")
    return table
