"""スキャンのスレッド版が動くか確認"""
import threading, time, win32gui
from scanner import _scan_hwnd, _scan_tree, _get_auto, CLICKABLE_TYPE_IDS
import comtypes

# File Explorer HWND を探す
hwnd = 0
def cb(h, _):
    global hwnd
    if win32gui.GetClassName(h) == 'CabinetWClass':
        hwnd = h
        return False
    return True
win32gui.EnumWindows(cb, None)
if not hwnd:
    hwnd = win32gui.GetForegroundWindow()

print(f"Target HWND: {hwnd}  class: {win32gui.GetClassName(hwnd)}")

# 300ms タイムアウト版
print("\n--- 300ms timeout ---")
t0 = time.time()
results = _scan_hwnd(hwnd, 300)
print(f"Result: {len(results)} elements in {(time.time()-t0)*1000:.0f}ms")

# 1000ms タイムアウト版
print("\n--- 1000ms timeout ---")
t0 = time.time()
results = _scan_hwnd(hwnd, 1000)
print(f"Result: {len(results)} elements in {(time.time()-t0)*1000:.0f}ms")
