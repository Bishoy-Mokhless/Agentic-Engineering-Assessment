"""Errors that stop a pipeline run with a clear message.

Spring analogy: custom RuntimeExceptions that a @ControllerAdvice would turn into a clean error.
The job catches PipelineError, logs the message, keeps the previous curated outputs, and exits with 1.
"""

from __future__ import annotations


class PipelineError(Exception):
    """Base class: a problem a person must fix (bad input, broken contract)."""


class CurationError(PipelineError):
    """Input data breaks a business-rule assumption, e.g. a country code with no mapping row."""


class ContractError(PipelineError):
    """A table does not match its schema contract (D-46, D-61)."""
