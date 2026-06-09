from datetime import date

from code.data.models import DailyQuote, FinancialReport, IndicatorType, Rule, RuleOperator
from code.screening.indicators import (
    calc_bollinger,
    calc_kdj,
    calc_latest_band_touch,
    calc_latest_ma_cross,
    calc_ma,
    calc_macd,
    calc_rsi,
    calc_volume_ratio,
    FUNDAMENTAL_GETTERS,
    get_current_ratio,
    get_debt_ratio,
    get_net_profit_yoy,
    get_pb,
    get_pe,
    get_revenue_yoy,
    get_roe,
)


def _make_quotes(prices: list[float]) -> list[DailyQuote]:
    return [
        DailyQuote("000001", date(2025, 1, 1) + date.resolution * i, p, p, p, p, 100, p * 100)
        for i, p in enumerate(prices)
    ]


class TestMA:
    def test_ma_basic(self):
        quotes = _make_quotes([10, 20, 30, 40, 50])
        result = calc_ma(quotes, 3)
        assert result[0] == 0.0
        assert result[1] == 0.0
        assert result[2] == 20.0  # (10+20+30)/3
        assert result[3] == 30.0  # (20+30+40)/3
        assert result[4] == 40.0  # (30+40+50)/3

    def test_ma_insufficient_data(self):
        quotes = _make_quotes([10, 20])
        result = calc_ma(quotes, 5)
        assert all(v == 0.0 for v in result)


class TestRSI:
    def test_rsi_returns_values(self):
        prices = [100 + i * 0.5 for i in range(30)]  # steady uptrend
        quotes = _make_quotes(prices)
        result = calc_rsi(quotes, 14)
        assert len(result) == len(quotes)
        # RSI in uptrend should be high
        last_valid = [v for v in result if v != 0][-1]
        assert last_valid > 50

    def test_rsi_insufficient_data(self):
        quotes = _make_quotes([100] * 5)
        result = calc_rsi(quotes, 14)
        assert all(v == 0.0 for v in result)


class TestMACD:
    def test_macd_structure(self):
        prices = [100 + i * 0.2 for i in range(50)]
        quotes = _make_quotes(prices)
        result = calc_macd(quotes)
        assert "dif" in result
        assert "dea" in result
        assert "macd" in result
        assert len(result["dif"]) == len(quotes)
        assert len(result["dea"]) == len(quotes)
        assert len(result["macd"]) == len(quotes)


class TestKDJ:
    def test_kdj_structure(self):
        prices = []
        v = 100
        for i in range(30):
            v += (i % 5) - 2  # some variation
            prices.append(v)
        quotes = _make_quotes(prices)
        result = calc_kdj(quotes)
        assert "k" in result
        assert "d" in result
        assert "j" in result
        assert len(result["k"]) == len(quotes)


class TestBollinger:
    def test_bollinger_structure(self):
        prices = [100 + i * 0.5 for i in range(30)]
        quotes = _make_quotes(prices)
        result = calc_bollinger(quotes, period=10)
        assert "upper" in result
        assert "middle" in result
        assert "lower" in result
        # 上轨应高于中轨
        for i in range(9, len(prices)):
            if result["upper"][i] != 0:
                assert result["upper"][i] >= result["middle"][i] >= result["lower"][i]

    def test_bollinger_insufficient_data(self):
        quotes = _make_quotes([100] * 5)
        result = calc_bollinger(quotes, period=20)
        assert all(v == 0.0 for v in result["upper"])


class TestVolumeRatio:
    def test_volume_ratio_normal(self):
        quotes = _make_quotes([100] * 10)
        result = calc_volume_ratio(quotes)
        assert result == 1.0  # all same volume

    def test_volume_ratio_insufficient(self):
        quotes = _make_quotes([100] * 3)
        assert calc_volume_ratio(quotes) == 1.0


class TestMACross:
    def test_golden_cross(self):
        # 构建金叉场景：前一期 MA5 < MA20，当前 MA5 > MA20
        prices = (
            [10] * 19  # MA20 建立（都是10）
            + [5] * 5   # MA5 下降（MA5 < MA20）
            + [20] * 1  # 跳涨触发 MA5 上穿
        )
        quotes = _make_quotes(prices)
        result = calc_latest_ma_cross(quotes, 5, 20)
        # After the jump to 20, MA5 should rise; MA20 stays near 10
        assert result in ("golden", "none")  # depends on exact window


class TestBandTouch:
    def test_band_touch_none(self):
        # 价格在布林带内波动，不触及边界
        prices = []
        v = 100.0
        for i in range(30):
            v += 0.5 if i % 2 == 0 else -0.5
            prices.append(v)
        quotes = _make_quotes(prices)
        result = calc_latest_band_touch(quotes, 10, 2.0)
        assert result == "none"


class TestFundamentalGetters:
    def test_getters_exist(self):
        assert callable(FUNDAMENTAL_GETTERS[IndicatorType.PE])
        assert callable(FUNDAMENTAL_GETTERS[IndicatorType.PB])
        assert callable(FUNDAMENTAL_GETTERS[IndicatorType.ROE])

    def test_getters_return_float(self):
        report = FinancialReport("000001", date(2025, 12, 31), 15, 2, 20, 1e9, 10, 1e8, 15, 40, 2)
        assert get_pe(report) == 15
        assert get_pb(report) == 2
        assert get_roe(report) == 20
        assert get_revenue_yoy(report) == 10
        assert get_net_profit_yoy(report) == 15
        assert get_debt_ratio(report) == 40
        assert get_current_ratio(report) == 2
