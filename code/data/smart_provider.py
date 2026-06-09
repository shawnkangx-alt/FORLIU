"""智能数据提供者：多源优先级，无降级，数据完全透明。"""

import logging
from datetime import date
from typing import Dict, List, Optional, Tuple

from .models import DailyQuote, FinancialReport, Stock
from .provider import DataProvider

logger = logging.getLogger(__name__)


class DataSourceError(Exception):
    """数据源错误，包含每层的具体失败原因。"""

    def __init__(self, provider_chain: List[Tuple[str, str, str]]):
        """provider_chain: [(provider_name, stock_code, error_message), ...]"""
        self.provider_chain = provider_chain
        lines = ["所有数据源均失败，详细错误如下："]
        for prov, code, err in provider_chain:
            lines.append(f"  [{prov}] 股票 {code}: {err}")
        super().__init__("\n".join(lines))


class SmartProvider(DataProvider):
    """多数据源优先级提供者。

    数据优先级（按类型）：
      行情(K线)：WebProvider(腾讯+新浪) → efinance → AkShare → BaoStock
      基本面：WebProvider(腾讯PE/PB+新浪日K) → Tushare → JoinQuant → eFinance → AkShare → BaoStock

    规则：
    - 永远不使用 Mock 数据作为降级
    - 每个 provider 独立追踪，数据来源全程透明
    - 全部失败时抛出 DataSourceError，列出所有层失败原因
    - 只返回有真实数据的股票，空数据股票不静默跳过
    """

    # 行情数据优先级
    QUOTE_PRIORITY = ["WebProvider", "EFinanceProvider", "AkShareProvider", "BaoStockProvider"]
    # 基本面数据优先级
    FINANCIAL_PRIORITY = ["WebProvider", "TushareProvider", "JoinQuantProvider", "EFinanceProvider", "AkShareProvider", "BaoStockProvider"]

    def __init__(self, providers: List[DataProvider]):
        if not providers:
            raise ValueError("至少需要一个数据源")
        self.providers = providers
        # 追踪当前活跃 provider（用于诊断输出）
        self._active_quotes: Optional[str] = None
        self._active_financials: Optional[str] = None
        # 记录每只股票的数据来源
        self._source_map: Dict[str, Dict[str, str]] = {}

    def _source_report(self) -> str:
        """返回当前数据来源摘要。"""
        lines = ["[数据来源]"]
        if self._active_quotes:
            lines.append(f"  行情: {self._active_quotes}")
        if self._active_financials:
            lines.append(f"  基本面: {self._active_financials}")
        if self._source_map:
            lines.append("  各股数据源:")
            for code, src in self._source_map.items():
                parts = [f"{k}={v}" for k, v in src.items()]
                lines.append(f"    {code}: {', '.join(parts)}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 行情数据
    # ------------------------------------------------------------------

    def get_daily_quotes(self, stock_code: str, start: date, end: date) -> List[DailyQuote]:
        errors: List[Tuple[str, str, str]] = []
        for p in self.providers:
            try:
                quotes = p.get_daily_quotes(stock_code, start, end)
                if quotes:
                    name = type(p).__name__
                    if self._active_quotes != name:
                        logger.info(f"[SmartProvider] 行情数据 -> {name}")
                        self._active_quotes = name
                    self._source_map.setdefault(stock_code, {})["quotes"] = name
                    return quotes
            except Exception as e:
                errors.append((type(p).__name__, stock_code, str(e)))
        # 所有源都失败
        raise DataSourceError(errors)

    def get_batch_quotes(
        self, stock_codes: List[str], start: date, end: date
    ) -> Dict[str, List[DailyQuote]]:
        result: Dict[str, List[DailyQuote]] = {}
        errors: List[Tuple[str, str, str]] = []
        for code in stock_codes:
            try:
                quotes = self.get_daily_quotes(code, start, end)
                if quotes:
                    result[code] = quotes
            except DataSourceError as e:
                # 收集但不在中途停止，让所有股票都尝试完
                errors.extend(e.provider_chain)
        if errors and not result:
            raise DataSourceError(errors)
        return result

    # ------------------------------------------------------------------
    # 基本面数据
    # ------------------------------------------------------------------

    def get_financials(self, stock_code: str, report_type: str = "annual") -> FinancialReport:
        errors: List[Tuple[str, str, str]] = []
        for p in self.providers:
            try:
                fin = p.get_financials(stock_code, report_type)
                # 验证数据有效性：PE/PB/ROE 至少有一个非零
                if fin.pe != 0 or fin.pb != 0 or fin.roe != 0:
                    name = type(p).__name__
                    if self._active_financials != name:
                        logger.info(f"[SmartProvider] 财务数据 -> {name}")
                        self._active_financials = name
                    self._source_map.setdefault(stock_code, {})["financials"] = name
                    return fin
                # 如果所有字段都是0，说明该 provider 返回了空数据，继续尝试下一个
            except Exception as e:
                errors.append((type(p).__name__, stock_code, str(e)))
        # 所有源都失败或数据全为零
        raise DataSourceError(errors)

    def get_batch_financials(
        self, stock_codes: List[str], report_type: str = "annual"
    ) -> Dict[str, FinancialReport]:
        result: Dict[str, FinancialReport] = {}
        errors: List[Tuple[str, str, str]] = []
        for code in stock_codes:
            try:
                fin = self.get_financials(code, report_type)
                result[code] = fin
            except DataSourceError as e:
                errors.extend(e.provider_chain)
        if errors and not result:
            raise DataSourceError(errors)
        return result

    # ------------------------------------------------------------------
    # 股票列表（全量返回，不依赖 mock）
    # ------------------------------------------------------------------

    def list_stocks(self) -> List[Stock]:
        errors: List[Tuple[str, str, str]] = []
        for p in self.providers:
            try:
                stocks = p.list_stocks()
                if stocks:
                    logger.info(f"[SmartProvider] 股票列表 -> {type(p).__name__}")
                    return stocks
            except Exception as e:
                errors.append((type(p).__name__, "list_stocks", str(e)))
        raise DataSourceError(errors)


def create_default_provider() -> DataProvider:
    """创建默认的 SmartProvider，按优先级串联所有真实数据源。

    数据源优先级（按类型）：
      行情：WebProvider(腾讯+新浪) → efinance → AkShare → BaoStock
      基本面：WebProvider(腾讯PE/PB) → Tushare → JoinQuant → eFinance → AkShare → BaoStock

    局限性说明：
      - WebProvider: 腾讯行情API(PE/PB/实时)+新浪日K，无需安装，批量秒级
      - efinance: 免费无需注册，封装新浪财经；但财务字段有限
      - AkShare: 免费无需注册，数据广，但受本机代理软件影响
      - BaoStock: 免费无需注册，历史数据完整，但财务字段较少
      - Tushare/JoinQuant: 需要注册 token，数据最全（未安装token时跳过）

    如果没有任何数据源可用，抛出 RuntimeError 引导用户配置。
    """
    from .cache_provider import CacheProvider

    providers: List[DataProvider] = []
    skipped: List[Tuple[str, str]] = []  # (provider_name, reason)

    # 优先级1: WebProvider（腾讯+新浪，无需安装，批量秒级，Web API）
    try:
        from .web_provider import WebProvider
        providers.append(WebProvider())
    except ImportError as e:
        skipped.append(("WebProvider", str(e)))

    # 优先级2: Tushare（数据最全，需 token）
    try:
        from .tushare_provider import TushareProvider
        providers.append(TushareProvider())
    except (ImportError, RuntimeError) as e:
        skipped.append(("Tushare", str(e)))

    # 优先级2: JoinQuant（数据质量高，需 token）
    try:
        from .joinquant_provider import JoinQuantProvider
        providers.append(JoinQuantProvider())
    except (ImportError, RuntimeError) as e:
        skipped.append(("JoinQuant", str(e)))

    # 优先级3: efinance（免费，封装新浪财经）
    try:
        from .efinance_provider import EFinanceProvider
        providers.append(EFinanceProvider())
    except ImportError as e:
        skipped.append(("efinance", str(e)))

    # 优先级4: AkShare（免费，但受代理影响）
    try:
        from .akshare_provider import AkShareProvider
        providers.append(AkShareProvider())
    except ImportError as e:
        skipped.append(("AkShare", str(e)))

    # 优先级5: BaoStock（免费，无需注册，历史数据完整）
    try:
        from .baostock_provider import BaoStockProvider
        providers.append(BaoStockProvider())
    except ImportError as e:
        skipped.append(("BaoStock", str(e)))

    if not providers:
        lines = ["无可用的真实数据源，请先安装并配置至少一个数据源：\n"]
        lines.append("已跳过的数据源及原因：")
        for name, reason in skipped:
            lines.append(f"  - {name}: {reason}")
        lines.append("\n推荐安装顺序：")
        lines.append("  1. Tushare (数据最全): pip install tushare && 注册 https://tushare.pro/register")
        lines.append("  2. JoinQuant (免费额度): pip install jqdatasdk && 注册 https://www.joinquant.com")
        lines.append("  3. efinance (免费无需注册): pip install efinance")
        raise RuntimeError("\n".join(lines))

    if skipped:
        logger.warning("[SmartProvider] 部分数据源不可用，已跳过：")
        for name, reason in skipped:
            logger.warning(f"  - {name}: {reason}")

    logger.info(f"[SmartProvider] 初始化完成，使用 {len(providers)} 个数据源")
    return CacheProvider(SmartProvider(providers))
