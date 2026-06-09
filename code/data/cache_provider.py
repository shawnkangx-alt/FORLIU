"""SQLite 缓存层，包装任意 DataProvider 避免重复请求。

⚠️ 数据来源追踪：
  - 写入缓存时记录 provider 名称
  - 读取缓存时验证来源，非真实 provider 的数据视为无效
  - MockDataProvider 的数据永远不会被缓存
  - 启动时自动清除历史遗留的 mock 数据
"""

import os
import sqlite3
import threading
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from .models import DailyQuote, FinancialReport, Stock
from .provider import DataProvider

DEFAULT_CACHE_DIR = os.path.expanduser("~/.forliu/cache")
DEFAULT_QUOTE_TTL_DAYS = 1
DEFAULT_FINANCIAL_TTL_DAYS = 7

# 真实数据源名称（用于识别 mock 数据）
_REAL_PROVIDER_NAMES = {
    "TushareProvider",
    "JoinQuantProvider",
    "EFinanceProvider",
    "AkShareProvider",
    "BaoStockProvider",
    "WebProvider",
    "SmartProvider",      # CacheProvider 包装层，source 记录为 SmartProvider
}


class CacheProvider(DataProvider):
    """带 SQLite 缓存的 DataProvider 装饰器。

    缓存策略：
      - 每个缓存记录存储数据来源 provider 名称
      - 读取时验证来源，mock 数据不会被返回
      - 启动时清除历史遗留的 mock 来源数据
      - TTL：行情 1 天，财务 7 天
    """

    def __init__(
        self,
        upstream: DataProvider,
        cache_dir: str = DEFAULT_CACHE_DIR,
        quote_ttl_days: int = DEFAULT_QUOTE_TTL_DAYS,
        financial_ttl_days: int = DEFAULT_FINANCIAL_TTL_DAYS,
    ):
        self.upstream = upstream
        self.quote_ttl = quote_ttl_days
        self.financial_ttl = financial_ttl_days
        self.db_path = os.path.join(cache_dir, "data_cache.db")
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS quotes (
                    stock_code TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    open REAL, high REAL, low REAL, close REAL,
                    volume REAL, amount REAL,
                    source TEXT NOT NULL DEFAULT '',
                    fetched_at TEXT NOT NULL,
                    PRIMARY KEY (stock_code, trade_date)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS financials (
                    stock_code TEXT PRIMARY KEY,
                    report_date TEXT,
                    pe REAL, pb REAL, roe REAL,
                    revenue REAL, revenue_yoy REAL,
                    net_profit REAL, net_profit_yoy REAL,
                    debt_ratio REAL, current_ratio REAL,
                    source TEXT NOT NULL DEFAULT '',
                    fetched_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stock_list (
                    code TEXT PRIMARY KEY,
                    name TEXT,
                    market TEXT,
                    source TEXT NOT NULL DEFAULT '',
                    fetched_at TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_quotes_code ON quotes(stock_code)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_quotes_date ON quotes(trade_date)")
            # 迁移：添加 source 列（历史表可能没有）
            for table, cols in [("quotes", "source"), ("financials", "source"), ("stock_list", "source")]:
                try:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {cols} TEXT NOT NULL DEFAULT ''")
                except sqlite3.OperationalError:
                    pass  # 列已存在
            # 清除历史遗留的 mock 数据
            for table in ("quotes", "financials", "stock_list"):
                conn.execute(f"DELETE FROM {table} WHERE source = 'MockDataProvider'")
            conn.commit()
            conn.close()

    def _provider_name(self) -> str:
        """获取当前 upstream 的 provider 名称。"""
        return type(self.upstream).__name__

    # ------------------------------------------------------------------
    # 股票列表
    # ------------------------------------------------------------------

    def list_stocks(self, force_refresh: bool = False) -> List[Stock]:
        """获取股票列表。

        Args:
            force_refresh: True = 强制从上游刷新全量（打印提示）；False = 优先读缓存，缓存为空则静默从上游获取。
        """
        # ── 读缓存路径（所有路径最终都在这里 return）───────────────────────────
        if not force_refresh:
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                rows = conn.execute(
                    "SELECT code, name, market, source, fetched_at FROM stock_list"
                ).fetchall()
                conn.close()

            if rows:
                valid = []
                for r in rows:
                    if len(r) < 5:
                        continue
                    src = r[3]
                    if src not in _REAL_PROVIDER_NAMES:
                        continue
                    try:
                        fetched = datetime.fromisoformat(r[4])
                    except (ValueError, TypeError):
                        continue
                    if datetime.now() - fetched < timedelta(days=30):
                        valid.append(r)
                if valid:
                    return [
                        Stock(code=r[0], name=r[1], market=r[2])
                        for r in valid
                    ]
            # 缓存为空或已过期：静默从上游获取，不打印，不写缓存
            return self.upstream.list_stocks()

        # ── force_refresh=True：强制从上游刷新全量（有提示）──────────────────
        upstream_name = self.upstream.__class__.__name__
        print(f"[CacheProvider] 全量同步股票列表（{upstream_name}），约 236+ 只...",
              file=__import__('sys').stderr)
        stocks = self.upstream.list_stocks()
        if stocks:
            now = datetime.now().isoformat()
            src = self._provider_name()
            with self._lock:
                conn = sqlite3.connect(self.db_path)
                conn.execute("DELETE FROM stock_list")
                conn.executemany(
                    "INSERT INTO stock_list VALUES (?, ?, ?, ?, ?)",
                    [(s.code, s.name,
                      s.market.value if hasattr(s.market, 'value') else s.market,
                      now, src) for s in stocks],
                )
                conn.commit()
                conn.close()
        return stocks
    # 行情数据
    # ------------------------------------------------------------------

    def get_daily_quotes(self, stock_code: str, start: date, end: date) -> List[DailyQuote]:
        cached = self._get_cached_quotes(stock_code, start, end)
        if cached is not None:
            return cached

        quotes = self.upstream.get_daily_quotes(stock_code, start, end)
        if quotes:
            self._save_quotes(quotes)
        return quotes

    def get_batch_quotes(
        self, stock_codes: List[str], start: date, end: date
    ) -> Dict[str, List[DailyQuote]]:
        result: Dict[str, List[DailyQuote]] = {}
        uncached: List[str] = []

        for code in stock_codes:
            cached = self._get_cached_quotes(code, start, end)
            if cached is not None:
                result[code] = cached
            else:
                uncached.append(code)

        if uncached:
            upstream_result = self.upstream.get_batch_quotes(uncached, start, end)
            for code, quotes in upstream_result.items():
                self._save_quotes(quotes)
                result[code] = quotes

        return result

    # ------------------------------------------------------------------
    # 财务数据
    # ------------------------------------------------------------------

    def get_financials(self, stock_code: str, report_type: str = "annual") -> FinancialReport:
        cached = self._get_cached_financials(stock_code)
        if cached is not None:
            return cached

        fin = self.upstream.get_financials(stock_code, report_type)
        if fin:
            self._save_financials(fin)
        return fin

    def get_batch_financials(
        self, stock_codes: List[str], report_type: str = "annual"
    ) -> Dict[str, FinancialReport]:
        result: Dict[str, FinancialReport] = {}
        uncached: List[str] = []

        for code in stock_codes:
            cached = self._get_cached_financials(code)
            if cached is not None:
                result[code] = cached
            else:
                uncached.append(code)

        if uncached:
            upstream_result = self.upstream.get_batch_financials(uncached, report_type=report_type)
            for code, fin in upstream_result.items():
                self._save_financials(fin)
                result[code] = fin

        return result

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _get_cached_quotes(
        self, stock_code: str, start: date, end: date
    ) -> Optional[List[DailyQuote]]:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute(
                "SELECT source, fetched_at FROM quotes WHERE stock_code = ? AND trade_date >= ? AND trade_date <= ? LIMIT 1",
                (stock_code, start.isoformat(), end.isoformat()),
            ).fetchone()
            conn.close()

        if not row:
            return None

        source, fetched_at_str = row
        # mock 来源的数据视为无效
        if source not in _REAL_PROVIDER_NAMES:
            return None

        fetched = datetime.fromisoformat(fetched_at_str)
        if datetime.now() - fetched >= timedelta(days=self.quote_ttl):
            return None

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute(
                "SELECT stock_code, trade_date, open, high, low, close, volume, amount "
                "FROM quotes WHERE stock_code = ? AND trade_date >= ? AND trade_date <= ? "
                "ORDER BY trade_date",
                (stock_code, start.isoformat(), end.isoformat()),
            ).fetchall()
            conn.close()

        return [
            DailyQuote(
                stock_code=r[0],
                date=date.fromisoformat(r[1]),
                open=r[2],
                high=r[3],
                low=r[4],
                close=r[5],
                volume=r[6],
                amount=r[7],
            )
            for r in rows
        ]

    def _get_cached_financials(self, stock_code: str) -> Optional[FinancialReport]:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute(
                "SELECT stock_code, report_date, pe, pb, roe, revenue, revenue_yoy, "
                "net_profit, net_profit_yoy, debt_ratio, current_ratio, source, fetched_at "
                "FROM financials WHERE stock_code = ?",
                (stock_code,),
            ).fetchone()
            conn.close()

        if not row:
            return None

        source = row[11]
        # mock 来源的数据视为无效
        if source not in _REAL_PROVIDER_NAMES:
            return None

        fetched_at_str = row[12]
        fetched = datetime.fromisoformat(fetched_at_str)
        if datetime.now() - fetched >= timedelta(days=self.financial_ttl):
            return None

        return FinancialReport(
            stock_code=row[0],
            report_date=date.fromisoformat(row[1]),
            pe=row[2],
            pb=row[3],
            roe=row[4],
            revenue=row[5],
            revenue_yoy=row[6],
            net_profit=row[7],
            net_profit_yoy=row[8],
            debt_ratio=row[9],
            current_ratio=row[10],
        )

    def _save_quotes(self, quotes: List[DailyQuote]) -> None:
        if not quotes:
            return
        now = datetime.now().isoformat()
        src = self._provider_name()
        # 不缓存 mock 来源的数据
        if src == "MockDataProvider":
            return
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.executemany(
                "INSERT OR REPLACE INTO quotes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        q.stock_code,
                        q.date.isoformat(),
                        q.open,
                        q.high,
                        q.low,
                        q.close,
                        q.volume,
                        q.amount,
                        src,
                        now,
                    )
                    for q in quotes
                ],
            )
            conn.commit()
            conn.close()

    def _save_financials(self, fin: FinancialReport) -> None:
        now = datetime.now().isoformat()
        src = self._provider_name()
        # 不缓存 mock 来源的数据
        if src == "MockDataProvider":
            return
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT OR REPLACE INTO financials VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    fin.stock_code,
                    fin.report_date.isoformat(),
                    fin.pe,
                    fin.pb,
                    fin.roe,
                    fin.revenue,
                    fin.revenue_yoy,
                    fin.net_profit,
                    fin.net_profit_yoy,
                    fin.debt_ratio,
                    fin.current_ratio,
                    src,
                    now,
                ),
            )
            conn.commit()
            conn.close()

    def clear_cache(self) -> None:
        """清除所有缓存数据。"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM quotes")
            conn.execute("DELETE FROM financials")
            conn.execute("DELETE FROM stock_list")
            conn.commit()
            conn.close()
