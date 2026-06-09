from datetime import date

from code.data.models import (
    DailyQuote,
    FinancialReport,
    IndicatorType,
    Rule,
    RuleOperator,
)
from code.screening.rules import RuleEvaluator


def _make_fin(**overrides) -> FinancialReport:
    defaults = {
        "stock_code": "000001",
        "report_date": date(2025, 12, 31),
        "pe": 15,
        "pb": 2,
        "roe": 20,
        "revenue": 1e10,
        "revenue_yoy": 15,
        "net_profit": 2e9,
        "net_profit_yoy": 20,
        "debt_ratio": 40,
        "current_ratio": 2,
    }
    defaults.update(overrides)
    return FinancialReport(**defaults)


def _make_quotes(prices: list[float]) -> list[DailyQuote]:
    return [
        DailyQuote("000001", date(2025, 1, 1) + date.resolution * i, p, p, p, p, 100, p * 100)
        for i, p in enumerate(prices)
    ]


class TestRuleEvaluator:

    def setup_method(self):
        self.evaluator = RuleEvaluator()

    # ---- GT / LT / BETWEEN ----

    def test_gt_match(self):
        rule = Rule(IndicatorType.PE, RuleOperator.GT, {"value": 10})
        fin = _make_fin(pe=15)
        assert self.evaluator.evaluate(rule, _make_quotes([100] * 30), fin) is True

    def test_gt_no_match(self):
        rule = Rule(IndicatorType.PE, RuleOperator.GT, {"value": 20})
        fin = _make_fin(pe=15)
        assert self.evaluator.evaluate(rule, _make_quotes([100] * 30), fin) is False

    def test_lt_match(self):
        rule = Rule(IndicatorType.PE, RuleOperator.LT, {"value": 20})
        fin = _make_fin(pe=15)
        assert self.evaluator.evaluate(rule, _make_quotes([100] * 30), fin) is True

    def test_lt_no_match(self):
        rule = Rule(IndicatorType.PE, RuleOperator.LT, {"value": 10})
        fin = _make_fin(pe=15)
        assert self.evaluator.evaluate(rule, _make_quotes([100] * 30), fin) is False

    def test_between_match(self):
        rule = Rule(IndicatorType.ROE, RuleOperator.BETWEEN, {"low": 10, "high": 30})
        fin = _make_fin(roe=20)
        assert self.evaluator.evaluate(rule, _make_quotes([100] * 30), fin) is True

    def test_between_no_match(self):
        rule = Rule(IndicatorType.ROE, RuleOperator.BETWEEN, {"low": 10, "high": 30})
        fin = _make_fin(roe=5)
        assert self.evaluator.evaluate(rule, _make_quotes([100] * 30), fin) is False

    # ---- RSI ----

    def test_rsi_between_match(self):
        # 使用足够多的数据点和合理的价格波动，RSI 自然落在中间区域
        prices = [100.0]
        rng = __import__("random").Random(42)
        for _ in range(100):
            prices.append(prices[-1] + rng.gauss(0, 0.5))
        rule = Rule(IndicatorType.RSI, RuleOperator.BETWEEN, {"low": 30, "high": 70})
        quotes = _make_quotes(prices)
        assert self.evaluator.evaluate(rule, quotes, _make_fin()) is True

    # ---- Volume ----

    def test_volume_gt(self):
        rule = Rule(IndicatorType.VOLUME, RuleOperator.GT, {"value": 0.5})
        quotes = _make_quotes([100] * 10)
        assert self.evaluator.evaluate(rule, quotes, _make_fin()) is True

    def test_volume_lt(self):
        rule = Rule(IndicatorType.VOLUME, RuleOperator.LT, {"value": 0.5})
        quotes = _make_quotes([100] * 10)
        # All same volume = ratio 1.0, so LT 0.5 should be False
        assert self.evaluator.evaluate(rule, quotes, _make_fin()) is False
