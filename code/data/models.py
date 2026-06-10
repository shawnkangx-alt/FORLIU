from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class Market(str, Enum):
    SH = "SH"
    SZ = "SZ"
    BJ = "BJ"


class RuleOperator(str, Enum):
    GT = "gt"
    LT = "lt"
    BETWEEN = "between"
    CROSS_ABOVE = "cross_above"
    CROSS_BELOW = "cross_below"
    TOUCH_UPPER = "touch_upper"
    TOUCH_LOWER = "touch_lower"


class IndicatorType(str, Enum):
    # Technical
    MA = "ma"
    MACD = "macd"
    RSI = "rsi"
    KDJ = "kdj"
    VOLUME = "volume"
    BOLLINGER = "bollinger"
    DMI = "dmi"
    OBV = "obv"
    WR = "wr"
    PSY = "psy"
    TURNOVER_RATE = "turnover_rate"
    # Fundamental
    PE = "pe"
    PB = "pb"
    ROE = "roe"
    REVENUE_YOY = "revenue_yoy"
    NET_PROFIT_YOY = "net_profit_yoy"
    DEBT_RATIO = "debt_ratio"
    CURRENT_RATIO = "current_ratio"


@dataclass
class Stock:
    code: str
    name: str
    market: Market


@dataclass
class DailyQuote:
    stock_code: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float


@dataclass
class FinancialReport:
    stock_code: str
    report_date: date = None  # type: ignore[assignment]
    report_type: str = "annual"  # "annual" | "quarterly" | "ttm"
    pe: float = 0
    pb: float = 0
    roe: float = 0
    revenue: float = 0
    revenue_yoy: float = 0
    net_profit: float = 0
    net_profit_yoy: float = 0
    debt_ratio: float = 0
    current_ratio: float = 0


@dataclass
class Rule:
    indicator: IndicatorType
    operator: RuleOperator
    params: Dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0  # 规则权重，影响最终得分


@dataclass
class Strategy:
    name: str
    description: str = ""
    rules: List[Rule] = field(default_factory=list)
    min_score: float = 0.0


@dataclass
class IndicatorResult:
    indicator: IndicatorType
    values: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScreeningResult:
    stock: Stock
    indicators: Dict[IndicatorType, IndicatorResult]
    matched_rules: List[Rule]
    score: float
    match_time: datetime = field(default_factory=datetime.now)


@dataclass
class ScheduleEntry:
    name: str
    strategy_name: str
    cron_expression: str
    notification_channels: List[str] = field(default_factory=lambda: ["console"])
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)
