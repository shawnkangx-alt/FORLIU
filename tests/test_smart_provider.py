from datetime import date

from code.data.mock_provider import MockDataProvider
from code.data.smart_provider import SmartProvider


class TestSmartProvider:

    def setup_method(self):
        self.provider = SmartProvider([MockDataProvider(seed=42)])

    def test_list_stocks(self):
        stocks = self.provider.list_stocks()
        assert len(stocks) == 50

    def test_get_daily_quotes(self):
        quotes = self.provider.get_daily_quotes("600519", date(2025, 6, 1), date(2025, 6, 10))
        assert len(quotes) > 0
        assert all(q.stock_code == "600519" for q in quotes)

    def test_get_financials(self):
        fin = self.provider.get_financials("600519")
        assert fin.stock_code == "600519"
        assert fin.pe > 0

    def test_batch_quotes(self):
        result = self.provider.get_batch_quotes(
            ["600519", "000858"], date(2025, 6, 1), date(2025, 6, 10)
        )
        assert len(result) == 2

    def test_batch_financials(self):
        result = self.provider.get_batch_financials(["600519", "000858"])
        assert len(result) == 2

    def test_active_source(self):
        self.provider.list_stocks()
        sources = self.provider.active_source
        assert sources["stocks"] == "MockDataProvider"

    def test_fallback_on_error(self):
        class FailingProvider(MockDataProvider):
            def list_stocks(self):
                raise RuntimeError("模拟失败")

        provider = SmartProvider([FailingProvider(seed=42), MockDataProvider(seed=99)])
        stocks = provider.list_stocks()
        assert len(stocks) == 50  # Falls back to second provider

    def test_empty_providers_raises(self):
        import pytest
        with pytest.raises(ValueError, match="至少需要一个数据源"):
            SmartProvider([])

    def test_all_fail_returns_empty(self):
        class AlwaysFails(MockDataProvider):
            def list_stocks(self):
                raise RuntimeError("fail")

        provider = SmartProvider([AlwaysFails(seed=1)])
        assert provider.list_stocks() == []

    def test_all_fail_financials_returns_zeroed(self):
        class AlwaysFails(MockDataProvider):
            def get_financials(self, code):
                raise RuntimeError("fail")

        provider = SmartProvider([AlwaysFails(seed=1)])
        fin = provider.get_financials("600519")
        assert fin.pe == 0
        assert fin.stock_code == "600519"
