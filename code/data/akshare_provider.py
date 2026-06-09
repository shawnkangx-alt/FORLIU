"""AkShare 数据提供者。完全免费，无需注册，覆盖 A 股全品类数据。"""

import os

# 清除系统代理，避免代理节点无法访问国内金融站点
for k in list(os.environ.keys()):
    if k.lower() in ("http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(k, None)

from datetime import date, datetime
from typing import Dict, List, Optional

from .models import DailyQuote, FinancialReport, Market, Stock
from .provider import DataProvider


class AkShareProvider(DataProvider):
    """基于 AkShare 的数据提供者。零配置、免费、开箱即用。"""

    _stock_cache: Optional[List[Stock]] = None
    _stock_cache_time: Optional[datetime] = None

    def list_stocks(self) -> List[Stock]:
        if self._stock_cache and self._stock_cache_time:
            if (datetime.now() - self._stock_cache_time).seconds < 3600:
                return list(self._stock_cache)  # type: ignore[arg-type]

        try:
            import akshare as ak

            df = ak.stock_zh_a_spot_em()
            stocks = []
            for _, row in df.iterrows():
                code = str(row["代码"])
                name = str(row["名称"])
                if code.startswith("6"):
                    market = Market.SH
                elif code.startswith(("0", "3")):
                    market = Market.SZ
                elif code.startswith(("8", "4")):
                    market = Market.BJ
                else:
                    market = Market.SZ
                stocks.append(Stock(code=code, name=name, market=market))

            self._stock_cache = stocks
            self._stock_cache_time = datetime.now()
            return stocks
        except ImportError:
            raise ImportError("请安装 akshare: pip install akshare")
        except Exception as e:
            raise RuntimeError(f"AkShare 获取股票列表失败: {e}")

    def get_daily_quotes(self, stock_code: str, start: date, end: date) -> List[DailyQuote]:
        try:
            import akshare as ak

            period = "daily"
            df = ak.stock_zh_a_hist(
                symbol=stock_code,
                period=period,
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                adjust="qfq",
            )

            if df.empty:
                return []

            quotes = []
            for _, row in df.iterrows():
                quotes.append(
                    DailyQuote(
                        stock_code=stock_code,
                        date=date.fromisoformat(str(row["日期"])[:10]),
                        open=float(row["开盘"]),
                        high=float(row["最高"]),
                        low=float(row["最低"]),
                        close=float(row["收盘"]),
                        volume=float(row["成交量"]) / 10000,
                        amount=float(row["成交额"]),
                    )
                )
            return quotes
        except ImportError:
            raise ImportError("请安装 akshare: pip install akshare")
        except Exception as e:
            raise RuntimeError(f"AkShare 获取 {stock_code} 日线数据失败: {e}")

    def get_financials(self, stock_code: str, report_type: str = "annual") -> FinancialReport:
        try:
            import akshare as ak

            indicator_map = {
                "annual": "按年度",
                "quarterly": "按单季度",
                "ttm": "按年度",  # TTM 用年度数据滚动计算
            }
            indicator = indicator_map.get(report_type, "按年度")
            df = ak.stock_fancial_abstract_ths(symbol=stock_code, indicator=indicator)
            if df is None or df.empty:
                return self._empty_financials(stock_code, report_type)

            latest = df.iloc[0]
            report_date_str = str(latest.get("报告期", "2025-12-31"))
            try:
                report_date = date.fromisoformat(report_date_str[:10])
            except (ValueError, TypeError):
                report_date = date(2025, 12, 31)

            def parse_pct(v):
                """解析百分比字符串，如 '20.24%' -> 20.24"""
                if isinstance(v, str) and "%" in v:
                    return float(v.replace("%", ""))
                return float(v or 0)

            return FinancialReport(
                stock_code=stock_code,
                report_date=report_date,
                report_type=report_type,
                pe=float(latest.get("市盈率", 0) or 0),
                pb=float(latest.get("市净率", 0) or 0),
                roe=parse_pct(latest.get("净资产收益率", 0)),
                revenue=float(latest.get("营业总收入", 0) or 0),
                revenue_yoy=parse_pct(latest.get("营业总收入同比增长", 0)),
                net_profit=float(latest.get("净利润", 0) or 0),
                net_profit_yoy=parse_pct(latest.get("净利润同比增长", 0)),
                debt_ratio=parse_pct(latest.get("资产负债率", 0)),
                current_ratio=float(latest.get("流动比率", 0) or 0),
            )
        except ImportError:
            raise ImportError("请安装 akshare: pip install akshare")
        except Exception as e:
            raise RuntimeError(f"AkShare 获取 {stock_code} 财务数据失败: {e}")

    def get_batch_quotes(
        self, stock_codes: List[str], start: date, end: date
    ) -> Dict[str, List[DailyQuote]]:
        result: Dict[str, List[DailyQuote]] = {}
        for code in stock_codes:
            try:
                result[code] = self.get_daily_quotes(code, start, end)
            except Exception as e:
                print(f"[AkShare] 获取 {code} 失败: {e}")
        return result

    def get_batch_financials(
        self, stock_codes: List[str], report_type: str = "annual"
    ) -> Dict[str, FinancialReport]:
        result: Dict[str, FinancialReport] = {}
        for code in stock_codes:
            try:
                result[code] = self.get_financials(code, report_type)
            except Exception as e:
                print(f"[AkShare] 获取 {code} 财务数据失败: {e}")
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
