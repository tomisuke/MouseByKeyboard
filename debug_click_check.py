"""Exercise the real tag -> overlay hide -> native click path on each monitor.

Only clicks buttons in this diagnostic's own windows. No resident hotkeys.
"""
import ctypes
ctypes.windll.shcore.SetProcessDpiAwareness(2)

import tkinter as tk
from types import SimpleNamespace
import win32api
import win32con
import win32gui
from app import App
from config import Config


def main():
    root = tk.Tk()
    root.withdraw()
    app = App(root, Config())
    root.after(10, app._poll)
    cases = []
    received = []
    failures = []
    for i, (_, _, (l, t, r, b)) in enumerate(win32api.EnumDisplayMonitors()):
        panel = tk.Toplevel(root)
        panel.title(f'KeyNavigator click test {i}')
        panel.geometry('400x240+0+0')
        panel.attributes('-topmost', True)
        button = tk.Button(panel, text='Click test', command=lambda n=i: print('COMMAND', n, flush=True))
        button.pack(fill='both', expand=True, padx=40, pady=40)
        for num in (1, 2, 3):
            button.bind(f'<ButtonRelease-{num}>',
                        lambda e, n=i, k=num: received.append((n, k, e.x_root, e.y_root)), add='+')
        root.update()
        hwnd = win32gui.GetAncestor(panel.winfo_id(), win32con.GA_ROOT)
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, (l+r)//2-200, (t+b)//2-120,
                              400, 240, win32con.SWP_NOACTIVATE)
        cases.append((i, panel, button, hwnd))
    root.update()
    steps = [(case, mode) for case in cases for mode in ('left', 'right', 'middle', 'double')]

    def run(index=0):
        if index == len(steps):
            app._remove_kb_hook()
            root.destroy()
            return
        (i, panel, button, hwnd), mode = steps[index]
        panel.lift()
        panel.focus_force()
        root.update_idletasks()
        x, y = win32gui.ClientToScreen(button.winfo_id(), (button.winfo_width()//2, button.winfo_height()//2))
        rect = SimpleNamespace(left=x-10, top=y-10, right=x+10, bottom=y+10)
        app._focus_hwnd = hwnd
        app._on_scan_done([(rect, None)])
        app._state.set_click_mode(mode)
        received.clear()
        # Use the same hint-character handler as keyboard input, including
        # the deferred click after withdrawing the overlay/restoring focus.
        tag = app._state.tags[0]
        root.after(200, lambda: [app._process_hint_char(c) for c in tag])
        def verify():
            num = {'left': 1, 'double': 1, 'middle': 2, 'right': 3}[mode]
            expected = 2 if mode == 'double' else 1
            ok = len(received) == expected and all(event == (i, num, x, y) for event in received)
            print('PASS' if ok else 'FAIL', i, mode, (x,y), received, flush=True)
            if not ok:
                failures.append((i, mode, received.copy()))
            root.after(200, lambda: run(index+1))
        root.after(700, verify)
    root.after(300, run)
    root.after(20000, root.destroy)
    root.mainloop()
    if failures:
        raise AssertionError(failures)


if __name__ == '__main__':
    main()
