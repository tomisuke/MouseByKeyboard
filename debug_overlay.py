"""オーバーレイが単体で表示されるかテスト"""
import ctypes
ctypes.windll.shcore.SetProcessDpiAwareness(2)

import tkinter as tk
from overlay import HintOverlay
from config import Config
from scanner import _scan_hwnd
import win32gui, time, threading

def main():
    cfg = Config()
    cfg.scan_timeout_ms = 2000

    root = tk.Tk()
    root.withdraw()

    keys_pressed = []

    def on_key(char):
        print(f"Key: {repr(char)}")
        keys_pressed.append(char)
        if len(keys_pressed) >= 1:
            # Cancel after first key
            root.after(500, root.destroy)

    def on_special(name):
        print(f"Special: {name}")
        root.after(100, root.destroy)

    overlay = HintOverlay(root, cfg, on_key=on_key, on_special=on_special)

    def do_scan():
        # Find File Explorer
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

        print(f"Scanning HWND: {hwnd}")
        try:
            print(f"ClassName: {win32gui.GetClassName(hwnd)}")
        except Exception as e:
            print(f"Could not get class name: {e}")
        t0 = time.time()
        try:
            elements = _scan_hwnd(hwnd, 2000)
        except Exception as e:
            print(f"Scan failed: {e}")
            elements = []
        print(f"Found {len(elements)} elements in {(time.time()-t0)*1000:.0f}ms")

        def show():
            from hint_manager import generate_tags
            tags = generate_tags(len(elements), cfg.hint_chars)
            print(f"Showing overlay with {len(tags)} tags")
            overlay.show(elements, tags)

        root.after(0, show)

    threading.Thread(target=do_scan, daemon=True).start()

    print("Overlay test starting - press any key when overlay appears...")
    root.after(100, lambda: None)  # keep alive
    root.mainloop()
    print("Done")

main()
