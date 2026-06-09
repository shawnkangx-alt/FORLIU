"""策略引擎：将 Strategy 应用于股票池，打分并排序。"""

from datetime import datetime
from typing import Dict, List, Optional

from ..data.models import (
    DailyQuote,
    FinancialReport,
    IndicatorResult,
    IndicatorType,
    Rule,
    ScreeningResult,
    Strategy,
)
from ..data.provider import DataProvider
from .indicators import FUNDAMENTAL_GETTERS, FUNDAMENTAL_INDICATORS, TECHNICAL_INDICATORS
from .rules import RuleEvaluator


class StrategyEngine:
    """评估整个策略并返回筛选结果。"""

    def __init__(self, provider: DataProvider, evaluator: Optional[RuleEvaluator] = None):
        self.provider = provider
        self.evaluator = evaluator or RuleEvaluator()

    def run(
        self, strategy: Strategy, stock_codes: Optional[List[str]] = None
    ) -> List[ScreeningResult]:
        stocks = self.provider.list_stocks()
        if stock_codes:
            code_set = set(stock_codes)
            stocks = [s for s in stocks if s.code in code_set]

        if not strategy.rules:
            return []

        codes = [s.code for s in stocks]
        all_quotes = self.provider.get_batch_quotes(codes, datetime(2025, 1, 1).date(), datetime(2025, 12, 31).date())
        all_financials = self.provider.get_batch_financials(codes, report_type="annual")

        results: List[ScreeningResult] = []

        for stock in stocks:
            quotes = all_quotes.get(stock.code, [])
            financials = all_financials.get(stock.code)
            if not quotes or not financials:
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
