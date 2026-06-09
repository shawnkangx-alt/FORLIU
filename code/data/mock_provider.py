import random
from datetime import date, timedelta
from typing import Dict, List, Optional

from .models import DailyQuote, FinancialReport, Market, Stock
from .provider import DataProvider


_STOCK_POOL = [
    ("600519", "贵州茅台", Market.SH),
    ("000858", "五粮液", Market.SZ),
    ("601318", "中国平安", Market.SH),
    ("000333", "美的集团", Market.SZ),
    ("600036", "招商银行", Market.SH),
    ("002415", "海康威视", Market.SZ),
    ("600276", "恒瑞医药", Market.SH),
    ("000651", "格力电器", Market.SZ),
    ("601888", "中国中免", Market.SH),
    ("002714", "牧原股份", Market.SZ),
    ("600900", "长江电力", Market.SH),
    ("000568", "泸州老窖", Market.SZ),
    ("601012", "隆基绿能", Market.SH),
    ("002475", "立讯精密", Market.SZ),
    ("600809", "山西汾酒", Market.SH),
    ("000725", "京东方A", Market.SZ),
    ("601166", "兴业银行", Market.SH),
    ("002594", "比亚迪", Market.SZ),
    ("600030", "中信证券", Market.SH),
    ("000063", "中兴通讯", Market.SZ),
    ("601398", "工商银行", Market.SH),
    ("002230", "科大讯飞", Market.SZ),
    ("600887", "伊利股份", Market.SH),
    ("000002", "万科A", Market.SZ),
    ("601688", "华泰证券", Market.SH),
    ("002142", "宁波银行", Market.SZ),
    ("600585", "海螺水泥", Market.SH),
    ("000792", "盐湖股份", Market.SZ),
    ("601899", "紫金矿业", Market.SH),
    ("002352", "顺丰控股", Market.SZ),
    ("600031", "三一重工", Market.SH),
    ("000538", "云南白药", Market.SZ),
    ("601857", "中国石油", Market.SH),
    ("002304", "洋河股份", Market.SZ),
    ("600048", "保利发展", Market.SH),
    ("000625", "长安汽车", Market.SZ),
    ("601066", "中信建投", Market.SH),
    ("002271", "东方雨虹", Market.SZ),
    ("600436", "片仔癀", Market.SH),
    ("000776", "广发证券", Market.SZ),
    ("601390", "中国中铁", Market.SH),
    ("002049", "紫光国微", Market.SZ),
    ("600346", "恒力石化", Market.SH),
    ("000100", "TCL科技", Market.SZ),
    ("601919", "中远海控", Market.SH),
    ("002371", "北方华创", Market.SZ),
    ("600438", "通威股份", Market.SH),
    ("000895", "双汇发展", Market.SZ),
    ("601728", "中国电信", Market.SH),
    ("002027", "分众传媒", Market.SZ),
]


class MockDataProvider(DataProvider):
    """模拟数据提供者，使用固定种子生成确定性数据。"""

    def __init__(self, seed: int = 42):
        self._rng = random.Random(seed)
        self._stocks = [Stock(code, name, market) for code, name, market in _STOCK_POOL]
        self._stock_codes = {s.code for s in self._stocks}
        self._price_seeds: Dict[str, float] = {}
        self._vol_seeds: Dict[str, float] = {}
        for s in self._stocks:
            code_rng = random.Random(hash(s.code) ^ seed)
            self._price_seeds[s.code] = code_rng.uniform(5, 200)
            self._vol_seeds[s.code] = code_rng.uniform(0.5, 2.0)

    def list_stocks(self) -> List[Stock]:
        return list(self._stocks)

    def get_daily_quotes(self, stock_code: str, start: date, end: date) -> List[DailyQuote]:
        if stock_code not in self._stock_codes:
            return []
        return self._generate_quotes(stock_code, start, end)

    def get_batch_quotes(
        self, stock_codes: List[str], start: date, end: date
    ) -> Dict[str, List[DailyQuote]]:
        return {
            code: self.get_daily_quotes(code, start, end)
            for code in stock_codes
            if code in self._stock_codes
        }

    def get_financials(self, stock_code: str, report_type: str = "annual") -> FinancialReport:
        rng = random.Random(hash(stock_code + f"_{report_type}") ^ 42)
        return FinancialReport(
            stock_code=stock_code,
            report_date=date(2025, 12, 31),
            report_type=report_type,
            pe=round(rng.uniform(8, 80), 2),
            pb=round(rng.uniform(0.8, 8), 2),
            roe=round(rng.uniform(3, 35), 2),
            revenue=round(rng.uniform(1e9, 5e11), 2),
            revenue_yoy=round(rng.uniform(-15, 40), 2),
            net_profit=round(rng.uniform(1e8, 5e10), 2),
            net_profit_yoy=round(rng.uniform(-20, 50), 2),
            debt_ratio=round(rng.uniform(10, 80), 2),
            current_ratio=round(rng.uniform(0.5, 5), 2),
        )

    def get_batch_financials(
        self, stock_codes: List[str], report_type: str = "annual"
    ) -> Dict[str, FinancialReport]:
        return {code: self.get_financials(code, report_type) for code in stock_codes if code in self._stock_codes}

    def _generate_quotes(self, stock_code: str, start: date, end: date) -> List[DailyQuote]:
        base_price = self._price_seeds[stock_code]
        base_vol = self._vol_seeds[stock_code]
        day_rng = random.Random(hash(stock_code) ^ 42)

        quotes: List[DailyQuote] = []
        current = start
        prev_close = base_price
        while current <= end:
            if current.weekday() < 5:
                change_pct = day_rng.gauss(0, 0.02)
                close = round(prev_close * (1 + change_pct), 2)
                intraday_range = close * day_rng.uniform(0.005, 0.03)
                open_price = round(close - intraday_range * day_rng.uniform(-0.5, 0.5), 2)
                high = round(max(open_price, close) + intraday_range * day_rng.random(), 2)
                low = round(min(open_price, close) - intraday_range * day_rng.random(), 2)

                vol = max(0, day_rng.gauss(base_vol, base_vol * 0.3))
                amount = round(vol * close * 1e7, 2)

                quotes.append(
                    DailyQuote(
                        stock_code=stock_code,
                        date=current,
                        open=open_price,
                        high=high,
                        low=low,
                        close=close,
                        volume=round(vol, 4),
                        amount=amount,
                    )
                )
                prev_close = close
            current += timedelta(days=1)

        return quotes
