"""overlay.py のオーバーレイウィンドウが実際にどの座標に配置されるかを診断する。

HintOverlay._setup() / show() と全く同じロジックで Toplevel を作り、
winfo_id() の hwnd が実際に SetWindowPos で意図した座標 (vx, vy, vw, vh) に
配置されているか、GetWindowRect で検証する。
"""
from __future__ import annotations
import ctypes
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk
import win32api
import win32gui
import win32con


def _set_dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


_set_dpi_aware()

root = tk.Tk()
root.withdraw()

t = tk.Toplevel(root)
t.overrideredirect(True)
t.attributes('-topmost', True)
t.attributes('-transparentcolor', 'black')
t.configure(bg='black')
t.withdraw()

vx = win32api.GetSystemMetrics(76)
vy = win32api.GetSystemMetrics(77)
vw = win32api.GetSystemMetrics(78)
vh = win32api.GetSystemMetrics(79)
print(f"intended: vx={vx} vy={vy} vw={vw} vh={vh}")

t.geometry(f'{vw}x{vh}{vx:+d}{vy:+d}')

canvas = tk.Canvas(t, bg='black', highlightthickness=0)
canvas.pack(fill=tk.BOTH, expand=True)

t.deiconify()
t.lift()
t.update_idletasks()

hwnd = t.winfo_id()
print(f"winfo_id() hwnd = {hwnd}")
print(f"GetWindowRect(winfo_id hwnd) BEFORE SetWindowPos = {win32gui.GetWindowRect(hwnd)}")

parent_hwnd = win32gui.GetParent(hwnd)
print(f"GetParent(hwnd) = {parent_hwnd}")
if parent_hwnd:
    print(f"GetWindowRect(parent hwnd) BEFORE SetWindowPos = {win32gui.GetWindowRect(parent_hwnd)}")

# GA_ROOT = 2 : 真のトップレベル祖先を取得
GA_ROOT = 2
user32 = ctypes.windll.user32
root_hwnd = user32.GetAncestor(hwnd, GA_ROOT)
print(f"GetAncestor(hwnd, GA_ROOT) = {root_hwnd}")
if root_hwnd:
    print(f"GetWindowRect(GA_ROOT hwnd) BEFORE SetWindowPos = {win32gui.GetWindowRect(root_hwnd)}")

ret = win32gui.SetWindowPos(
    hwnd,
    win32con.HWND_TOPMOST,
    vx, vy, vw, vh,
    win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW
)
print(f"SetWindowPos(winfo_id hwnd, ...) return value = {ret}  (0 = failure, check GetLastError)")
if not ret:
    print(f"  GetLastError = {win32api.GetLastError()}")

print("--- after SetWindowPos on winfo_id() hwnd ---")
print(f"GetWindowRect(winfo_id hwnd) = {win32gui.GetWindowRect(hwnd)}")
if parent_hwnd:
    print(f"GetWindowRect(parent hwnd) = {win32gui.GetWindowRect(parent_hwnd)}")
if root_hwnd:
    print(f"GetWindowRect(GA_ROOT hwnd) = {win32gui.GetWindowRect(root_hwnd)}")

# 本当のトップレベル (GA_ROOT) に対して SetWindowPos した場合の挙動を確認
if root_hwnd and root_hwnd != hwnd:
    ret2 = win32gui.SetWindowPos(
        root_hwnd,
        win32con.HWND_TOPMOST,
        vx, vy, vw, vh,
        win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW
    )
    print(f"SetWindowPos(GA_ROOT hwnd, ...) return value = {ret2}")
    print(f"GetWindowRect(GA_ROOT hwnd) after = {win32gui.GetWindowRect(root_hwnd)}")
    print(f"GetWindowRect(winfo_id hwnd) after = {win32gui.GetWindowRect(hwnd)}")

# 参考: 実際に描画されるバッジのローカル座標計算を再現
# サブディスプレイ上の要素 (絶対座標 y=-970) と、プライマリ上の要素 (絶対座標 y=310) を想定
for label, abs_y in [("sub-display element", -970), ("primary-display element", 310)]:
    local_y = abs_y - vy
    print(f"{label}: abs_y={abs_y} -> canvas local_y={local_y}")

t.withdraw()
root.destroy()
