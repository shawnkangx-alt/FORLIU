"""规则评估引擎。将 Rule 应用于股票数据，判断是否满足条件。"""

from typing import List

from ..data.models import DailyQuote, FinancialReport, IndicatorType, Rule, RuleOperator
from .indicators import (
    FUNDAMENTAL_GETTERS,
    calc_kdj,
    calc_latest_band_touch,
    calc_latest_ma_cross,
    calc_macd,
    calc_rsi,
    calc_volume_ratio,
)


def _latest_rsi(quotes: List[DailyQuote], period: int = 14) -> float:
    rsi_vals = calc_rsi(quotes, period)
    for v in reversed(rsi_vals):
        if v != 0:
            return v
    return 0.0


def _latest_volume_ratio(quotes: List[DailyQuote]) -> float:
    return calc_volume_ratio(quotes)


def _latest_macd_cross(quotes: List[DailyQuote]) -> str:
    """检测最近一期 MACD 金叉/死叉。"""
    macd_data = calc_macd(quotes)
    dif = macd_data["dif"]
    dea = macd_data["dea"]

    valid = [i for i in range(len(dif) - 1, -1, -1) if dif[i] != 0 and dea[i] != 0]
    if len(valid) < 2:
        return "none"

    curr, prev = valid[0], valid[1]
    if dif[prev] <= dea[prev] and dif[curr] > dea[curr]:
        return "golden"
    if dif[prev] >= dea[prev] and dif[curr] < dea[curr]:
        return "death"
    return "none"


def _latest_macd_value(quotes: List[DailyQuote]) -> float:
    """获取最近一期 MACD 柱状值。"""
    macd_data = calc_macd(quotes)
    for v in reversed(macd_data["macd"]):
        if v != 0:
            return v
    return 0.0


def _latest_kdj_cross(quotes: List[DailyQuote]) -> str:
    """检测最近一期 KDJ K/D 交叉。"""
    kdj_data = calc_kdj(quotes)
    k = kdj_data["k"]
    d = kdj_data["d"]

    valid = [i for i in range(len(k) - 1, -1, -1) if k[i] != 0 and d[i] != 0]
    if len(valid) < 2:
        return "none"

    curr, prev = valid[0], valid[1]
    if k[prev] <= d[prev] and k[curr] > d[curr]:
        return "golden"
    if k[prev] >= d[prev] and k[curr] < d[curr]:
        return "death"
    return "none"


def _latest_kdj_values(quotes: List[DailyQuote]) -> dict:
    """获取最近一期 K/D/J 值。"""
    kdj_data = calc_kdj(quotes)
    result = {"k": 0.0, "d": 0.0, "j": 0.0}
    for i in range(len(quotes) - 1, -1, -1):
        if kdj_data["k"][i] != 0 and result["k"] == 0.0:
            result["k"] = kdj_data["k"][i]
            result["d"] = kdj_data["d"][i]
            result["j"] = kdj_data["j"][i]
            break
    return result


class RuleEvaluator:
    """评估单条规则是否匹配。"""

    def evaluate(
        self, rule: Rule, quotes: List[DailyQuote], financials: FinancialReport
    ) -> bool:
        indicator = rule.indicator
        operator = rule.operator
        params = rule.params

        if indicator == IndicatorType.RSI:
            value = _latest_rsi(quotes, params.get("period", 14))
            return self._eval_numeric(value, operator, params)

        elif indicator == IndicatorType.MA:
            fast = params.get("fast_period", 5)
            slow = params.get("slow_period", 20)
            cross = calc_latest_ma_cross(quotes, fast, slow)
            if operator in (RuleOperator.CROSS_ABOVE, RuleOperator.CROSS_BELOW):
                expected = "golden" if operator == RuleOperator.CROSS_ABOVE else "death"
                return cross == expected
            return False

        elif indicator == IndicatorType.MACD:
            if operator in (RuleOperator.CROSS_ABOVE, RuleOperator.CROSS_BELOW):
                cross = _latest_macd_cross(quotes)
                expected = "golden" if operator == RuleOperator.CROSS_ABOVE else "death"
                return cross == expected
            value = _latest_macd_value(quotes)
            return self._eval_numeric(value, operator, params)

        elif indicator == IndicatorType.KDJ:
            if operator in (RuleOperator.CROSS_ABOVE, RuleOperator.CROSS_BELOW):
                cross = _latest_kdj_cross(quotes)
                expected = "golden" if operator == RuleOperator.CROSS_ABOVE else "death"
                return cross == expected
            kdj = _latest_kdj_values(quotes)
            field = params.get("field", "k")
            value = kdj.get(field, 0.0)
            return self._eval_numeric(value, operator, params)

        elif indicator == IndicatorType.VOLUME:
            value = _latest_volume_ratio(quotes)
            return self._eval_numeric(value, operator, params)

        elif indicator == IndicatorType.BOLLINGER:
            period = params.get("period", 20)
            std_mult = params.get("std_mult", 2.0)
            touch = calc_latest_band_touch(quotes, period, std_mult)
            if operator == RuleOperator.TOUCH_UPPER:
                return touch == "upper"
            if operator == RuleOperator.TOUCH_LOWER:
                return touch == "lower"
            return False

        getter = FUNDAMENTAL_GETTERS.get(indicator)
        if getter:
            value = getter(financials)
            return self._eval_numeric(value, operator, params)

        return False

    def _eval_numeric(
        self, value: float, operator: RuleOperator, params: dict
    ) -> bool:
        if operator == RuleOperator.GT:
            return value > params.get("value", 0)
        elif operator == RuleOperator.LT:
            return value < params.get("value", float("inf"))
        elif operator == RuleOperator.BETWEEN:
            low = params.get("low", 0)
            high = params.get("high", float("inf"))
            return low <= value <= high
        return False
