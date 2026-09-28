"""Check real GDI capture and detected coordinates using per-monitor targets."""
import ctypes
ctypes.windll.shcore.SetProcessDpiAwareness(2)
import time
import tkinter as tk
import win32api
import win32gui
import win32con
from PIL import ImageGrab
from scanner import _grab_screen_gdi, _scan_cv


def main():
    root = tk.Tk()
    root.withdraw()
    targets = []
    failures = []
    try:
        for i, (_, _, (l, t, r, b)) in enumerate(win32api.EnumDisplayMonitors()):
            top = tk.Toplevel(root)
            top.overrideredirect(True)
            top.attributes('-topmost', True)
            top.geometry('320x200+0+0')
            canvas = tk.Canvas(top, bg='#202020', highlightthickness=0)
            canvas.pack(fill='both', expand=True)
            canvas.create_rectangle(100, 70, 220, 130, fill='#ffffff', outline='#ffffff')
            root.update()
            hwnd = win32gui.GetAncestor(top.winfo_id(), win32con.GA_ROOT)
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST,
                                  (l+r)//2-160, (t+b)//2-100, 320, 200, 0)
            root.update()
            bounds = win32gui.GetWindowRect(hwnd)
            targets.append((i, bounds))
        time.sleep(0.3)
        for i, bounds in targets:
            for name, image in [('GDI', _grab_screen_gdi(bounds)),
                                ('PIL', ImageGrab.grab(bbox=bounds, all_screens=True))]:
                pixel = image.getpixel((160, 100))
                x, y = bounds[0]+160, bounds[1]+100
                detected = _scan_cv(image, bounds)
                matches = [rect for rect, _ in detected
                           if abs((rect.left+rect.right)//2-x) < 6
                           and abs((rect.top+rect.bottom)//2-y) < 6]
                ok = pixel == (255,255,255) and bool(matches)
                print(name, i, bounds, 'pixel=', pixel, 'matches=', len(matches),
                      'PASS' if ok else 'FAIL', flush=True)
                if not ok:
                    failures.append((name, i))
    finally:
        root.destroy()
    assert not failures, failures


if __name__ == '__main__':
    main()
