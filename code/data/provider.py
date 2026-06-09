from abc import ABC, abstractmethod
from datetime import date
from typing import Dict, List

from .models import DailyQuote, FinancialReport, Stock


class DataProvider(ABC):
    """股票数据提供者抽象接口。"""

    @abstractmethod
    def list_stocks(self) -> List[Stock]:
        """返回可用的股票池。"""
        ...

    @abstractmethod
    def get_daily_quotes(self, stock_code: str, start: date, end: date) -> List[DailyQuote]:
        """获取单只股票的日线行情数据。"""
        ...

    @abstractmethod
    def get_financials(self, stock_code: str, report_type: str = "annual") -> FinancialReport:
        """获取单只股票的财务数据。

        Args:
            stock_code: 股票代码
            report_type: 报告类型，annual(年度)|quarterly(季度)|ttm(滚动全年)
        """
        ...

    @abstractmethod
    def get_batch_quotes(
        self, stock_codes: List[str], start: date, end: date
    ) -> Dict[str, List[DailyQuote]]:
        """批量获取日线行情数据。"""
        ...

    @abstractmethod
    def get_batch_financials(
        self, stock_codes: List[str], report_type: str = "annual"
    ) -> Dict[str, FinancialReport]:
        """批量获取财务数据。"""
        ...
