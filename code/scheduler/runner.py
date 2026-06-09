"""定时任务执行器。加载调度配置 -> 执行筛选 -> 分发通知。"""

import sys
from typing import Dict, List, Optional, Type

from ..data.mock_provider import MockDataProvider
from ..data.models import ScreeningResult
from ..notification.base import Notifier
from ..notification.console import ConsoleNotifier
from ..notification.email_notify import EmailNotifier
from ..notification.wechat import WeChatNotifier
from ..screening.screener import Screener
from .store import ScheduleConfigStore

NOTIFIER_REGISTRY: Dict[str, Notifier] = {
    "console": ConsoleNotifier(),
    "wechat": WeChatNotifier(),
    "email": EmailNotifier(),
}


class ScheduleRunner:
    """加载调度配置，执行股票筛选并发送通知。"""

    def __init__(self, provider: Optional[MockDataProvider] = None):
        self.provider = provider or MockDataProvider()
        self.screener = Screener(self.provider)
        self.store = ScheduleConfigStore()

    def run_schedule(self, schedule_id: str) -> bool:
        """执行一个定时任务。"""
        entry = self.store.get(schedule_id)
        if not entry:
            print(f"未找到定时任务: {schedule_id}")
            return False

        if not entry.enabled:
            return False

        results = self.screener.screen_preset(entry.strategy_name)
        success = True
        for channel in entry.notification_channels:
            notifier = NOTIFIER_REGISTRY.get(channel.strip())
            if notifier:
                if not notifier.send(results, entry.name):
                    success = False

        return success

    def run_all_due(self) -> List[str]:
        """执行所有启用的定时任务。返回执行成功的任务 ID 列表。"""
        entries = self.store.list_all()
        executed = []
        for entry in entries:
            if entry.enabled:
                if self.run_schedule(entry.id):
                    executed.append(entry.id)
        return executed


def main():
    """CLI 入口：python -m code.scheduler.runner --all 或 --schedule-id <id>"""
    import argparse

    parser = argparse.ArgumentParser(description="FORLIU 定时任务执行器")
    parser.add_argument("--all", action="store_true", help="执行所有启用的定时任务")
    parser.add_argument("--schedule-id", help="执行指定 ID 的定时任务")

    args = parser.parse_args()
    runner = ScheduleRunner()

    if args.all:
        ids = runner.run_all_due()
        print(f"已执行 {len(ids)} 个定时任务")
    elif args.schedule_id:
        ok = runner.run_schedule(args.schedule_id)
        sys.exit(0 if ok else 1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
