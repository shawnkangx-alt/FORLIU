from code.data.models import IndicatorType, Rule, RuleOperator, Strategy
from code.data.mock_provider import MockDataProvider
from code.screening.strategy import StrategyEngine


class TestStrategyEngine:

    def setup_method(self):
        self.provider = MockDataProvider(seed=42)
        self.engine = StrategyEngine(self.provider)

    def test_empty_strategy(self):
        strategy = Strategy("empty")
        results = self.engine.run(strategy)
        assert results == []

    def test_single_rule_value(self):
        strategy = Strategy(
            "test", rules=[Rule(IndicatorType.PE, RuleOperator.LT, {"value": 100})]
        )
        results = self.engine.run(strategy)
        # PE < 100 should match all 50 stocks in mock data
        assert len(results) == 50
        for r in results:
            assert r.score == 100.0
            assert len(r.matched_rules) == 1

    def test_results_ranked_by_score(self):
        strategy = Strategy(
            "test",
            rules=[
                Rule(IndicatorType.PE, RuleOperator.LT, {"value": 100}),
                Rule(IndicatorType.ROE, RuleOperator.GT, {"value": 0}),
            ],
        )
        results = self.engine.run(strategy)
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score

    def test_min_score_filters(self):
        strategy = Strategy(
            "test",
            rules=[
                Rule(IndicatorType.PE, RuleOperator.LT, {"value": 100}),
                Rule(IndicatorType.DEBT_RATIO, RuleOperator.LT, {"value": 0.1}),
                Rule(IndicatorType.ROE, RuleOperator.GT, {"value": 90}),
            ],
            min_score=100,
        )
        results = self.engine.run(strategy)
        # With min_score=100, only stocks matching ALL rules pass
        # Very few (possibly 0) stocks with debt < 0.1 and ROE > 90
        assert all(r.score >= 100 for r in results)

    def test_stock_codes_filter(self):
        strategy = Strategy(
            "test", rules=[Rule(IndicatorType.PE, RuleOperator.LT, {"value": 100})]
        )
        results = self.engine.run(strategy, stock_codes=["600519", "000858"])
        assert len(results) == 2
        codes = {r.stock.code for r in results}
        assert codes == {"600519", "000858"}
