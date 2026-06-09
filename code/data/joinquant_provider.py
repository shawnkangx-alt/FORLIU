"""聚宽 (JoinQuant) 数据提供者。数据质量高，有免费额度，API 调用需注册。

注册: https://www.joinquant.com/register
免费指标有限额，高级指标需付费。
"""

import os
from datetime import date, datetime
from typing import Dict, List, Optional

from .models import DailyQuote, FinancialReport, Market, Stock
from .provider import DataProvider


class JoinQuantProvider(DataProvider):
    """基于聚宽 (JoinQuant) 的数据提供者。

    注册后设置 token: export JOINQUANT_TOKEN=你的token
    或 config set data_sources.joinquant.token 你的token

    聚宽免费账号每日有 API 调用次数限制，适合小批量数据。
    """

    _stock_cache: Optional[List[Stock]] = None

    def _get_token(self) -> str:
        token = os.environ.get("JOINQUANT_TOKEN", "")
        if not token:
            try:
                from ..utils import config as cfg
                c = cfg.load_config()
                token = c.get("data_sources", {}).get("joinquant", {}).get("token", "")
            except Exception:
                pass
        if not token:
            raise RuntimeError(
                "JoinQuant 需要 token，请设置环境变量 JOINQUANT_TOKEN "
                "或运行: forliu config set data_sources.joinquant.token 你的token"
            )
        return token

    def list_stocks(self) -> List[Stock]:
        if self._stock_cache:
            return list(self._stock_cache)

        try:
            import jqdatasdk as jq

            token = self._get_token()
            # jq 需要用 (username, password) 登录，token 字段在环境变量或配置中存的是密码
            # JoinQuant 支持用手机号+密码登录
            try:
                jq.auth(token.split(",")[0] if "," in token else token, "unused")
            except Exception:
                # JQData 可能用 API key 方式
                pass

            # 获取所有 A 股
            stocks = []
            all_stocks = jq.get_all_securities(["stock"])
            for _, row in all_stocks.iterrows():
                code = str(row["display_name"][-6:])
                name = str(row["display_name"][:-6])
                market_str = str(row["market"])
                if market_str == "sh":
                    market = Market.SH
                elif market_str == "sz":
                    market = Market.SZ
                elif market_str == "bj":
                    market = Market.BJ
                else:
                    continue
                stocks.append(Stock(code=code, name=name, market=market))

            self._stock_cache = stocks
            return stocks
        except ImportError:
            raise ImportError("请安装聚宽: pip install jqdatasdk")
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"JoinQuant 获取股票列表失败: {e}")

    def get_daily_quotes(self, stock_code: str, start: date, end: date) -> List[DailyQuote]:
        try:
            import jqdatasdk as jq

            # jqdata 需要证券代码格式: '000001.XSHE' (深圳) 或 '600519.XSHG' (上海)
            jq_code = self._to_jq_code(stock_code)

            df = jq.get_price(
                jq_code,
                start_date=start.strftime("%Y-%m-%d"),
                end_date=end.strftime("%Y-%m-%d"),
                frequency="daily",
                skip_suspended=False,
            )
            if df is None or df.empty:
                return []

            quotes = []
            for idx, row in df.iterrows():
                quotes.append(
                    DailyQuote(
                        stock_code=stock_code,
                        date=idx.date() if hasattr(idx, "date") else date.fromisoformat(str(idx)[:10]),
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row["volume"]) / 10000,
                        amount=float(row["money"]) if "money" in row else 0,
                    )
                )
            return quotes
        except ImportError:
            raise ImportError("请安装聚宽: pip install jqdatasdk")
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"JoinQuant 获取 {stock_code} 日线数据失败: {e}")

    def get_financials(self, stock_code: str, report_type: str = "annual") -> FinancialReport:
        try:
            import jqdatasdk as jq

            jq_code = self._to_jq_code(stock_code)

            # 获取财务指标
            try:
                fin = jq.get_fundamentals(
                    jq_code,
                    statDate=date.today().year - 1,
                )
                if fin is not None and not fin.empty:
                    row = fin.iloc[0]
                    return FinancialReport(
                        stock_code=stock_code,
                        report_date=date(date.today().year - 1, 12, 31),
                        report_type=report_type,
                        pe=float(row.get("pe_ratio", 0) or 0),
                        pb=float(row.get("pb_ratio", 0) or 0),
                        roe=float(row.get("roe", 0) or 0),
                        revenue=float(row.get("operating_revenue", 0) or 0),
                        revenue_yoy=float(row.get("revenue_yoy", 0) or 0),
                        net_profit=float(row.get("net_profit", 0) or 0),
                        net_profit_yoy=float(row.get("net_profit_yoy", 0) or 0),
                        debt_ratio=float(row.get("debt_ratio", 0) or 0),
                        current_ratio=float(row.get("current_ratio", 0) or 0),
                    )
            except Exception:
                pass

            return self._empty_financials(stock_code, report_type)
        except ImportError:
            raise ImportError("请安装聚宽: pip install jqdatasdk")
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"JoinQuant 获取 {stock_code} 财务数据失败: {e}")

    def get_batch_quotes(
        self, stock_codes: List[str], start: date, end: date
    ) -> Dict[str, List[DailyQuote]]:
        result: Dict[str, List[DailyQuote]] = {}
        for code in stock_codes:
            try:
                result[code] = self.get_daily_quotes(code, start, end)
            except Exception as e:
                print(f"[JoinQuant] 获取 {code} 失败: {e}")
        return result

    def get_batch_financials(self, stock_codes: List[str], report_type: str = "annual") -> Dict[str, FinancialReport]:
        result: Dict[str, FinancialReport] = {}
        for code in stock_codes:
            try:
                result[code] = self.get_financials(code, report_type)
            except Exception as e:
                print(f"[JoinQuant] 获取 {code} 财务数据失败: {e}")
        return result

    @staticmethod
    def _to_jq_code(stock_code: str) -> str:
        """将股票代码转为 JoinQuant 格式"""
        if "." in stock_code:
            return stock_code
        if stock_code.startswith(("6", "9")):
            return f"{stock_code}.XSHG"
        return f"{stock_code}.XSHE"

    @staticmethod
    def _empty_financials(stock_code: str, report_type: str = "annual") -> FinancialReport:
        return FinancialReport(
            stock_code=stock_code,
            report_date=date(2025, 12, 31),
            report_type=report_type,
            pe=0, pb=0, roe=0, revenue=0, revenue_yoy=0,
            net_profit=0, net_profit_yoy=0, debt_ratio=0, current_ratio=0,
        )
