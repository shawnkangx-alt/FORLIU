"""技术面和基本面指标计算器。所有函数为纯函数，无副作用。"""

from typing import Any, Callable, Dict, List, Union

from ..data.models import DailyQuote, FinancialReport, IndicatorType


# ===== 技术面指标 =====


def calc_ma(quotes: List[DailyQuote], period: int) -> List[float]:
    """简单移动平均线。"""
    closes = [q.close for q in quotes]
    if len(closes) < period:
        return [0.0] * len(closes)
    result = [0.0] * (period - 1)
    window_sum = sum(closes[:period])
    result.append(round(window_sum / period, 4))
    for i in range(period, len(closes)):
        window_sum += closes[i] - closes[i - period]
        result.append(round(window_sum / period, 4))
    return result


def _ema(values: List[float], period: int) -> List[float]:
    """指数移动平均。"""
    if len(values) < period:
        return [0.0] * len(values)
    multiplier = 2.0 / (period + 1)
    result = [0.0] * (period - 1)
    start = sum(values[:period]) / period
    ema_vals = [start]
    for v in values[period:]:
        ema_vals.append((v - ema_vals[-1]) * multiplier + ema_vals[-1])
    result.extend(round(e, 4) for e in ema_vals)
    return result


def calc_macd(
    quotes: List[DailyQuote], fast: int = 12, slow: int = 26, signal: int = 9
) -> Dict[str, List[float]]:
    """MACD 指标。返回 dif, dea, macd (柱状)。"""
    closes = [q.close for q in quotes]
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)

    dif = [0.0] * len(closes)
    for i in range(len(closes)):
        if ema_fast[i] != 0 and ema_slow[i] != 0:
            dif[i] = round(ema_fast[i] - ema_slow[i], 4)

    dea = _ema(dif[max(slow - 1, 0) :], signal)
    dea_full = [0.0] * (len(closes) - len(dea)) + dea

    macd = [0.0] * len(closes)
    for i in range(len(closes)):
        macd[i] = round((dif[i] - dea_full[i]) * 2, 4) if dif[i] != 0 else 0.0

    return {"dif": dif, "dea": dea_full, "macd": macd}


def calc_rsi(quotes: List[DailyQuote], period: int = 14) -> List[float]:
    """Wilder's RSI 相对强弱指标。"""
    closes = [q.close for q in quotes]
    if len(closes) < period + 1:
        return [0.0] * len(closes)

    result = [0.0] * period

    gains = []
    losses = []
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        gains.append(diff if diff > 0 else 0)
        losses.append(abs(diff) if diff < 0 else 0)

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    rs = avg_gain / avg_loss if avg_loss != 0 else float("inf")
    result.append(round(100.0 - 100.0 / (1 + rs), 4))

    for i in range(period + 1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gain = diff if diff > 0 else 0
        loss = abs(diff) if diff < 0 else 0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        rs = avg_gain / avg_loss if avg_loss != 0 else float("inf")
        result.append(round(100.0 - 100.0 / (1 + rs), 4))

    return result


def calc_kdj(
    quotes: List[DailyQuote], n: int = 9, m1: int = 3, m2: int = 3
) -> Dict[str, List[float]]:
    """KDJ 随机指标。返回 k, d, j 三个数组。"""
    if len(quotes) < n:
        return {"k": [0.0] * len(quotes), "d": [0.0] * len(quotes), "j": [0.0] * len(quotes)}

    highs = [q.high for q in quotes]
    lows = [q.low for q in quotes]
    closes = [q.close for q in quotes]

    k = [0.0] * (n - 1)
    d = [0.0] * (n - 1)
    j = [0.0] * (n - 1)

    k_vals = [50.0]  # initial K value
    for i in range(n - 1, len(closes)):
        highest = max(highs[i - n + 1 : i + 1])
        lowest = min(lows[i - n + 1 : i + 1])
        if highest != lowest:
            rsv = (closes[i] - lowest) / (highest - lowest) * 100
        else:
            rsv = k_vals[-1]
        k_vals.append(round(k_vals[-1] * (m1 - 1) / m1 + rsv / m1, 4))

    k_vals = k_vals[1:]  # drop initial seed
    k.extend(k_vals)

    # D = MA(K, m2) smoothed
    d_start = k[n - 1 : n - 1 + m2 - 1]
    for i in range(n - 1 + m2 - 1, len(k)):
        d_avg = sum(k[i - m2 + 1 : i + 1]) / m2
        d.append(round(d_avg, 4))

    d = d[: len(k)]
    while len(d) < len(k):
        d = [0.0] * (len(k) - len(d)) + d

    for i in range(len(k)):
        if k[i] != 0 and d[i] != 0:
            j.append(round(3 * k[i] - 2 * d[i], 4))
        else:
            j.append(0.0)

    return {"k": k, "d": d, "j": j}


def calc_bollinger(
    quotes: List[DailyQuote], period: int = 20, std_mult: float = 2.0
) -> Dict[str, List[float]]:
    """布林带。返回 upper, middle, lower。"""
    closes = [q.close for q in quotes]
    if len(closes) < period:
        return {
            "upper": [0.0] * len(closes),
            "middle": [0.0] * len(closes),
            "lower": [0.0] * len(closes),
        }

    middle = calc_ma(quotes, period)
    upper = [0.0] * (period - 1)
    lower = [0.0] * (period - 1)

    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1 : i + 1]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        std_dev = variance**0.5
        upper.append(round(mean + std_mult * std_dev, 4))
        lower.append(round(mean - std_mult * std_dev, 4))

    return {"upper": upper, "middle": middle, "lower": lower}


def calc_volume_ratio(quotes: List[DailyQuote]) -> float:
    """量比：当日成交量 / 5日均量。"""
    if len(quotes) < 6:
        return 1.0
    current_vol = quotes[-1].volume
    avg_vol = sum(q.volume for q in quotes[-6:-1]) / 5
    return round(current_vol / avg_vol, 4) if avg_vol > 0 else 1.0


def calc_turnover_rate(quotes: List[DailyQuote]) -> float:
    """换手率：当日成交量 / 总股本（需要市值数据，暂无）。返回成交量趋势。"""
    if len(quotes) < 2:
        return 0.0
    # 简化：近5日均量 vs 近20日均量（量能趋势）
    if len(quotes) < 21:
        return 1.0
    current_avg = sum(q.volume for q in quotes[-5:]) / 5
    hist_avg = sum(q.volume for q in quotes[-20:]) / 20
    return round(current_avg / hist_avg, 4) if hist_avg > 0 else 1.0


def calc_volume(quotes: List[DailyQuote]) -> float:
    """最新成交量（万手）。"""
    if not quotes:
        return 0.0
    return round(quotes[-1].volume, 2)


def calc_obv(quotes: List[DailyQuote]) -> float:
    """OBV 能量潮指标：累计量净流入。"""
    if len(quotes) < 2:
        return 0.0
    obv = 0.0
    for i in range(1, len(quotes)):
        if quotes[i].close > quotes[i - 1].close:
            obv += quotes[i].volume
        elif quotes[i].close < quotes[i - 1].close:
            obv -= quotes[i].volume
    return round(obv, 2)


def calc_dmi(
    quotes: List[DailyQuote], period: int = 14
) -> Dict[str, float]:
    """DMI 动向指标。返回 adx, +di, -di。

    ADX > 25 表示趋势强；+di > -di 为多头信号。
    """
    if len(quotes) < period + 1:
        return {"adx": 0.0, "di_plus": 0.0, "di_minus": 0.0}

    tr_list = []
    dm_plus_list = []
    dm_minus_list = []

    for i in range(1, len(quotes)):
        high, low, prev_close = quotes[i].high, quotes[i].low, quotes[i - 1].close
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        dm_plus = max(high - quotes[i - 1].high, 0) if (high - quotes[i - 1].high) > (quotes[i - 1].low - low) else 0
        dm_minus = max(quotes[i - 1].low - low, 0) if (quotes[i - 1].low - low) > (high - quotes[i - 1].high) else 0
        tr_list.append(tr)
        dm_plus_list.append(dm_plus)
        dm_minus_list.append(dm_minus)

    # ATR
    atr = sum(tr_list[:period]) / period
    for i in range(period, len(tr_list)):
        atr = (atr * (period - 1) + tr_list[i]) / period

    di_plus_raw = sum(dm_plus_list[:period]) / period if atr != 0 else 0
    di_minus_raw = sum(dm_minus_list[:period]) / period if atr != 0 else 0
    di_plus = round(di_plus_raw / atr * 100, 4) if atr != 0 else 0.0
    di_minus = round(di_minus_raw / atr * 100, 4) if atr != 0 else 0.0

    # ADX
    dx_list = []
    for i in range(period, len(tr_list)):
        atr_i = (atr * (period - 1) + tr_list[i]) / period
        dm_plus_i = sum(dm_plus_list[i - period + 1:i + 1]) / period
        dm_minus_i = sum(dm_minus_list[i - period + 1:i + 1]) / period
        di_plus_i = round(dm_plus_i / atr_i * 100, 4) if atr_i != 0 else 0.0
        di_minus_i = round(dm_minus_i / atr_i * 100, 4) if atr_i != 0 else 0.0
        dx = abs(di_plus_i - di_minus_i) / (di_plus_i + di_minus_i) * 100 if (di_plus_i + di_minus_i) > 0 else 0
        dx_list.append(dx)

    adx = round(sum(dx_list) / len(dx_list), 4) if dx_list else 0.0

    return {"adx": adx, "di_plus": di_plus, "di_minus": di_minus}


def calc_wr(quotes: List[DailyQuote], period: int = 14) -> float:
    """WR 威廉指标。0~-100，超卖>-80，超买<-20。"""
    if len(quotes) < period:
        return -50.0
    highest = max(q.high for q in quotes[-period:])
    lowest = min(q.low for q in quotes[-period:])
    close = quotes[-1].close
    if highest == lowest:
        return -50.0
    wr = (highest - close) / (highest - lowest) * -100
    return round(wr, 4)


def calc_psy(quotes: List[DailyQuote], period: int = 12) -> float:
    """PSY 心理线。上涨天数占比。>75偏热，<25偏冷。"""
    if len(quotes) < period + 1:
        return 50.0
    up_days = sum(1 for i in range(1, period + 1) if quotes[i].close > quotes[i - 1].close)
    return round(up_days / period * 100, 4)


def calc_latest_ma_cross(quotes: List[DailyQuote], fast: int, slow: int) -> str:
    """检测最近一期均线交叉状态。返回 'golden', 'death', 或 'none'。"""
    ma_fast = calc_ma(quotes, fast)
    ma_slow = calc_ma(quotes, slow)

    idx = -1
    # 找到最近两个都有值的位置
    valid_indices = [
        i
        for i in range(len(quotes) - 1, -1, -1)
        if ma_fast[i] != 0 and ma_slow[i] != 0
    ]
    if len(valid_indices) < 2:
        return "none"

    curr_idx, prev_idx = valid_indices[0], valid_indices[1]
    if ma_fast[prev_idx] <= ma_slow[prev_idx] and ma_fast[curr_idx] > ma_slow[curr_idx]:
        return "golden"
    if ma_fast[prev_idx] >= ma_slow[prev_idx] and ma_fast[curr_idx] < ma_slow[curr_idx]:
        return "death"
    return "none"


def calc_latest_band_touch(quotes: List[DailyQuote], period: int, std_mult: float) -> str:
    """检测最近一期是否触及布林带。返回 'upper', 'lower', 或 'none'。"""
    boll = calc_bollinger(quotes, period, std_mult)
    close = quotes[-1].close
    if boll["upper"][-1] != 0 and close >= boll["upper"][-1]:
        return "upper"
    if boll["lower"][-1] != 0 and close <= boll["lower"][-1]:
        return "lower"
    return "none"


# ===== 基本面指标 =====


def get_pe(report: FinancialReport) -> float:
    return report.pe


def get_pb(report: FinancialReport) -> float:
    return report.pb


def get_roe(report: FinancialReport) -> float:
    return report.roe


def get_revenue_yoy(report: FinancialReport) -> float:
    return report.revenue_yoy


def get_net_profit_yoy(report: FinancialReport) -> float:
    return report.net_profit_yoy


def get_debt_ratio(report: FinancialReport) -> float:
    return report.debt_ratio


def get_current_ratio(report: FinancialReport) -> float:
    return report.current_ratio


# ===== 调度表 =====

FUNDAMENTAL_GETTERS: Dict[IndicatorType, Callable[[FinancialReport], float]] = {
    IndicatorType.PE: get_pe,
    IndicatorType.PB: get_pb,
    IndicatorType.ROE: get_roe,
    IndicatorType.REVENUE_YOY: get_revenue_yoy,
    IndicatorType.NET_PROFIT_YOY: get_net_profit_yoy,
    IndicatorType.DEBT_RATIO: get_debt_ratio,
    IndicatorType.CURRENT_RATIO: get_current_ratio,
}

TECHNICAL_INDICATORS = {
    IndicatorType.MA,
    IndicatorType.MACD,
    IndicatorType.RSI,
    IndicatorType.KDJ,
    IndicatorType.VOLUME,
    IndicatorType.BOLLINGER,
    IndicatorType.DMI,
    IndicatorType.OBV,
    IndicatorType.WR,
    IndicatorType.PSY,
    IndicatorType.TURNOVER_RATE,
}

TECHNICAL_GETTERS: Dict[IndicatorType, Callable[..., Union[float, Dict]]] = {
    # (quotes, **params) -> float | Dict
    IndicatorType.MA: lambda q, **k: calc_ma(q, **k)[-1] if calc_ma(q, **k)[-1] != 0 else calc_ma(q, **k)[-2],
    IndicatorType.MACD: lambda q, **k: calc_macd(q, **k)["dif"][-1],
    IndicatorType.RSI: lambda q, **k: calc_rsi(q, **k)[-1],
    IndicatorType.KDJ: lambda q, **k: calc_kdj(q, **k)["k"][-1],
    IndicatorType.VOLUME: calc_volume,
    IndicatorType.BOLLINGER: lambda q, **k: calc_bollinger(q, **k)["upper"][-1],
    IndicatorType.DMI: lambda q, **k: calc_dmi(q, **k)["adx"],
    IndicatorType.OBV: calc_obv,
    IndicatorType.WR: calc_wr,
    IndicatorType.PSY: calc_psy,
    IndicatorType.TURNOVER_RATE: calc_turnover_rate,
}

FUNDAMENTAL_INDICATORS = set(FUNDAMENTAL_GETTERS.keys())
