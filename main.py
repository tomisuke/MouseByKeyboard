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


_app_mutex = None


def _check_single_instance() -> bool:
    global _app_mutex
    try:
        import win32event
        import win32api
        import winerror
        # システム全体で一意の名前のミューテックスを作成
        _app_mutex = win32event.CreateMutex(None, True, "Global\\KeyNavigator_SingleInstance_Mutex_998877")
        last_error = win32api.GetLastError()
        # ERROR_ALREADY_EXISTS = 183
        if last_error == winerror.ERROR_ALREADY_EXISTS:
            return False
        return True
    except Exception:
        return True


def main() -> None:
    if not _check_single_instance():
        print("[KeyNavigator] KeyNavigatorは既に起動しています。")
        # スタートアップや別のランチャーから同時に起動されることがあるため、
        # 既存プロセスがあれば通知を出さずに終了する。
        sys.exit(0)

    # スタートアップ起動対策: タスクバー(Shell_TrayWnd)が表示されるまで待機する
    import win32gui
    import time
    wait_attempts = 20  # 0.5s * 20 = 10秒
    for _ in range(wait_attempts):
        hwnd_tray = win32gui.FindWindow("Shell_TrayWnd", None)
        if hwnd_tray:
            break
        time.sleep(0.5)

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
    finally:
        sys.exit(0)


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    main()
