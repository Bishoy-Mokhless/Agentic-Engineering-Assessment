"""Small statistics helpers for rates (D-33, D-75)."""

from __future__ import annotations

import math
from functools import cache

from scipy.stats import norm


@cache  # pure function, called once per row: scipy's ppf is slow (D-92 made it visible)
def z_value(confidence_level: float) -> float:
    """0.95 -> 1.96 (the number of standard errors on each side of a two-sided interval)."""
    return float(norm.ppf(1 - (1 - confidence_level) / 2))


def wilson_interval(successes: float, n: float, confidence_level: float = 0.95) -> tuple[float, float] | None:
    """Wilson score interval for a proportion successes / n (D-33).

    Stays inside 0..1 and behaves well for small n and rates near 0% or 100%,
    where the textbook "p +/- 1.96 * standard error" breaks down.

    Examples:
        wilson_interval(12, 16) -> (0.505, 0.898)    (75% of 16 people)
        wilson_interval(1, 1)   -> (0.207, 1.0)      (one person: very wide)
        wilson_interval(0, 0)   -> None              (no one to measure)

    For turnover, n is the average headcount (not a whole number); the formula still works,
    and the result is labelled an approximation (events over average headcount).
    """
    if n <= 0:
        return None
    z = z_value(confidence_level)
    p = successes / n
    z2 = z * z

    # centre and half-width of the interval
    denominator = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denominator
    half_width = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denominator

    low = max(0.0, centre - half_width)
    high = min(1.0, centre + half_width)
    return low, high


def objective_status(ci_low: float, ci_high: float, target: float, direction: str) -> str:
    """D-75: a verdict only when the whole confidence interval is on one side of the target.

    direction "at_least" (retention >= target):
        met           if ci_low  >= target        e.g. [0.88, 0.93] vs 0.86
        not_met       if ci_high <  target        e.g. [0.73, 0.83] vs 0.90
        inconclusive  otherwise                   e.g. [0.51, 0.90] vs 0.86
    direction "at_most" (turnover <= target): the mirror image.
    """
    if direction == "at_least":
        if ci_low >= target:
            return "met"
        if ci_high < target:
            return "not_met"
        return "inconclusive"

    if direction == "at_most":
        if ci_high <= target:
            return "met"
        if ci_low > target:
            return "not_met"
        return "inconclusive"

    raise ValueError(f"unknown objective direction '{direction}' (expected at_least or at_most)")
