"""股票池过滤器：市值、交易所、板块、自选股列表过滤。"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set


@dataclass
class MarketCapRange:
    """市值范围（单位：亿元）。"""
    min_total: Optional[float] = None  # 总市值下限
    max_total: Optional[float] = None  # 总市值上限
    min_float: Optional[float] = None  # 流通市值下限
    max_float: Optional[float] = None  # 流通市值上限


@dataclass
class StockPoolFilter:
    """股票池过滤器，支持多重条件组合。

    示例：
        f = StockPoolFilter(
            watchlist_files=["my_stocks.txt"],
            exchanges={"SH", "SZ"},
            market_cap=MarketCapRange(min_total=50, max_total=500),
            industries={"银行", "医药生物"},
        )
        filtered = f.apply(stock_dict)  # stock_dict: {code: {"name":..., "industry":..., ...}}
    """

    # --- 数据源 ---
    watchlist_codes: Set[str] = field(default_factory=set)  # 自选股代码集合
    watchlist_files: List[str] = field(default_factory=list)  # 自选股文件路径列表

    # --- 过滤条件 ---
    exchanges: Optional[Set[str]] = None  # 交易所过滤 {"SH", "SZ", "BJ"}
    industries: Optional[Set[str]] = None  # 行业板块过滤
    market_cap: Optional[MarketCapRange] = None  # 市值范围
    exclude_st: bool = True  # 排除 ST/*ST

    def __post_init__(self):
        # 从文件加载自选股
        for fp in self.watchlist_files:
            self._load_watchlist(fp)

    def _load_watchlist(self, filepath: str):
        """从文件加载自选股，每行一个代码（支持 # 注释）。"""
        path = Path(filepath).expanduser()
        if not path.exists():
            print(f"[StockPool] 自选股文件不存在: {filepath}")
            return
        try:
            content = path.read_text(encoding="utf-8")
            for line in content.splitlines():
                code = line.split("#")[0].strip()
                if code:
                    self.watchlist_codes.add(code)
        except Exception as e:
            print(f"[StockPool] 读取自选股文件失败 {filepath}: {e}")

    def filter_codes(self, codes: List[str]) -> List[str]:
        """对候选股票代码列表进行过滤，返回符合条件的代码。"""
        result = codes
        result = self._filter_by_watchlist(result)
        result = self._filter_by_exchange(result)
        result = self._filter_by_st(result)
        return result

    def _filter_by_watchlist(self, codes: List[str]) -> List[str]:
        if not self.watchlist_codes:
            return codes
        return [c for c in codes if c in self.watchlist_codes]

    def _filter_by_exchange(self, codes: List[str]) -> List[str]:
        if not self.exchanges:
            return codes
        return [c for c in codes if self._get_exchange(c) in self.exchanges]

    def _filter_by_st(self, codes: List[str]) -> List[str]:
        """排除 ST 股票（通过名称判断，需外部传入名称映射）。"""
        # 这里只做代码层面的粗筛，实际 ST 判断依赖外部 name_map
        return codes

    @staticmethod
    def _get_exchange(code: str) -> str:
        """从股票代码判断交易所。"""
        code = code.strip()
        if code.startswith(("6", "9")):
            return "SH"
        if code.startswith(("0", "3")):
            return "SZ"
        if code.startswith(("4", "8")):
            return "BJ"
        return "UNKNOWN"

    def get_filter_summary(self) -> Dict:
        """返回过滤条件摘要，供日志/调试用。"""
        return {
            "watchlist_count": len(self.watchlist_codes),
            "watchlist_files": self.watchlist_files,
            "exchanges": list(self.exchanges) if self.exchanges else None,
            "industries": list(self.industries) if self.industries else None,
            "market_cap": {
                "min_total": self.market_cap.min_total if self.market_cap else None,
                "max_total": self.market_cap.max_total if self.market_cap else None,
                "min_float": self.market_cap.min_float if self.market_cap else None,
                "max_float": self.market_cap.max_float if self.market_cap else None,
            } if self.market_cap else None,
            "exclude_st": self.exclude_st,
        }


# --- CLI 辅助：解析 filter JSON ---
def parse_filter_from_args(args: dict) -> StockPoolFilter:
    """从命令行参数 dict 构造 StockPoolFilter。"""
    filter_args = {}

    if args.get("watchlist"):
        watchlist = args["watchlist"]
        if isinstance(watchlist, str):
            watchlist = [watchlist]
        filter_args["watchlist_files"] = watchlist

    if args.get("exchange"):
        filter_args["exchanges"] = set(args["exchange"].split(","))

    if args.get("industry"):
        filter_args["industries"] = set(args["industry"].split(","))

    if args.get("market_cap"):
        mc = args["market_cap"]
        # 支持 "50-500" 格式
        if isinstance(mc, str) and "-" in mc:
            parts = mc.split("-")
            filter_args["market_cap"] = MarketCapRange(
                min_total=float(parts[0]) if parts[0] else None,
                max_total=float(parts[1]) if parts[1] else None,
            )
        elif isinstance(mc, dict):
            filter_args["market_cap"] = MarketCapRange(**{k: v for k, v in mc.items() if v})

    exclude_st = args.get("exclude_st", True)
    filter_args["exclude_st"] = exclude_st

    return StockPoolFilter(**filter_args)
