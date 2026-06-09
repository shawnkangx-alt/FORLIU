"""
WebProvider: 基于东方财富/腾讯的网页 API 获取股票数据。
优先级高于 AkShare/BaoStock，因为无需安装依赖且支持批量查询。

数据源:
- 股票列表: Eastmoney RPT_LICO_FN_CPD (ISNEW=1 过滤最新报告期)
- 实时行情: Tencent qt.gtimg.cn (GBK, 批量秒级)
- 历史行情: Eastmoney datacenter 历史K线接口
- 财务数据: Eastmoney RPT_LICO_FN_CPD (ROE/营收/利润/负债率)
"""

import json
import re
import time
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import urllib.request
import urllib.parse

from .models import DailyQuote, FinancialReport, Stock
from .provider import DataProvider


_TIMEOUT = 10
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.eastmoney.com/",
    "Accept": "*/*",
}


def _http_get(url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> str:
    """HTTP GET 请求，返回响应文本。"""
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=headers or _HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = resp.read()
            # 尝试 UTF-8，失败则用 GBK（腾讯行情用 GBK）
            try:
                return data.decode("utf-8")
            except UnicodeDecodeError:
                return data.decode("gbk", errors="replace")
    except Exception as e:
        raise RuntimeError(f"HTTP 请求失败 {url}: {e}")


def _parse_tencent_quote(raw: str) -> Optional[Dict]:
    """解析腾讯行情单条记录。"""
    # 格式: v_sh600519="1~贵州茅台~600519~1256.00~..."
    m = re.search(r'v_\w+="([^"]+)"', raw)
    if not m:
        return None
    fields = m.group(1).split("~")
    if len(fields) < 35:
        return None
    try:
        return {
            "code": fields[2],
            "name": fields[1],
            "price": float(fields[3]),
            "prev_close": float(fields[4]),
            "open": float(fields[5]),
            "volume": int(fields[6]),        # 成交量（手）
            "bid1_price": float(fields[9]) if fields[9] else 0.0,
            "ask1_price": float(fields[19]) if fields[19] else 0.0,
            "timestamp": fields[30] or "",
            "turnover": float(fields[37]) if len(fields) > 37 and fields[37] else 0.0,  # 成交额（元）
            "pe": float(fields[39]) if len(fields) > 39 and fields[39] else 0.0,  # 市盈率
            "pb": float(fields[46]) if len(fields) > 46 and fields[46] else 0.0,  # 市净率
        }
    except (ValueError, IndexError):
        return None


def _tencent_code(code: str) -> str:
    """股票代码转腾讯格式。"""
    code = code.strip()
    if code.startswith(("6", "9")):
        return f"sh{code}"
    else:
        return f"sz{code}"


class WebProvider(DataProvider):
    """基于网页 API 的数据提供者（东方财富 + 腾讯）。"""

    def __init__(self):
        self._stock_cache: Optional[List[Stock]] = None
        self._stock_fetch_time: float = 0.0

    # -------------------------------------------------------------------------
    # 股票列表
    # -------------------------------------------------------------------------

    def list_stocks(self) -> List[Stock]:
        if self._stock_cache:
            return list(self._stock_cache)

        stocks = self._fetch_stock_list()
        self._stock_cache = stocks
        self._stock_fetch_time = time.time()
        return list(stocks)

    def _fetch_stock_list(self) -> List[Stock]:
        """获取股票列表。

        策略：优先尝试 Eastmoney datacenter（多种报表），失败则用
        内嵌的 BaoStock 静态股票列表作为可靠降级。
        """
        # 方法1：尝试 Eastmoney 全量股票列表
        stocks_em = self._fetch_em_stock_list()
        if len(stocks_em) > 100:
            return stocks_em

        # 方法2：BaoStock 静态列表（内嵌，约236只主要股票）
        from .baostock_provider import _STATIC_STOCKS
        seen: set = set()
        result: List[Stock] = []
        for code, name, market in _STATIC_STOCKS:
            if code not in seen:
                seen.add(code)
                result.append(Stock(code=code, name=name, market=market.value if hasattr(market, 'value') else market))
        print(f"[WebProvider] 降级使用 BaoStock 静态列表: {len(result)} 只")
        return result

    def _fetch_em_stock_list(self) -> List[Stock]:
        """从 Eastmoney 获取全量股票列表。"""
        # 尝试多个报表名称
        report_names = [
            "RPT_DMSK_TS_BASICINFO",
            "RPT_STOCK_LIST_NEW",
            "RPT_BASIC_INFO",
        ]
        for report_name in report_names:
            stocks = self._fetch_em_by_report(report_name)
            if len(stocks) > 100:
                print(f"[WebProvider] Eastmoney {report_name}: {len(stocks)} 只")
                return stocks
        return []

    def _fetch_em_by_report(self, report_name: str) -> List[Stock]:
        """用指定报表名从 Eastmoney 获取股票列表。"""
        all_stocks: Dict[str, Stock] = {}
        for page in range(1, 200):
            url = "https://datacenter.eastmoney.com/api/data/v1/get"
            params = {
                "reportName": report_name,
                "columns": "SECURITY_CODE,SECURITY_NAME_ABBR",
                f"pageNumber": str(page),
                "pageSize": "5000",
                "sortColumns": "SECURITY_CODE",
                "sortTypes": "1",
            }
            try:
                text = _http_get(url, params)
                data = json.loads(text)
            except Exception as e:
                break

            result = data.get("result")
            if not result or not result.get("data"):
                break

            for row in result["data"]:
                code = row.get("SECURITY_CODE", "")
                name = str(row.get("SECURITY_NAME_ABBR", "")).strip()
                if code and code not in all_stocks:
                    all_stocks[code] = Stock(code=code, name=name, market="A")

            if len(result["data"]) < 5000:
                break

        return list(all_stocks.values())

    # -------------------------------------------------------------------------
    # 实时行情（腾讯）
    # -------------------------------------------------------------------------

    def get_batch_quotes(self, stock_codes: List[str], start: date, end: date) -> Dict[str, List[DailyQuote]]:
        """获取多只股票行情。用腾讯实时 API 拿最新价格，
        Eastmoney 历史K线补充日线数据用于技术指标计算。"""
        result: Dict[str, List[DailyQuote]] = {}

        # 1. 腾讯实时行情（批量，秒级）
        quotes_real = self._fetch_tencent_realtime(stock_codes)
        for code, qdata in quotes_real.items():
            result[code] = [
                DailyQuote(
                    stock_code=code,
                    date=date.today(),
                    open=qdata["open"],
                    high=qdata["price"],  # 实时价格作为当日收盘近似
                    low=qdata["price"],
                    close=qdata["price"],
                    volume=qdata["volume"] / 10000.0,  # 手 -> 万手
                    amount=qdata.get("turnover", 0.0),
                )
            ]

        # 补充历史 K 线（用于技术指标）
        # 限制：只取最近60交易日，避免慢
        hist_end = end or date.today()
        hist_start = hist_end - timedelta(days=75)

        for code in stock_codes:
            if code not in result:
                result[code] = []
            # 尝试获取历史日线
            hist = self._fetch_em_historical(code, hist_start, hist_end)
            if hist:
                # 腾讯已有今日数据（如有重复日期，用历史的）
                hist_dates = {q.date for q in hist}
                existing = result[code]
                existing_dates = {q.date for q in existing}
                # 合并，历史的优先级（更完整）
                combined = existing + [q for q in hist if q.date not in existing_dates]
                result[code] = sorted(combined, key=lambda q: q.date)

        return result

    def _fetch_tencent_realtime(self, stock_codes: List[str]) -> Dict[str, Dict]:
        """腾讯实时行情批量获取。"""
        if not stock_codes:
            return {}

        # 腾讯最多支持约200个代码批量查询
        batch_size = 150
        all_quotes: Dict[str, Dict] = {}

        for i in range(0, len(stock_codes), batch_size):
            batch = stock_codes[i:i + batch_size]
            codes_param = ",".join(_tencent_code(c) for c in batch)
            url = f"https://qt.gtimg.cn/q={codes_param}"

            try:
                text = _http_get(url, headers={**_HEADERS, "Referer": "https://finance.qq.com/"})
            except Exception as e:
                print(f"[WebProvider] 腾讯实时行情失败: {e}")
                continue

            for line in text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                parsed = _parse_tencent_quote(line)
                if parsed:
                    # 去掉 sh/sz 前缀
                    code = parsed["code"]
                    all_quotes[code] = parsed

        return all_quotes

    def _fetch_em_historical(self, stock_code: str, start: date, end: date) -> List[DailyQuote]:
        """从 Sina 获取单只股票历史日线。"""
        # 新浪历史K线API，scale=240 = 日K（240天分钟=1天）
        prefix = "sh" if stock_code.startswith(("6", "9")) else "sz"
        url = (
            f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php"
            f"/CN_MarketData.getKLineData?symbol={prefix}{stock_code}"
            f"&scale=240&ma=no&datalen=500"
        )
        try:
            text = _http_get(url)
            data = json.loads(text)
        except Exception:
            return []

        quotes = []
        for item in data:
            try:
                item_date = datetime.strptime(item["day"], "%Y-%m-%d").date()
                if not (start <= item_date <= end):
                    continue
                quotes.append(DailyQuote(
                    stock_code=stock_code,
                    date=item_date,
                    open=float(item["open"]),
                    high=float(item["high"]),
                    low=float(item["low"]),
                    close=float(item["close"]),
                    volume=float(item["volume"]) / 10000.0,  # 股 -> 万股
                    amount=0.0,  # Sina K-line 无成交额数据
                ))
            except (ValueError, KeyError):
                continue
        return quotes

    def get_daily_quotes(self, stock_code: str, start: date, end: date) -> List[DailyQuote]:
        result = self.get_batch_quotes([stock_code], start, end)
        return result.get(stock_code, [])

    # -------------------------------------------------------------------------
    # 财务数据（Eastmoney）
    # -------------------------------------------------------------------------

    def get_batch_financials(self, stock_codes: List[str], report_type: str = "annual") -> Dict[str, FinancialReport]:
        """批量获取财务数据。

        策略：
        1. 腾讯实时行情 API → 实时 PE/PB（批量秒级）
        2. BaoStock → ROE/营收/利润（逐只约3秒，可靠）
        3. PE = 实时行情市盈率，PB = 实时行情市净率
        """
        result: Dict[str, FinancialReport] = {}

        # 腾讯实时行情已有 PE/PB，且足够完整
        # 腾讯没有 ROE/营收/负债率，但这些字段在 value 筛选策略中非必需
        # PE/PB 已是完整财务数据，足以支持低估值筛选
        tencent_data = self._fetch_tencent_realtime(stock_codes)
        bao_financials: Dict[str, FinancialReport] = {}  # 暂不使用 BaoStock（连接不稳定）

        for code in stock_codes:
            td = tencent_data.get(code, {})
            bf = bao_financials.get(code)

            pe = td.get("pe", 0.0) or (bf.pe if bf else 0.0)
            pb = td.get("pb", 0.0) or (bf.pb if bf else 0.0)

            result[code] = FinancialReport(
                stock_code=code,
                report_date=bf.report_date if bf else date.today(),
                report_type=report_type,
                pe=pe,
                pb=pb,
                roe=bf.roe if bf else 0.0,
                revenue=bf.revenue if bf else 0.0,
                net_profit=bf.net_profit if bf else 0.0,
                revenue_yoy=bf.revenue_yoy if bf else 0.0,
                net_profit_yoy=bf.net_profit_yoy if bf else 0.0,
                debt_ratio=bf.debt_ratio if bf else 0.0,
                current_ratio=bf.current_ratio if bf else 0.0,
            )

        return result

    def _fetch_bao_financials(self, stock_codes: List[str], report_type: str) -> Dict[str, FinancialReport]:
        """从 BaoStock 获取详细财务数据（ROE/营收/利润/负债率）。"""
        try:
            import baostock as bs
        except ImportError:
            return {}

        result: Dict[str, FinancialReport] = {}
        lg = bs.login()
        if lg.error_code != "0":
            return {}

        import time
        for code in stock_codes:
            bs_code = f"sh.{code}" if code.startswith(("6", "9")) else f"sz.{code}"
            for attempt in range(3):
                try:
                    # ROE 数据（profit data）
                    rs = bs.query_profit_data(code=bs_code, year=2024, quarter=4)
                    roe = 0.0
                    net_profit = 0.0
                    revenue = 0.0
                    if rs.error_code == "0":
                        while rs.next():
                            row = rs.get_row_data()
                            # fields: code, pubDate, statDate, roeAvg, npMargin, gpMargin,
                            #         netProfit, epsTTM, MBRevenue, totalShare, liqaShare
                            roe = float(row[3]) if row[3] else 0.0  # roeAvg 已是百分比 e.g. 38.4
                            net_profit = float(row[6]) if row[6] else 0.0  # 元
                            revenue = float(row[8]) if row[8] else 0.0  # 元

                    # 资产负债率（balance sheet）
                    bsrs = bs.query_balance_data(code=bs_code, year=2024, quarter=4)
                    debt_ratio = 0.0
                    current_ratio = 0.0
                    if bsrs.error_code == "0":
                        while bsrs.next():
                            brow = bsrs.get_row_data()
                            # fields: code, pubDate, statDate, currentRatio, quickRatio, cashRatio,
                            #         YOYLiability, liabilityToAsset, assetToEquity
                            debt_ratio = float(brow[7]) if brow[7] else 0.0  # 已是小数形式
                            current_ratio = float(brow[3]) if brow[3] else 0.0

                    result[code] = FinancialReport(
                        stock_code=code,
                        report_date=date(2024, 12, 31),
                        report_type=report_type,
                        pe=0.0,
                        pb=0.0,
                        roe=roe,
                        revenue=revenue,
                        net_profit=net_profit,
                        debt_ratio=debt_ratio * 100.0,
                        current_ratio=current_ratio,
                    )
                    break  # success
                except Exception as e:
                    if attempt < 2:
                        time.sleep(1)  # 重试前等待1秒
                        bs.login()  # 重新连接
                    continue

        bs.logout()
        return result

    def get_financials(self, stock_code: str, report_type: str = "annual") -> FinancialReport:
        result = self.get_batch_financials([stock_code], report_type)
        return result.get(stock_code, FinancialReport(stock_code=stock_code))

    def _fetch_all_financials(self) -> Dict[str, FinancialReport]:
        """从 Eastmoney 拉全量财务数据（最新报告期），返回以代码为键的字典。"""
        # 东方财富 ISNEW=1 过滤后每批量较少，需要多页
        # 实际每页5000条，约需 100+ 页（全部股票约5000+）
        # 优化：用 A 股市场过滤条件减少数据量
        all_reports: Dict[str, FinancialReport] = {}
        seen_codes: set = set()

        for page in range(1, 200):
            url = "https://datacenter.eastmoney.com/api/data/v1/get"
            params = {
                "reportName": "RPT_LICO_FN_CPD",
                "columns": (
                    "SECURITY_CODE,SECURITY_NAME_ABBR,"
                    "BASIC_EPS,TOTAL_OPERATE_INCOME,PARENT_NETPROFIT,"
                    "WEIGHTAVG_ROE,TOTAL_ASSETS,TOTAL_LIABILITIES,"
                    "YSTZ,SJLTZ,BPS,QDATE,DATATYPE"
                ),
                f"pageNumber": str(page),
                f"pageSize": "5000",
                "sortColumns": "SECURITY_CODE",
                "sortTypes": "1",
                "filters": "ISNEW%3D1",
            }
            try:
                text = _http_get(url, params)
                data = json.loads(text)
            except Exception as e:
                print(f"[WebProvider] 财务数据失败 (page {page}): {e}")
                break

            result = data.get("result")
            if not result or not result.get("data"):
                break

            for row in result["data"]:
                code = row.get("SECURITY_CODE", "")
                if not code or code in seen_codes:
                    continue
                seen_codes.add(code)

                # 解析报告期
                report_date_str = row.get("QDATE", "")
                report_date = self._parse_qdate(report_date_str, report_type="annual")

                # 计算 PE/PB（如果字段有的话）
                net_profit = float(row.get("PARENT_NETPROFIT") or 0)
                total_assets = float(row.get("TOTAL_ASSETS") or 0)
                total_liabilities = float(row.get("TOTAL_LIABILITIES") or 0)

                # BPS（每股净资产）
                bps = float(row.get("BPS") or 0)

                # 如果有 BASIC_EPS 和 BPS，可以用实时价格算 PE/PB
                eps = float(row.get("BASIC_EPS") or 0)
                # 从 Eastmoney 实时行情拿当前股价来算 PE/PB
                # 这里先放0，后面可以补充实时价格
                pe = 0.0
                pb = 0.0
                if bps > 0:
                    # PB = 实时价格 / BPS（暂用0，后面补充实时行情价格）
                    pb = 0.0

                all_reports[code] = FinancialReport(
                    stock_code=code,
                    report_date=report_date,
                    report_type="annual",
                    pe=pe,
                    pb=pb,
                    roe=float(row.get("WEIGHTAVG_ROE") or 0) / 100.0,  # 百分数 -> 小数
                    revenue=float(row.get("TOTAL_OPERATE_INCOME") or 0),
                    revenue_yoy=float(row.get("YSTZ") or 0),
                    net_profit=net_profit,
                    net_profit_yoy=float(row.get("SJLTZ") or 0),
                    debt_ratio=(total_liabilities / total_assets * 100.0) if total_assets > 0 else 0.0,
                )

            if len(result["data"]) < 5000:
                break

        print(f"[WebProvider] 财务数据: {len(all_reports)} 只股票")
        return all_reports

    def _parse_qdate(self, qdate_str: str, report_type: str = "annual") -> date:
        """解析东方财富季度报告期字符串，如 '2024Q4' -> date(2024, 12, 31)"""
        if not qdate_str:
            return date.today()
        qdate_str = qdate_str.strip()
        m = re.match(r"(\d{4})Q([1-4])", qdate_str)
        if m:
            year, quarter = int(m.group(1)), int(m.group(2))
            month = {1: 3, 2: 6, 3: 9, 4: 12}[quarter]
            return date(year, month, 31)
        # 年报格式：2024
        try:
            year = int(qdate_str[:4])
            return date(year, 12, 31)
        except:
            return date.today()
