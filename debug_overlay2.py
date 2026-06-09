"""オーバーレイが単体で表示されるかテスト（ファイルログ版）"""
import ctypes, sys, time, threading, win32gui
ctypes.windll.shcore.SetProcessDpiAwareness(2)

log = open("debug_overlay2.log", "w", encoding="utf-8")
def L(msg):
    log.write(msg + "\n")
    log.flush()

L("=== start ===")

import tkinter as tk
from overlay import HintOverlay
from config import Config
from scanner import _scan_hwnd
from hint_manager import generate_tags

try:
    cfg = Config()
    cfg.scan_timeout_ms = 2000
    L("Config OK")

    root = tk.Tk()
    root.withdraw()
    L("Tk root created")

    def on_key(char):
        L(f"Key pressed: {repr(char)}")
        root.after(2000, root.destroy)

    def on_special(name):
        L(f"Special key: {name}")
        root.after(500, root.destroy)

    overlay = HintOverlay(root, cfg, on_key=on_key, on_special=on_special)
    L("Overlay created")

    def do_scan():
        hwnd = 0
        def cb(h, _):
            nonlocal hwnd
            if win32gui.GetClassName(h) == 'CabinetWClass':
                hwnd = h
                return False
            return True
        win32gui.EnumWindows(cb, None)
        if not hwnd:
            hwnd = win32gui.GetForegroundWindow()
        L(f"Scanning HWND={hwnd} class={win32gui.GetClassName(hwnd)}")

        t0 = time.time()
        elements = _scan_hwnd(hwnd, 2000)
        L(f"Scan done: {len(elements)} elements in {(time.time()-t0)*1000:.0f}ms")

        def show():
            try:
                tags = generate_tags(len(elements), cfg.hint_chars)
                L(f"Calling overlay.show() with {len(elements)} elements")
                overlay.show(elements, tags)
                L("overlay.show() returned")
            except Exception as e:
                L(f"ERROR in show: {e}")
                import traceback
                L(traceback.format_exc())

        root.after(0, show)

    threading.Thread(target=do_scan, daemon=True).start()
    L("Scan thread started, entering mainloop")
    root.mainloop()
    L("mainloop exited")

except Exception as e:
    import traceback
    L(f"FATAL: {e}\n{traceback.format_exc()}")

log.close()
