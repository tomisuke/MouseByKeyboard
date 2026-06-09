"""
KeyNavigator - キーボードだけでマウス操作を完結させるWindows常駐ユーティリティ

起動: python main.py
依存: pip install -r requirements.txt
"""
from __future__ import annotations
import ctypes
import sys


def _set_dpi_aware() -> None:
    """プロセスをPer-Monitor DPI Aware v2に設定する（座標ズレ防止）。"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


# DPI設定はtkinterより前に行う必要がある
_set_dpi_aware()

import tkinter as tk

from config import Config
from app import App
from tray import TrayIcon


def main() -> None:
    config = Config.load()

    root = tk.Tk()
    root.withdraw()  # メインウィンドウは非表示

    app = App(root, config)
    app.start()

    tray = TrayIcon(config, app._queue)
    tray.start()

    print('[KeyNavigator] 起動しました。タスクトレイのアイコンを右クリックで操作できます。')
    print(f'  全画面スキャン:      {config.hotkey_all}')
    print(f'  アクティブ画面:      {config.hotkey_active}')
    print(f'  プレフィックス:      ダブル={config.prefix_double}  '
          f'右={config.prefix_right}  中央={config.prefix_middle}')

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
