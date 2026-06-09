"""筛选编排器：加载预设策略，执行筛选，格式化输出。"""

from typing import TYPE_CHECKING, Dict, List, Optional

from ..data.models import (
    IndicatorType,
    Rule,
    RuleOperator,
    ScreeningResult,
    Strategy,
)
from ..data.provider import DataProvider

if TYPE_CHECKING:
    from .stock_pool import StockPoolFilter

_PRESETS: Dict[str, Strategy] = {
    "value": Strategy(
        name="value",
        description="低估值策略：低PE + 低PB + 高ROE + 低负债率",
        rules=[
            Rule(IndicatorType.PE, RuleOperator.LT, {"value": 20}, weight=3.0),
            Rule(IndicatorType.PB, RuleOperator.LT, {"value": 3}, weight=2.0),
            Rule(IndicatorType.ROE, RuleOperator.GT, {"value": 10}, weight=2.0),
            Rule(IndicatorType.DEBT_RATIO, RuleOperator.LT, {"value": 60}, weight=1.0),
        ],
        min_score=50,
    ),
    "growth": Strategy(
        name="growth",
        description="高成长策略：高营收增长 + 高利润增长 + ROE",
        rules=[
            Rule(IndicatorType.REVENUE_YOY, RuleOperator.GT, {"value": 20}, weight=3.0),
            Rule(IndicatorType.NET_PROFIT_YOY, RuleOperator.GT, {"value": 20}, weight=2.0),
            Rule(IndicatorType.ROE, RuleOperator.GT, {"value": 10}, weight=1.0),
        ],
        min_score=50,
    ),
    "momentum": Strategy(
        name="momentum",
        description="动量策略：均线金叉 + RSI合理区间 + 放量",
        rules=[
            Rule(IndicatorType.MA, RuleOperator.CROSS_ABOVE, {"fast_period": 5, "slow_period": 20}, weight=3.0),
            Rule(IndicatorType.RSI, RuleOperator.BETWEEN, {"low": 30, "high": 70}, weight=1.0),
            Rule(IndicatorType.VOLUME, RuleOperator.GT, {"value": 1.0}, weight=2.0),
        ],
        min_score=50,
    ),
    "bollinger_breakout": Strategy(
        name="bollinger_breakout",
        description="布林突破策略：触及下轨反弹 + 放量",
        rules=[
            Rule(IndicatorType.BOLLINGER, RuleOperator.TOUCH_LOWER, {"period": 20, "std_mult": 2.0}, weight=2.0),
            Rule(IndicatorType.VOLUME, RuleOperator.GT, {"value": 1.2}, weight=2.0),
        ],
        min_score=50,
    ),
    "comprehensive": Strategy(
        name="comprehensive",
        description="综合策略：价值 + 成长 + 动量",
        rules=[
            Rule(IndicatorType.PE, RuleOperator.LT, {"value": 30}, weight=2.0),
            Rule(IndicatorType.PB, RuleOperator.LT, {"value": 5}, weight=1.0),
            Rule(IndicatorType.ROE, RuleOperator.GT, {"value": 8}, weight=2.0),
            Rule(IndicatorType.REVENUE_YOY, RuleOperator.GT, {"value": 10}, weight=2.0),
            Rule(IndicatorType.RSI, RuleOperator.BETWEEN, {"low": 25, "high": 75}, weight=1.0),
        ],
        min_score=40,
    ),
}


class Screener:
    """股票筛选编排器。"""

    def __init__(self, provider: DataProvider, pool_filter: Optional["StockPoolFilter"] = None,
                 report_type: str = "annual"):
        self.provider = provider
        self.pool_filter = pool_filter
        self.report_type = report_type
        self._engine = _StrategyRunner(provider)

    def screen(self, strategy: Strategy, top_n: int = 20, stock_limit: Optional[int] = None) -> List[ScreeningResult]:
        """执行策略筛选，返回 top N 结果。"""
        results = self._engine.run(strategy, pool_filter=self.pool_filter,
                                  report_type=self.report_type, stock_limit=stock_limit)
        return results[:top_n]

    def screen_preset(self, preset_name: str, top_n: int = 20, stock_limit: Optional[int] = None) -> List[ScreeningResult]:
        """执行预设策略筛选。"""
        strategy = _PRESETS.get(preset_name)
        if not strategy:
            raise ValueError(f"未知预设策略: {preset_name}，可用: {list(_PRESETS.keys())}")
        return self.screen(strategy, top_n=top_n, stock_limit=stock_limit)

    def list_presets(self) -> Dict[str, str]:
        """列出所有可用预设策略及其描述。"""
        return {name: s.description for name, s in _PRESETS.items()}


# Internal runner — actual strategy evaluation logic
from datetime import datetime, timedelta
from typing import Callable, Dict, List

from ..data.models import (
    DailyQuote,
    FinancialReport,
    IndicatorResult,
    IndicatorType,
    Rule,
    ScreeningResult,
    Strategy,
)
from .indicators import FUNDAMENTAL_GETTERS, FUNDAMENTAL_INDICATORS
from .rules import RuleEvaluator


class _StrategyRunner:
    """评估策略并返回筛选结果。"""

    def __init__(self, provider: DataProvider):
        self.provider = provider
        self.evaluator = RuleEvaluator()

    def run(
        self, strategy: Strategy, pool_filter: Optional["StockPoolFilter"] = None,
        report_type: str = "annual", stock_limit: Optional[int] = None
    ) -> List[ScreeningResult]:
        stocks = self.provider.list_stocks()
        if stock_limit:
            stocks = stocks[:stock_limit]

        # 应用股票池过滤
        if pool_filter:
            codes = [s.code for s in stocks]
            filtered_codes = pool_filter.filter_codes(codes)
            code_set = set(filtered_codes)
            stocks = [s for s in stocks if s.code in code_set]

        if not stocks or not strategy.rules:
            return []

        codes = [s.code for s in stocks]
        end = datetime.today().date()
        start = end - timedelta(days=60)
        try:
            all_quotes = self.provider.get_batch_quotes(
                codes, start, end
            )
        except Exception as e:
            raise RuntimeError(f"获取行情数据失败: {e}")

        try:
            all_financials = self.provider.get_batch_financials(
                codes, report_type=report_type
            )
        except Exception as e:
            raise RuntimeError(f"获取财务数据失败: {e}")

        results: List[ScreeningResult] = []
        skipped_quotes: List[str] = []
        skipped_financials: List[str] = []

        for stock in stocks:
            quotes = all_quotes.get(stock.code, [])
            financials = all_financials.get(stock.code)
            if not quotes:
                skipped_quotes.append(stock.code)
                continue
            if not financials:
                skipped_financials.append(stock.code)
                continue

            matched: List[Rule] = []
            total_weight = sum(rule.weight for rule in strategy.rules)
            matched_weight = 0.0
            for rule in strategy.rules:
                try:
                    if self.evaluator.evaluate(rule, quotes, financials):
                        matched.append(rule)
                        matched_weight += rule.weight
                except Exception:
                    continue

            if total_weight > 0:
                score = (matched_weight / total_weight) * 100.0
            else:
                score = 0.0

            if score >= strategy.min_score:
                indicators = self._collect_indicators(strategy.rules, quotes, financials)
                results.append(
                    ScreeningResult(
                        stock=stock,
                        indicators=indicators,
                        matched_rules=matched,
                        score=round(score, 1),
                    )
                )

        results.sort(key=lambda r: r.score, reverse=True)

        # 如果所有股票都被跳过（无行情或无财务），报告详情
        if not results and (skipped_quotes or skipped_financials):
            parts = []
            if skipped_quotes:
                parts.append(f"无行情数据({len(skipped_quotes)}只): {', '.join(skipped_quotes[:10])}")
            if skipped_financials:
                parts.append(f"无财务数据({len(skipped_financials)}只): {', '.join(skipped_financials[:10])}")
            raise RuntimeError("筛选完成但无符合条件结果。\n" + "\n".join(parts))

        return results

    def _collect_indicators(
        self, rules: List[Rule], quotes: List[DailyQuote], financials: FinancialReport
    ) -> Dict[IndicatorType, IndicatorResult]:
        indicators: Dict[IndicatorType, IndicatorResult] = {}
        seen: set[IndicatorType] = set()
        for rule in rules:
            if rule.indicator in seen:
                continue
            seen.add(rule.indicator)
            result = IndicatorResult(indicator=rule.indicator)
            if rule.indicator in FUNDAMENTAL_INDICATORS:
                getter = FUNDAMENTAL_GETTERS[rule.indicator]
                result.values["current"] = getter(financials)
            indicators[rule.indicator] = result
        return indicators
