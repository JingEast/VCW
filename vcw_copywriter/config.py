"""
配置管理模块
"""
import copy
import json
from pathlib import Path

DEFAULT_CONFIG = {
    "llm": {
        "provider": "openai",
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
        "temperature": 0.7,
        "max_tokens": 2000
    },
    "memory": {
        "db_path": "data/memory_db.json",
        "max_entries_per_topic": 10
    },
    "output": {
        "save_dir": "data/generated",
        "auto_save": True
    },
    "quality_check": {
        "enabled": True,
        "strict_mode": False
    }
}


class Config:
    def __init__(self, config_path="config.json"):
        self.config_path = Path(config_path)
        self.data = self._load()

    def _load(self):
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                # 合并默认值，确保新字段存在（深拷贝防止污染全局默认值）
                merged = self._deep_merge(copy.deepcopy(DEFAULT_CONFIG), loaded)
                return merged
        return copy.deepcopy(DEFAULT_CONFIG)

    def _deep_merge(self, base, update):
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                base[key] = self._deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    def save(self):
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def get(self, *keys, default=None):
        d = self.data
        for key in keys:
            if isinstance(d, dict) and key in d:
                d = d[key]
            else:
                return default
        return d

    def set(self, *keys, value):
        d = self.data
        for key in keys[:-1]:
            if key not in d:
                d[key] = {}
            d = d[key]
        d[keys[-1]] = value


def ensure_dirs():
    Path("data").mkdir(exist_ok=True)
    Path("data/generated").mkdir(exist_ok=True)
