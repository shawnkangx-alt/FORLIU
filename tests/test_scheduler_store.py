import json
import os
import tempfile

from code.data.models import ScheduleEntry
from code.scheduler.store import ScheduleConfigStore


class TestScheduleConfigStore:

    def setup_method(self):
        self.tmpfile = tempfile.mktemp(suffix=".json")
        self.store = ScheduleConfigStore(path=self.tmpfile)

    def teardown_method(self):
        if os.path.exists(self.tmpfile):
            os.remove(self.tmpfile)

    def test_list_empty(self):
        assert self.store.list_all() == []

    def test_add_and_list(self):
        entry = ScheduleEntry(
            name="测试任务", strategy_name="value", cron_expression="0 15 * * *"
        )
        self.store.add(entry)
        entries = self.store.list_all()
        assert len(entries) == 1
        assert entries[0].name == "测试任务"
        assert entries[0].strategy_name == "value"
        assert entries[0].enabled is True

    def test_get_by_id(self):
        entry = ScheduleEntry(
            name="测试任务", strategy_name="value", cron_expression="0 15 * * *"
        )
        self.store.add(entry)
        found = self.store.get(entry.id)
        assert found is not None
        assert found.name == "测试任务"

    def test_get_nonexistent(self):
        assert self.store.get("nonexistent") is None

    def test_remove(self):
        entry = ScheduleEntry(
            name="测试任务", strategy_name="value", cron_expression="0 15 * * *"
        )
        self.store.add(entry)
        assert self.store.remove(entry.id) is True
        assert self.store.list_all() == []

    def test_remove_nonexistent(self):
        assert self.store.remove("nonexistent") is False

    def test_enable_disable(self):
        entry = ScheduleEntry(
            name="测试任务", strategy_name="value", cron_expression="0 15 * * *"
        )
        self.store.add(entry)

        self.store.enable(entry.id, False)
        e = self.store.get(entry.id)
        assert e.enabled is False

        self.store.enable(entry.id, True)
        e = self.store.get(entry.id)
        assert e.enabled is True

    def test_persistence(self):
        entry = ScheduleEntry(
            name="持久化测试", strategy_name="growth", cron_expression="30 9 * * 1-5"
        )
        self.store.add(entry)

        store2 = ScheduleConfigStore(path=self.tmpfile)
        entries = store2.list_all()
        assert len(entries) == 1
        assert entries[0].name == "持久化测试"

    def test_add_multiple(self):
        for i in range(3):
            self.store.add(
                ScheduleEntry(
                    name=f"任务{i}", strategy_name="value", cron_expression="0 15 * * *"
                )
            )
        assert len(self.store.list_all()) == 3
