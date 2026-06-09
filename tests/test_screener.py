import pytest

from code.data.mock_provider import MockDataProvider
from code.screening.screener import Screener


class TestScreener:

    def setup_method(self):
        self.provider = MockDataProvider(seed=42)
        self.screener = Screener(self.provider)

    def test_list_presets(self):
        presets = self.screener.list_presets()
        assert "value" in presets
        assert "growth" in presets
        assert "momentum" in presets
        assert "bollinger_breakout" in presets
        assert "comprehensive" in presets
        assert len(presets) == 5

    def test_screen_preset_value(self):
        results = self.screener.screen_preset("value", top_n=10)
        assert len(results) <= 10
        for r in results:
            assert r.score >= 50

    def test_screen_preset_growth(self):
        results = self.screener.screen_preset("growth", top_n=10)
        assert len(results) <= 10

    def test_screen_preset_momentum(self):
        results = self.screener.screen_preset("momentum", top_n=10)
        assert len(results) <= 10

    def test_screen_preset_comprehensive(self):
        results = self.screener.screen_preset("comprehensive", top_n=10)
        assert len(results) <= 10

    def test_unknown_preset_raises(self):
        with pytest.raises(ValueError, match="未知预设策略"):
            self.screener.screen_preset("nonexistent")

    def test_results_have_stocks(self):
        results = self.screener.screen_preset("value", top_n=5)
        for r in results:
            assert r.stock.code
            assert r.stock.name
            assert 0 <= r.score <= 100
            assert len(r.matched_rules) > 0
