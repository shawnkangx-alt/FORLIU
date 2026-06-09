from datetime import date

from code.data.mock_provider import MockDataProvider


class TestMockDataProvider:
    def test_list_stocks(self, provider):
        stocks = provider.list_stocks()
        assert len(stocks) == 50
        codes = {s.code for s in stocks}
        assert "600519" in codes
        assert "000858" in codes

    def test_seeded_reproducibility(self):
        p1 = MockDataProvider(seed=42)
        p2 = MockDataProvider(seed=42)
        q1 = p1.get_daily_quotes("600519", date(2025, 1, 1), date(2025, 1, 31))
        q2 = p2.get_daily_quotes("600519", date(2025, 1, 1), date(2025, 1, 31))
        for a, b in zip(q1, q2):
            assert a.close == b.close
            assert a.volume == b.volume

    def test_different_seeds_different_data(self):
        p1 = MockDataProvider(seed=42)
        p2 = MockDataProvider(seed=99)
        q1 = p1.get_daily_quotes("000858", date(2025, 1, 1), date(2025, 1, 10))
        q2 = p2.get_daily_quotes("000858", date(2025, 1, 1), date(2025, 1, 10))
        closes1 = [q.close for q in q1]
        closes2 = [q.close for q in q2]
        assert closes1 != closes2

    def test_same_stock_same_data(self):
        p = MockDataProvider(seed=42)
        q1 = p.get_daily_quotes("600519", date(2025, 6, 1), date(2025, 6, 10))
        q2 = p.get_daily_quotes("600519", date(2025, 6, 1), date(2025, 6, 10))
        assert len(q1) == len(q2)
        for a, b in zip(q1, q2):
            assert a.close == b.close

    def test_skips_weekends(self, sample_quotes):
        for q in sample_quotes:
            assert q.date.weekday() < 5

    def test_quotes_have_ohlcv(self, sample_quotes):
        assert len(sample_quotes) > 0
        for q in sample_quotes:
            assert q.high >= q.low
            assert q.high >= q.open
            assert q.high >= q.close
            assert q.low <= q.open
            assert q.low <= q.close
            assert q.volume >= 0
            assert q.amount > 0

    def test_unknown_stock_returns_empty(self, provider):
        quotes = provider.get_daily_quotes("999999", date(2025, 1, 1), date(2025, 1, 31))
        assert quotes == []

    def test_get_financials(self, sample_financials):
        assert sample_financials.stock_code == "600519"
        assert sample_financials.pe > 0
        assert sample_financials.pb > 0
        assert sample_financials.roe > 0
        assert isinstance(sample_financials.revenue_yoy, float)

    def test_batch_quotes(self, provider):
        stocks = provider.list_stocks()[:5]
        codes = [s.code for s in stocks]
        result = provider.get_batch_quotes(codes, date(2025, 6, 1), date(2025, 6, 10))
        assert len(result) == 5
        for code in codes:
            assert code in result
            assert len(result[code]) > 0

    def test_batch_financials(self, provider):
        stocks = provider.list_stocks()[:10]
        codes = [s.code for s in stocks]
        result = provider.get_batch_financials(codes)
        assert len(result) == 10
        for code in codes:
            assert result[code].stock_code == code
