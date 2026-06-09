"""通知模块抽象接口。"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List

from ..data.models import ScreeningResult


class Notifier(ABC):
    channel_name: str = ""

    @abstractmethod
    def send(self, results: List[ScreeningResult], strategy_name: str) -> bool:
        """发送筛选结果通知。返回是否成功。"""
        ...

    def format_results(self, results: List[ScreeningResult], strategy_name: str) -> str:
        """格式化筛选结果为可读文本。"""
        lines = [
            f"=== FORLIU 筛选结果: {strategy_name} ===",
            f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"匹配数量: {len(results)}",
            "",
        ]
        for i, r in enumerate(results[:20], 1):
            matched = ",".join(rule.indicator.value for rule in r.matched_rules)
            lines.append(f"{i}. {r.stock.name}({r.stock.code}) 得分:{r.score:.0f} [{matched}]")
        return "\n".join(lines)
