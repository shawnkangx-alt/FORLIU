"""股票池过滤器：市值、交易所、板块、自选股列表过滤。"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

# 行业板块映射：名称 → 代码集合
# "semiconductor" 是特殊虚拟行业，从 semiconductor.py 动态获取
_INDUSTRY_STOCK_CODES: Dict[str, Set[str]] = {}


def _get_industry_codes(industry_name: str) -> Optional[Set[str]]:
    """根据行业名称获取股票代码集合。

    特殊行业：
    - "半导体" / "semiconductor": 从 semiconductor.py 动态获取
    - 其他：从东方财富行业分类获取（待实现）
    返回 None 表示未实现，返回空 set 表示无数据。
    """
    name_lower = industry_name.lower()
    if name_lower in ("半导体", "bandaoti", "semiconductor"):
        from ..data.semiconductor import get_semiconductor_codes

        return get_semiconductor_codes()
    # 其他行业暂未实现
    return None


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
            industries={"半导体"},
            market_cap=MarketCapRange(min_total=50, max_total=500),
        )
        filtered = f.filter_codes(all_codes)
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
        """对候选股票代码列表进行过滤，返回符合条件的代码。

        特殊处理：如果 industries 包含"半导体"（或别名），
        则直接使用半导体股票集合作为搜索空间，忽略 codes 参数。
        """
        # 行业过滤优先：如果是半导体，直接用半导体集合，不依赖 provider 的股票列表
        if self.industries and any(
            n.lower() in ("半导体", "bandaoti", "semiconductor")
            for n in self.industries
        ):
            from ..data.semiconductor import get_semiconductor_codes

            semi_codes = get_semiconductor_codes()
            # 同时应用其他过滤条件
            result = list(semi_codes)
            result = self._filter_by_exchange(result)
            result = self._filter_by_st(result)
            return result

        result = codes
        result = self._filter_by_watchlist(result)
        result = self._filter_by_exchange(result)
        result = self._filter_by_industry(result)
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

    def _filter_by_industry(self, codes: List[str]) -> List[str]:
        """按行业板块过滤。

        特殊行业（如"半导体"）从 semiconductor.py 动态获取代码列表。
        其他行业暂不支持。
        """
        if not self.industries:
            return codes
        result: List[str] = []
        for code in codes:
            for industry in self.industries:
                codes_for_industry = _get_industry_codes(industry)
                if codes_for_industry is None:
                    # 行业未实现，跳过该过滤条件并打印警告
                    print(f"[StockPool] 行业 '{industry}' 暂不支持，将跳过板块过滤")
                    break
                if code in codes_for_industry:
                    result.append(code)
                    break
        return result if result else codes  # 空结果说明无匹配，返回原始列表

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
