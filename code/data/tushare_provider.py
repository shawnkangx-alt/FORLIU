"""Tushare 数据提供者。数据最全，技术面+基本面都有，需要注册获取 token（免费送120积分）。"""

import os
from datetime import date, datetime
from typing import Dict, List, Optional

from .models import DailyQuote, FinancialReport, Market, Stock
from .provider import DataProvider


class TushareProvider(DataProvider):
    """基于 Tushare Pro 的数据提供者。数据最全，但需要注册获取 token。

    注册: https://tushare.pro/register
    获取 token 后设置环境变量: export TUSHARE_TOKEN=你的token
    或 config set data_sources.tushare.token 你的token
    """

    _token: Optional[str] = None
    _stock_cache: Optional[List[Stock]] = None

    def _get_token(self) -> str:
        if self._token:
            return self._token
        # 优先读环境变量，再读配置文件
        token = os.environ.get("TUSHARE_TOKEN", "")
        if not token:
            try:
                from ..utils import config as cfg
                c = cfg.load_config()
                token = c.get("data_sources", {}).get("tushare", {}).get("token", "")
            except Exception:
                pass
        if not token:
            raise RuntimeError(
                "Tushare 需要 token，请设置环境变量 TUSHARE_TOKEN "
                "或运行: forliu config set data_sources.tushare.token 你的token"
            )
        self._token = token
        return token

    def _init_tushare(self):
        import tushare as ts
        token = self._get_token()
        ts.set_token(token)
        return ts.pro_api(token)

    def list_stocks(self) -> List[Stock]:
        if self._stock_cache:
            return list(self._stock_cache)

        try:
            import tushare as ts
            api = self._init_tushare()
            df = api.stock_basic(exchange="", list_status="L", fields="ts_code,symbol,name,market")
            stocks = []
            for _, row in df.iterrows():
                code = str(row["symbol"])
                name = str(row["name"])
                exchange = str(row.get("market", "SZ"))
                if exchange == "SH" or code.startswith(("6", "9")):
                    market = Market.SH
                elif exchange == "SZ" or code.startswith(("0", "3")):
                    market = Market.SZ
                elif exchange == "BJ" or code.startswith(("8", "4")):
                    market = Market.BJ
                else:
                    market = Market.SZ
                stocks.append(Stock(code=code, name=name, market=market))

            self._stock_cache = stocks
            return stocks
        except ImportError:
            raise ImportError("请安装 tushare: pip install tushare")
        except RuntimeError:
            raise  # token 未配置
        except Exception as e:
            raise RuntimeError(f"Tushare 获取股票列表失败: {e}")

    def get_daily_quotes(self, stock_code: str, start: date, end: date) -> List[DailyQuote]:
        try:
            import tushare as ts

            api = self._init_tushare()
            # Tushare 需要 ts_code 格式: 600519.SH
            ts_code = self._to_ts_code(stock_code)
            df = api.query(
                "daily",
                ts_code=ts_code,
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
            )
            if df is None or df.empty:
                return []

            quotes = []
            for _, row in df.sort_values("trade_date").iterrows():
                quotes.append(
                    DailyQuote(
                        stock_code=stock_code,
                        date=date.fromisoformat(str(row["trade_date"])[:8]),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row["vol"]) / 10000,
                        amount=float(row["amount"]) if "amount" in row else 0,
                    )
                )
            return quotes
        except ImportError:
            raise ImportError("请安装 tushare: pip install tushare")
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Tushare 获取 {stock_code} 日线数据失败: {e}")

    def get_financials(self, stock_code: str, report_type: str = "annual") -> FinancialReport:
        try:
            import tushare as ts

            api = self._init_tushare()
            ts_code = self._to_ts_code(stock_code)

            # 尝试获取财务数据（需要足够积分）
            fin_df = None
            try:
                fin_df = api.fina_indicator(
                    ts_code=ts_code, start_date="20240101", limit=4
                )
            except Exception:
                pass

            # 尝试获取利润表
            income_df = None
            try:
                income_df = api.income(
                    ts_code=ts_code, start_date="20240101", limit=4
                )
            except Exception:
                pass

            if fin_df is not None and not fin_df.empty:
                latest = fin_df.iloc[0]
                return FinancialReport(
                    stock_code=stock_code,
                    report_date=date.fromisoformat(str(latest.get("end_date", "20251231"))[:8]),
                    report_type=report_type,
                    pe=float(latest.get("pe", 0) or 0),
                    pb=float(latest.get("pb", 0) or 0),
                    roe=float(latest.get("roe", 0) or 0),
                    revenue=float(latest.get("revenue", 0) or 0),
                    revenue_yoy=float(latest.get("revenue_yoy", 0) or 0),
                    net_profit=float(latest.get("net_profit", 0) or 0),
                    net_profit_yoy=float(latest.get("np_yoy", 0) or 0),
                    debt_ratio=float(latest.get("debt_to_assets", 0) or 0),
                    current_ratio=float(latest.get("current_ratio", 0) or 0),
                )

            return self._empty_financials(stock_code, report_type)
        except ImportError:
            raise ImportError("请安装 tushare: pip install tushare")
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Tushare 获取 {stock_code} 财务数据失败: {e}")

    def get_batch_quotes(
        self, stock_codes: List[str], start: date, end: date
    ) -> Dict[str, List[DailyQuote]]:
        result: Dict[str, List[DailyQuote]] = {}
        for code in stock_codes:
            try:
                result[code] = self.get_daily_quotes(code, start, end)
            except Exception as e:
                print(f"[Tushare] 获取 {code} 失败: {e}")
        return result

    def get_batch_financials(self, stock_codes: List[str], report_type: str = "annual") -> Dict[str, FinancialReport]:
        result: Dict[str, FinancialReport] = {}
        for code in stock_codes:
            try:
                result[code] = self.get_financials(code, report_type)
            except Exception as e:
                print(f"[Tushare] 获取 {code} 财务数据失败: {e}")
        return result

    @staticmethod
    def _to_ts_code(stock_code: str) -> str:
        """将股票代码转为 Tushare 格式 (600519.SH)"""
        if "." in stock_code:
            return stock_code
        if stock_code.startswith(("6", "9")):
            return f"{stock_code}.SH"
        return f"{stock_code}.SZ"

    @staticmethod
    def _empty_financials(stock_code: str, report_type: str = "annual") -> FinancialReport:
        return FinancialReport(
            stock_code=stock_code,
            report_date=date(2025, 12, 31),
            report_type=report_type,
            pe=0, pb=0, roe=0, revenue=0, revenue_yoy=0,
            net_profit=0, net_profit_yoy=0, debt_ratio=0, current_ratio=0,
        )
