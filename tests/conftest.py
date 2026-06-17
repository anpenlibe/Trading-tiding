"""Shared pytest fixtures and path setup.

Adds the repo root to sys.path so `import src...` works when running pytest
from anywhere, mirroring how the apps/ entry points bootstrap themselves.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def fresh_trader():
    """A PaperTrader with a known starting capital."""
    from src.core.paper_trader import PaperTrader
    return PaperTrader(initial_capital=10000)


@pytest.fixture
def risk_manager():
    from src.core.risk_manager import SimpleRiskManager
    return SimpleRiskManager()
