"""Regression tests for the exception hierarchy.

Pins two things:
- The whole family stays catchable via the TradingSystemError base (the actual
  contract callers rely on for blanket error handling).
- The exceptions removed during cleanup (RiskValidationError, TradeExecutionError,
  APIError — all had zero references) do not silently creep back. If a later
  phase adopts exception-based error signalling in the risk/execution/AI layers,
  re-add them deliberately and update this test.
"""

import pytest

import src.exceptions as exc

CONCRETE_ERRORS = [
    exc.DataCollectionError,
    exc.ValidationError,
    exc.AIAnalysisError,
    exc.DatabaseError,
    exc.ConfigurationError,
]


@pytest.mark.parametrize("error_cls", CONCRETE_ERRORS)
def test_errors_are_catchable_as_base(error_cls):
    with pytest.raises(exc.TradingSystemError):
        raise error_cls("boom")


def test_removed_dead_exceptions_stay_removed():
    for name in ("RiskValidationError", "TradeExecutionError", "APIError"):
        assert not hasattr(exc, name), (
            f"{name} had zero references and was removed; re-add it only if a "
            f"layer actually raises it."
        )
