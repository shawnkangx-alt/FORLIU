"""全局配置管理。配置文件存储在 ~/.forliu/config.json。"""

import json
import os
from typing import Any, Dict


CONFIG_DIR = os.path.expanduser("~/.forliu")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG: Dict[str, Any] = {
    "data_provider": "mock",
    "notifications": {
        "wechat": {
            "webhook_url": "",
            "enabled": False,
        },
        "email": {
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "username": "",
            "password": "",
            "to_addresses": [],
        },
    },
}


def _ensure_dir() -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load_config() -> Dict[str, Any]:
    """加载配置，如果文件不存在则使用默认配置。"""
    if not os.path.exists(CONFIG_PATH):
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        data = {}
    merged = dict(DEFAULT_CONFIG)
    _deep_merge(merged, data)
    return merged


def save_config(config: Dict[str, Any]) -> None:
    """保存配置到文件。"""
    _ensure_dir()
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get(key: str, default: Any = None) -> Any:
    """获取指定配置项。支持点号分隔的嵌套键，如 'notifications.wechat.webhook_url'。"""
    config = load_config()
    parts = key.split(".")
    current = config
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
            if current is None:
                return default
        else:
            return default
    return current


def set_key(key: str, value: Any) -> None:
    """设置指定配置项。支持点号分隔的嵌套键。"""
    config = load_config()
    parts = key.split(".")
    current = config
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value
    save_config(config)


def _deep_merge(base: dict, override: dict) -> None:
    """递归合并 override 到 base。"""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
