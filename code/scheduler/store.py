"""定时任务配置存储。JSON 文件持久化。"""

import json
import os
from typing import List, Optional

from ..data.models import ScheduleEntry

DEFAULT_STORE_PATH = os.path.expanduser("~/.forliu/schedules.json")


class ScheduleConfigStore:
    """JSON 文件持久化的定时任务 CRUD。"""

    def __init__(self, path: str = DEFAULT_STORE_PATH):
        self.path = path

    def list_all(self) -> List[ScheduleEntry]:
        data = self._load()
        entries = data.get("schedules", [])
        return [_dict_to_entry(e) for e in entries]

    def get(self, schedule_id: str) -> Optional[ScheduleEntry]:
        for entry in self.list_all():
            if entry.id == schedule_id:
                return entry
        return None

    def add(self, entry: ScheduleEntry) -> None:
        data = self._load()
        entries = data.get("schedules", [])
        entries.append(_entry_to_dict(entry))
        data["schedules"] = entries
        self._save(data)

    def remove(self, schedule_id: str) -> bool:
        data = self._load()
        entries = data.get("schedules", [])
        new_entries = [e for e in entries if e.get("id") != schedule_id]
        if len(new_entries) == len(entries):
            return False
        data["schedules"] = new_entries
        self._save(data)
        return True

    def enable(self, schedule_id: str, enabled: bool) -> bool:
        data = self._load()
        entries = data.get("schedules", [])
        found = False
        for e in entries:
            if e.get("id") == schedule_id:
                e["enabled"] = enabled
                found = True
        if found:
            data["schedules"] = entries
            self._save(data)
        return found

    def _load(self) -> dict:
        if not os.path.exists(self.path):
            return {"schedules": []}
        try:
            with open(self.path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"schedules": []}

    def _save(self, data: dict) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def _entry_to_dict(entry: ScheduleEntry) -> dict:
    return {
        "id": entry.id,
        "name": entry.name,
        "strategy_name": entry.strategy_name,
        "cron_expression": entry.cron_expression,
        "notification_channels": entry.notification_channels,
        "enabled": entry.enabled,
        "created_at": entry.created_at.isoformat(),
    }


def _dict_to_entry(d: dict) -> ScheduleEntry:
    from datetime import datetime

    return ScheduleEntry(
        id=d.get("id", ""),
        name=d.get("name", ""),
        strategy_name=d.get("strategy_name", ""),
        cron_expression=d.get("cron_expression", ""),
        notification_channels=d.get("notification_channels", ["console"]),
        enabled=d.get("enabled", True),
        created_at=datetime.fromisoformat(d["created_at"]) if "created_at" in d else datetime.now(),
    )
