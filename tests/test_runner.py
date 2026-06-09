import os
import tempfile

from code.data.mock_provider import MockDataProvider
from code.scheduler.runner import NOTIFIER_REGISTRY, ScheduleRunner
from code.scheduler.store import ScheduleConfigStore
from code.data.models import ScheduleEntry


class TestScheduleRunner:

    def setup_method(self):
        self.tmpfile = tempfile.mktemp(suffix=".json")
        self.provider = MockDataProvider(seed=42)
        self.runner = ScheduleRunner(provider=self.provider)
        self.runner.store = ScheduleConfigStore(path=self.tmpfile)

    def teardown_method(self):
        if os.path.exists(self.tmpfile):
            os.remove(self.tmpfile)

    def test_run_nonexistent_schedule(self):
        assert self.runner.run_schedule("nonexistent") is False

    def test_run_disabled_schedule(self):
        entry = ScheduleEntry(
            name="禁用任务",
            strategy_name="value",
            cron_expression="0 15 * * *",
            notification_channels=["console"],
            enabled=False,
        )
        self.runner.store.add(entry)
        assert self.runner.run_schedule(entry.id) is False

    def test_run_valid_schedule(self):
        entry = ScheduleEntry(
            name="有效任务",
            strategy_name="value",
            cron_expression="0 15 * * *",
            notification_channels=["console"],
            enabled=True,
        )
        self.runner.store.add(entry)
        result = self.runner.run_schedule(entry.id)
        assert result is True

    def test_run_all_due(self):
        for i in range(2):
            self.runner.store.add(
                ScheduleEntry(
                    name=f"任务{i}",
                    strategy_name="value",
                    cron_expression="0 15 * * *",
                    notification_channels=["console"],
                    enabled=True,
                )
            )
        ids = self.runner.run_all_due()
        assert len(ids) == 2

    def test_run_all_skips_disabled(self):
        self.runner.store.add(
            ScheduleEntry(
                name="启用",
                strategy_name="value",
                cron_expression="0 15 * * *",
                notification_channels=["console"],
                enabled=True,
            )
        )
        self.runner.store.add(
            ScheduleEntry(
                name="禁用",
                strategy_name="value",
                cron_expression="0 15 * * *",
                notification_channels=["console"],
                enabled=False,
            )
        )
        ids = self.runner.run_all_due()
        assert len(ids) == 1


class TestNotifierRegistry:
    def test_console_registered(self):
        assert "console" in NOTIFIER_REGISTRY
        assert NOTIFIER_REGISTRY["console"].channel_name == "console"

    def test_wechat_registered(self):
        assert "wechat" in NOTIFIER_REGISTRY
        assert NOTIFIER_REGISTRY["wechat"].channel_name == "wechat"

    def test_email_registered(self):
        assert "email" in NOTIFIER_REGISTRY
        assert NOTIFIER_REGISTRY["email"].channel_name == "email"
