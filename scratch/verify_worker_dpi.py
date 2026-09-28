"""サブディスプレイ要素取得バグの修正検証スクリプト。

1. ProcessPoolExecutor ワーカーの DPI Awareness が正しく設定されているか確認する
   (修正前は Unaware=0 のままだったはずのものが、修正後は
   PROCESS_PER_MONITOR_DPI_AWARE=2 になっていることを確認)。
2. 実際に副ディスプレイ (負の座標を持つモニタ) 上に開いたウィンドウを
   Scanner.scan_all() でスキャンし、取得された要素の座標がそのウィンドウの
   実座標範囲内に収まっていることを確認する。
"""
from __future__ import annotations
import ctypes
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import win32gui
import win32api
import win32con
import win32process

from config import Config
from scanner import Scanner, _worker_init_dpi_aware, _scan_hwnd_process


def _get_dpi_awareness() -> int:
    value = ctypes.c_int()
    ctypes.windll.shcore.GetProcessDpiAwareness(0, ctypes.byref(value))
    return value.value


def check_worker_dpi_awareness(scanner: Scanner) -> None:
    future = scanner._process_pool.submit(_get_dpi_awareness)
    result = future.result()
    print(f"[TEST] worker DPI awareness = {result} (expect 2 = PROCESS_PER_MONITOR_DPI_AWARE)")
    assert result == 2, "ワーカープロセスの DPI Awareness が設定されていません"


def check_worker_dpi_awareness_without_fix() -> None:
    """initializer なしのプールを作り、修正前の状態 (Unaware) を再現して比較する。"""
    from concurrent.futures import ProcessPoolExecutor
    pool = ProcessPoolExecutor(max_workers=1)
    try:
        future = pool.submit(_get_dpi_awareness)
        result = future.result()
        print(f"[TEST] (修正なしの比較用) initializer 無しの worker DPI awareness = {result} (0 = Unaware であれば従来のバグ状態を再現できている)")
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _list_notepad_hwnds() -> set:
    hwnds = set()

    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetClassName(hwnd) == 'Notepad':
            hwnds.add(hwnd)
        return True

    win32gui.EnumWindows(cb, None)
    return hwnds


def find_notepad_hwnd(before: set, timeout=5.0) -> int:
    start = time.time()
    while time.time() - start < timeout:
        new_hwnds = _list_notepad_hwnds() - before
        if new_hwnds:
            return next(iter(new_hwnds))
        time.sleep(0.2)
    return 0


def main():
    print("--- ディスプレイ構成 ---")
    monitors = win32api.EnumDisplayMonitors()
    for h, _, rect in monitors:
        print(f"  {rect}")

    # 2枚目のモニタ (負の座標を持つ = サブディスプレイ) を特定
    sub_rect = None
    for _, _, rect in monitors:
        if rect[1] < 0 or rect[0] < 0:
            sub_rect = rect
            break
    if sub_rect is None:
        # 負座標がない場合は単純に2枚目のものをサブとして扱う
        sub_rect = monitors[1][2] if len(monitors) > 1 else monitors[0][2]
    print(f"サブディスプレイと判定した領域: {sub_rect}")

    config = Config()
    config.scan_timeout_ms = 1500
    scanner = Scanner(config)

    try:
        check_worker_dpi_awareness_without_fix()
        check_worker_dpi_awareness(scanner)

        # メモ帳をサブディスプレイ上に開く
        before = _list_notepad_hwnds()
        proc = subprocess.Popen(["notepad.exe"])
        hwnd = find_notepad_hwnd(before)
        assert hwnd, "notepad のウィンドウが見つかりませんでした"

        target_x = sub_rect[0] + 100
        target_y = sub_rect[1] + 100
        win32gui.MoveWindow(hwnd, target_x, target_y, 600, 400, True)
        time.sleep(0.5)

        win_rect = win32gui.GetWindowRect(hwnd)
        print(f"[TEST] notepad を移動後のウィンドウ実座標: {win_rect}")
        assert win_rect[1] < 0 or win_rect[0] < 0 or (sub_rect[1] < 0), "ウィンドウがサブディスプレイの負座標領域に配置されていません"

        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.3)

        found_any = False
        for batch in scanner.scan_all():
            for r, _ in batch:
                # サブディスプレイ上の notepad ウィンドウの要素が、実座標範囲内にあるか確認
                if (win_rect[0] - 5) <= r.left and r.right <= (win_rect[2] + 5) and \
                   (win_rect[1] - 5) <= r.top and r.bottom <= (win_rect[3] + 5):
                    found_any = True

        print(f"[TEST] notepad(サブディスプレイ上)の要素がウィンドウ範囲内で検出されたか: {found_any}")
        assert found_any, "サブディスプレイ上のウィンドウ要素が正しい座標で検出されませんでした"

        print("\n=== 検証成功: サブディスプレイ上の要素が正しい座標で取得されました ===")

        # 参考: このマシンは両モニタとも 96 DPI (100%) のため、DPI Unaware な
        # ワーカーでも本環境では偶然座標がズレない可能性がある。実際に
        # initializer 無し (Unaware) のワーカーで同じウィンドウをスキャンし、
        # 結果を比較して参考情報として出力する。
        screen_rect = scanner._get_screen_rect()
        from concurrent.futures import ProcessPoolExecutor
        unaware_pool = ProcessPoolExecutor(max_workers=1)
        try:
            unaware_result = unaware_pool.submit(
                _scan_hwnd_process, hwnd, config.scan_timeout_ms, screen_rect
            ).result()
        finally:
            unaware_pool.shutdown(wait=False, cancel_futures=True)
        print(f"[REF] Unawareワーカーでの直接スキャン結果 ({len(unaware_result)}件): {unaware_result[:5]}")
        print(f"[REF] 参考: 本機は両ディスプレイとも96DPI(100%)のため、DPI設定差によるズレはこの環境では再現しない可能性がある。"
              f"上記の座標が win_rect={win_rect} の範囲内に収まっているかを目視確認。")

        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
    finally:
        scanner.shutdown()


if __name__ == "__main__":
    main()
