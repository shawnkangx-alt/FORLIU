import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code"))

import pytest
from datetime import date

from code.data.mock_provider import MockDataProvider


@pytest.fixture
def provider():
    return MockDataProvider(seed=42)


@pytest.fixture
def stocks(provider):
    return provider.list_stocks()


@pytest.fixture
def sample_quotes(provider):
    return provider.get_daily_quotes("600519", date(2025, 1, 1), date(2025, 12, 31))


@pytest.fixture
def sample_financials(provider):
    return provider.get_financials("600519")
