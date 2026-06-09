"""控制台通知输出。"""

from typing import List

from ..data.models import ScreeningResult
from .base import Notifier


class ConsoleNotifier(Notifier):
    channel_name = "console"

    def send(self, results: List[ScreeningResult], strategy_name: str) -> bool:
        print(self.format_results(results, strategy_name))
        return True
