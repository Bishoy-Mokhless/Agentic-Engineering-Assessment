"""Typed application settings loaded from config/settings.yaml.

Spring analogy: a @ConfigurationProperties class bound from application.yml.
Pydantic validates the file when it is loaded, so a typo in the YAML fails at startup
with a clear message instead of later in the pipeline.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SETTINGS_FILE = PROJECT_ROOT / "config" / "settings.yaml"

Frequency = Literal["monthly", "quarterly", "annual"]
Provider = Literal["eurostat", "worldbank"]


class PathSettings(BaseModel):
    raw: Path
    source_shaped: Path  # D-71
    canonical: Path
    analytical: Path
    hr_source: Path
    mappings: Path
    build_tmp: Path  # D-48: temporary build folder


class HttpSettings(BaseModel):
    """D-47: timeouts and retry with exponential backoff for external APIs."""

    timeout_seconds: float
    retries: int
    backoff_factor: float


class IndicatorSettings(BaseModel):
    """One external indicator (D-24..D-27)."""

    provider: Provider
    dataset: str
    frequency: Frequency
    lens: str
    unit: str
    since: str
    filters: dict[str, str] = {}
    exclude_from_analysis: list[str] = []


class ObjectiveAnalysis(BaseModel):
    role: Literal["primary", "secondary"]  # D-35
    grain: Literal["country_hire_quarter", "country_hire_year", "country_year_end_ttm"]


class AnalysisSettings(BaseModel):
    bootstrap_iterations: int  # D-33
    random_seed: int  # D-48: deterministic reruns
    alpha: float  # D-34
    formal_view: Literal["within_country"]  # D-54: only this view enters Holm families
    descriptive_views: list[Literal["pooled"]]  # D-54: context only
    objectives: dict[str, ObjectiveAnalysis]


class Settings(BaseModel):
    as_of_date: date
    countries: list[str]
    paths: PathSettings
    http: HttpSettings
    publication_lag_months: dict[Frequency, int]  # D-29
    providers: dict[Provider, str]
    indicators: dict[str, IndicatorSettings]
    analysis: AnalysisSettings


def load_settings(path: Path | None = None) -> Settings:
    """Read config/settings.yaml and return a validated Settings object.

    Raises a clear error at startup if a setting is missing or has the wrong type.
    """
    # 1. Read the YAML file into plain Python dicts and lists.
    if path is None:
        path = DEFAULT_SETTINGS_FILE
    with open(path, encoding="utf-8") as file:
        data = yaml.safe_load(file)

    # 2. Paths in the YAML are relative ("data/raw"); make them absolute from the project root.
    absolute_paths = {}
    for name, relative_path in data["paths"].items():
        absolute_paths[name] = PROJECT_ROOT / relative_path
    data["paths"] = absolute_paths

    # 3. Validate and convert into typed objects (like binding @ConfigurationProperties).
    return Settings.model_validate(data)
