"""Lineage records: _build.json per curated layer (D-62, D-74).

Each layer says which run built it, from which inputs (with checksums), and which files it
produced (rows + sha256). Following the inputs of analytical -> canonical -> raw traces any
number back to the exact provider response or delivered file.
"""

from __future__ import annotations

from datetime import datetime

from retention.repository.curated_repository import TableInfo


def build_record(
    layer: str, run_id: str, built_at: datetime, inputs: list[dict], tables: dict[str, TableInfo]
) -> dict:
    """_build.json: which run built this layer, from which raw inputs, producing which files (D-74)."""
    table_records = {}
    for name in sorted(tables):
        info = tables[name]
        table_records[name] = {"file": info.file, "rows": info.rows, "sha256": info.sha256}
    return {
        "layer": layer,
        "run_id": run_id,
        "built_at": built_at.isoformat(timespec="seconds"),
        "inputs": inputs,
        "tables": table_records,
    }


def table_inputs(layer: str, record: dict) -> list[dict]:
    """Turn another layer's _build.json into input entries, e.g. canonical/employees.parquet + sha256."""
    inputs = []
    for name in sorted(record["tables"]):
        table = record["tables"][name]
        inputs.append({"source": layer, "snapshot": f"{layer}/{table['file']}", "sha256": table["sha256"]})
    return inputs
