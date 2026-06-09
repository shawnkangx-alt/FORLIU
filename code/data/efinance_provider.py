"""efinance 数据提供者。封装新浪/腾讯财经接口，免费无需注册，轻量稳定。"""

import os

# 清除系统代理，避免代理节点无法访问国内金融站点
for k in list(os.environ.keys()):
    if k.lower() in ("http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(k, None)

from datetime import date, datetime
from typing import Dict, List, Optional

from .models import DailyQuote, FinancialReport, Market, Stock
from .provider import DataProvider


class EFinanceProvider(DataProvider):
    """基于 efinance 的数据提供者。封装新浪财经接口，免费无需注册。

    安装: pip install efinance
    数据来源: 新浪财经 / 腾讯财经（自动选择）
    优点: 轻量、不依赖东方财富、不受代理软件影响
    缺点: 非官方API，极端行情可能数据延迟
    """

    _stock_cache: Optional[List[Stock]] = None

    def list_stocks(self) -> List[Stock]:
        if self._stock_cache:
            return list(self._stock_cache)

        try:
            import efinance as ef

            # 获取 A 股全量股票实时行情
            df = ef.stock.get_realtime_quotes()
            if df is None or df.empty:
                raise RuntimeError("efinance 返回空数据")

            stocks = []
            for _, row in df.iterrows():
                code = str(row.get("股票代码", "")) or str(row.get("code", ""))
                name = str(row.get("股票名称", "")) or str(row.get("name", ""))
                if not code or code == "nan":
                    continue
                # 过滤掉指数和基金
                if not (code.startswith(("6", "0", "3", "8", "4"))):
                    continue
                if code.startswith(("6", "9")):
                    market = Market.SH
                elif code.startswith(("0", "3")):
                    market = Market.SZ
                elif code.startswith(("8", "4")):
                    market = Market.BJ
                else:
                    market = Market.SZ
                stocks.append(Stock(code=code, name=name, market=market))

            self._stock_cache = stocks
            return stocks
        except ImportError:
            raise ImportError("请安装 efinance: pip install efinance")
        except Exception as e:
            raise RuntimeError(f"efinance 获取股票列表失败: {e}")

    def get_daily_quotes(self, stock_code: str, start: date, end: date) -> List[DailyQuote]:
        try:
            import efinance as ef

            # efinance.get_hist 返回 DataFrame，index 是日期
            df = ef.stock.get_hist(
                code=stock_code,
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
            )
            if df is None or df.empty:
                return []

            quotes = []
            for idx, row in df.iterrows():
                # index 可能是 datetime 或 string
                if hasattr(idx, "date"):
                    d = idx.date()
                else:
                    d = date.fromisoformat(str(idx)[:10])

                # 兼容不同列名版本
                open_p = float(row.get("开盘", row.get("open", 0)) or 0)
                high = float(row.get("最高", row.get("high", 0)) or 0)
                low = float(row.get("最低", row.get("low", 0)) or 0)
                close = float(row.get("收盘", row.get("close", 0)) or 0)
                vol = float(row.get("成交量", row.get("volume", 0)) or 0)
                amount = float(row.get("成交额", row.get("amount", 0)) or 0)

                quotes.append(
                    DailyQuote(
                        stock_code=stock_code,
                        date=d,
                        open=open_p,
                        high=high,
                        low=low,
                        close=close,
                        volume=vol / 10000,
                        amount=amount,
                    )
                )
            return quotes
        except ImportError:
            raise ImportError("请安装 efinance: pip install efinance")
        except Exception as e:
            raise RuntimeError(f"efinance 获取 {stock_code} 日线数据失败: {e}")

    def get_financials(self, stock_code: str, report_type: str = "annual") -> FinancialReport:
        try:
            import efinance as ef

            fin_df = ef.stock.get_indicator(stock_code, n=1)
            if fin_df is not None and not fin_df.empty:
                row = fin_df.iloc[0]
                return FinancialReport(
                    stock_code=stock_code,
                    report_date=date(date.today().year, 12, 31),
                    report_type=report_type,
                    pe=float(row.get("市盈率", row.get("PE", 0)) or 0),
                    pb=float(row.get("市净率", row.get("PB", 0)) or 0),
                    roe=float(row.get("净资产收益率", row.get("ROE", 0)) or 0),
                    revenue=float(row.get("营业总收入", row.get("TotalRevenue", 0)) or 0),
                    revenue_yoy=float(row.get("营收同比增长", row.get("RevenueYOY", 0)) or 0),
                    net_profit=float(row.get("净利润", row.get("NetProfit", 0)) or 0),
                    net_profit_yoy=float(row.get("净利润同比增长", row.get("ProfitYOY", 0)) or 0),
                    debt_ratio=float(row.get("资产负债率", row.get("DebtAssetRatio", 0)) or 0),
                    current_ratio=float(row.get("流动比率", row.get("CurrentRatio", 0)) or 0),
                )
            return self._empty_financials(stock_code, report_type)
        except ImportError:
            raise ImportError("请安装 efinance: pip install efinance")
        except Exception as e:
            raise RuntimeError(f"efinance 获取 {stock_code} 财务数据失败: {e}")

    def get_batch_quotes(
        self, stock_codes: List[str], start: date, end: date
    ) -> Dict[str, List[DailyQuote]]:
        result: Dict[str, List[DailyQuote]] = {}
        for code in stock_codes:
            try:
                result[code] = self.get_daily_quotes(code, start, end)
            except Exception as e:
                print(f"[efinance] 获取 {code} 失败: {e}")
        return result

    def get_batch_financials(self, stock_codes: List[str], report_type: str = "annual") -> Dict[str, FinancialReport]:
        result: Dict[str, FinancialReport] = {}
        for code in stock_codes:
            try:
                result[code] = self.get_financials(code, report_type)
            except Exception as e:
                print(f"[efinance] 获取 {code} 财务数据失败: {e}")
        return result

    @staticmethod
    def _empty_financials(stock_code: str, report_type: str = "annual") -> FinancialReport:
        return FinancialReport(
            stock_code=stock_code,
            report_date=date(2025, 12, 31),
            report_type=report_type,
            pe=0, pb=0, roe=0, revenue=0, revenue_yoy=0,
            net_profit=0, net_profit_yoy=0, debt_ratio=0, current_ratio=0,
        )
