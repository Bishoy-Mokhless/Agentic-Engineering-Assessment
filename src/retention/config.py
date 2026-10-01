"""Typed application settings loaded from config/settings.yaml.

Pydantic validates the file when it is loaded, so a typo in the YAML fails at startup
with a clear message instead of later in the pipeline: unknown keys are rejected and numbers
must be in range (D-99).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SETTINGS_FILE = PROJECT_ROOT / "config" / "settings.yaml"

Frequency = Literal["monthly", "quarterly", "annual"]
Provider = Literal["eurostat", "worldbank"]
Probability = Annotated[float, Field(gt=0, lt=1)]


class StrictModel(BaseModel):
    """Every settings block rejects unknown keys, so a misspelled setting is an error, not ignored."""

    model_config = ConfigDict(extra="forbid")


class PathSettings(StrictModel):
    raw: Path
    source_shaped: Path  # D-71
    canonical: Path
    analytical: Path
    hr_source: Path
    mappings: Path
    build_tmp: Path  # D-48: temporary build folder


class HttpSettings(StrictModel):
    """D-47: timeouts and retry with exponential backoff for external APIs."""

    timeout_seconds: float = Field(gt=0)
    retries: int = Field(ge=0)
    backoff_factor: float = Field(ge=0)


class IndicatorSettings(StrictModel):
    """One external indicator (D-24..D-27)."""

    provider: Provider
    dataset: str
    frequency: Frequency
    lens: str
    unit: str
    since: str
    filters: dict[str, str] = {}
    exclude_from_analysis: list[str] = []


class ProviderTerms(StrictModel):
    """Licence and attribution shown in the Trust view (brief: source attribution)."""

    name: str
    licence: str
    terms_url: str
    attribution: str


class MetricsSettings(StrictModel):
    report_start: date  # D-23
    confidence_level: Probability  # D-33
    small_sample_below: int = Field(ge=1)  # D-78
    senior_levels: list[str] = Field(min_length=1)  # D-14, D-94: career levels that count as senior hires


class ObjectiveAnalysis(StrictModel):
    role: Literal["primary", "secondary"]  # D-35
    grain: Literal["country_hire_quarter", "country_hire_year", "country_year_end_ttm"]


class AnalysisSettings(StrictModel):
    bootstrap_iterations: int = Field(ge=1)  # D-33
    random_seed: int  # D-48: deterministic reruns
    alpha: Probability  # D-34
    formal_view: Literal["within_country"]  # D-54: only this view enters Holm families
    descriptive_views: list[Literal["pooled", "time_adjusted"]]  # D-54, D-79: context only
    objectives: dict[str, ObjectiveAnalysis]


class Settings(StrictModel):
    as_of_date: date
    countries: list[str]
    paths: PathSettings
    http: HttpSettings
    publication_lag_months: dict[Frequency, Annotated[int, Field(ge=0)]]  # D-29
    providers: dict[Provider, str]
    provider_terms: dict[str, ProviderTerms]
    indicators: dict[str, IndicatorSettings]
    metrics: MetricsSettings
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

    # 3. Validate and convert into typed objects.
    return Settings.model_validate(data)
