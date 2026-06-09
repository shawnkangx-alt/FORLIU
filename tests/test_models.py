from datetime import date, datetime

from code.data.models import (
    DailyQuote,
    FinancialReport,
    IndicatorType,
    Market,
    Rule,
    RuleOperator,
    ScheduleEntry,
    ScreeningResult,
    Stock,
    Strategy,
)


class TestStock:
    def test_create(self):
        s = Stock("600519", "贵州茅台", Market.SH)
        assert s.code == "600519"
        assert s.name == "贵州茅台"
        assert s.market == Market.SH


class TestDailyQuote:
    def test_create(self):
        q = DailyQuote("600519", date(2025, 6, 1), 1600, 1620, 1580, 1610, 50000, 8e7)
        assert q.stock_code == "600519"
        assert q.close == 1610
        assert q.volume == 50000


class TestFinancialReport:
    def test_create(self):
        r = FinancialReport("600519", date(2025, 3, 31), 30, 8, 25, 1e10, 15, 5e9, 20, 30, 3)
        assert r.pe == 30
        assert r.roe == 25
        assert r.revenue_yoy == 15


class TestRule:
    def test_gt_rule(self):
        r = Rule(IndicatorType.RSI, RuleOperator.GT, {"value": 70})
        assert r.indicator == IndicatorType.RSI
        assert r.operator == RuleOperator.GT
        assert r.params["value"] == 70

    def test_cross_rule(self):
        r = Rule(IndicatorType.MA, RuleOperator.CROSS_ABOVE, {"fast_period": 5, "slow_period": 20})
        assert r.params["fast_period"] == 5
        assert r.params["slow_period"] == 20


class TestStrategy:
    def test_create(self):
        rules = [Rule(IndicatorType.PE, RuleOperator.LT, {"value": 20})]
        s = Strategy("value", "低估值策略", rules, min_score=50)
        assert s.name == "value"
        assert len(s.rules) == 1
        assert s.min_score == 50

    def test_defaults(self):
        s = Strategy("test")
        assert s.rules == []
        assert s.min_score == 0.0


class TestScreeningResult:
    def test_create(self):
        stock = Stock("600519", "贵州茅台", Market.SH)
        result = ScreeningResult(stock=stock, indicators={}, matched_rules=[], score=80)
        assert result.stock.code == "600519"
        assert result.score == 80
        assert isinstance(result.match_time, datetime)


class TestScheduleEntry:
    def test_create(self):
        entry = ScheduleEntry(
            name="每日扫描", strategy_name="momentum", cron_expression="37 15 * * 1-5"
        )
        assert entry.name == "每日扫描"
        assert entry.strategy_name == "momentum"
        assert entry.enabled is True
        assert len(entry.id) == 12


class TestEnums:
    def test_market(self):
        assert Market.SH.value == "SH"
        assert Market.SZ.value == "SZ"

    def test_indicator_type(self):
        assert IndicatorType.RSI.value == "rsi"
        assert IndicatorType.PE.value == "pe"

    def test_rule_operator(self):
        assert RuleOperator.GT.value == "gt"
        assert RuleOperator.CROSS_ABOVE.value == "cross_above"
