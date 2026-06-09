from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict, fields

CONFIG_DIR = os.path.join(os.path.expanduser('~'), '.keynamigator')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')


@dataclass
class Config:
    hotkey_all: str = 'ctrl+q'
    hotkey_active: str = 'ctrl+shift+q'
    # Home-row keys first (fjdksl), then outward
    hint_chars: str = 'fjdkslaghrueiwoqpvnmcxbt'
    font_size: int = 8
    # Prefix keys pressed before tag input to change click mode
    prefix_double: str = ';'
    prefix_right: str = "'"
    prefix_middle: str = ','
    scan_timeout_ms: int = 2000

    def save(self) -> None:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls) -> Config:
        if not os.path.exists(CONFIG_PATH):
            return cls()
        try:
            with open(CONFIG_PATH, encoding='utf-8') as f:
                data = json.load(f)
            valid = {fi.name for fi in fields(cls)}
            return cls(**{k: v for k, v in data.items() if k in valid})
        except Exception:
            return cls()
