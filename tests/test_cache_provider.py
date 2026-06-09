import os
import tempfile
from datetime import date

from code.data.cache_provider import CacheProvider
from code.data.mock_provider import MockDataProvider


class TestCacheProvider:

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.upstream = MockDataProvider(seed=42)
        self.cache = CacheProvider(
            self.upstream,
            cache_dir=self.tmpdir,
            quote_ttl_days=365,
            financial_ttl_days=365,
        )

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_list_stocks_cached(self):
        stocks1 = self.cache.list_stocks()
        stocks2 = self.cache.list_stocks()
        assert len(stocks1) == len(stocks2)
        assert stocks1[0].code == stocks2[0].code

    def test_quotes_cached(self):
        quotes1 = self.cache.get_daily_quotes("600519", date(2025, 6, 1), date(2025, 6, 10))
        quotes2 = self.cache.get_daily_quotes("600519", date(2025, 6, 1), date(2025, 6, 10))
        assert len(quotes1) == len(quotes2)
        for a, b in zip(quotes1, quotes2):
            assert a.close == b.close
            assert a.date == b.date

    def test_financials_cached(self):
        fin1 = self.cache.get_financials("600519")
        fin2 = self.cache.get_financials("600519")
        assert fin1.pe == fin2.pe
        assert fin1.roe == fin2.roe

    def test_batch_quotes(self):
        result = self.cache.get_batch_quotes(
            ["600519", "000858"], date(2025, 6, 1), date(2025, 6, 10)
        )
        assert "600519" in result
        assert "000858" in result
        assert len(result["600519"]) > 0

    def test_batch_financials(self):
        result = self.cache.get_batch_financials(["600519", "000858"])
        assert "600519" in result
        assert "000858" in result

    def test_clear_cache(self):
        self.cache.get_daily_quotes("600519", date(2025, 6, 1), date(2025, 6, 10))
        self.cache.clear_cache()
        # After clear, should refetch from upstream (same data, freshly cached)
        quotes = self.cache.get_daily_quotes("600519", date(2025, 6, 1), date(2025, 6, 10))
        assert len(quotes) > 0

    def test_cache_file_created(self):
        self.cache.get_daily_quotes("600519", date(2025, 6, 1), date(2025, 6, 10))
        db_path = os.path.join(self.tmpdir, "data_cache.db")
        assert os.path.exists(db_path)
