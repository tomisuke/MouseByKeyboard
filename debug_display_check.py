"""Run the real Tk overlay on every connected display and measure alignment.

Run with --hold to leave the calibration badges visible for 45 seconds.
--image also checks image detection using a target on each display.
--fixtures leaves those target windows open for 120 seconds for manual tests.
--startup-single simulates starting before the secondary monitor connects.
--app starts the normal resident app and logs overlay alignment after each scan
      (stop any other resident instance first to avoid hotkey conflicts).
Calibration modes do not install global keyboard hooks or perform clicks.
"""
import ctypes
import sys
from types import SimpleNamespace

ctypes.windll.shcore.SetProcessDpiAwareness(2)

import tkinter as tk
import win32api
import win32gui
import win32con
from config import Config
from overlay import HintOverlay


def main():
    root = tk.Tk()
    root.withdraw()
    fixtures = []
    if '--image' in sys.argv or '--fixtures' in sys.argv:
        from PIL import ImageGrab
        from scanner import Scanner
        for i, (_, _, (l, t, r, b)) in enumerate(win32api.EnumDisplayMonitors()):
            panel = tk.Toplevel(root)
            panel.title(f'KeyNavigator display test {i}')
            panel.geometry('400x240+0+0')
            panel.attributes('-topmost', True)
            canvas = tk.Canvas(panel, bg='#303030', highlightthickness=0)
            canvas.pack(fill='both', expand=True)
            canvas.create_rectangle(140, 90, 260, 140, fill='white', outline='white')
            root.update()
            win32gui.SetWindowPos(win32gui.GetAncestor(panel.winfo_id(), win32con.GA_ROOT),
                                  win32con.HWND_TOPMOST, (l+r)//2-200, (t+b)//2-120,
                                  400, 240, win32con.SWP_NOACTIVATE)
            fixtures.append((panel, canvas))
        root.update()
        import time
        time.sleep(0.3)
        scanner = Scanner(Config())
        bounds = scanner._get_screen_rect()
        image = ImageGrab.grab(bbox=bounds, all_screens=True)
        detected = scanner.scan_all_image()
        for panel, canvas in fixtures:
            x, y = win32gui.ClientToScreen(canvas.winfo_id(), (200, 115))
            pixel = image.getpixel((x-bounds[0], y-bounds[1]))
            matches = [rect for rect, _ in detected if abs((rect.left+rect.right)//2-x) <= 10
                       and abs((rect.top+rect.bottom)//2-y) <= 10]
            print('IMAGE', panel.title(), 'pixel=', pixel, 'matching_rectangles=', len(matches), flush=True)
            assert pixel == (255, 255, 255), 'Secondary screen was not captured'
            assert matches, 'Image scanner did not find the calibration target'
        if '--fixtures' in sys.argv:
            root.after(120000, root.destroy)
            root.mainloop()
            return
        for panel, _ in fixtures:
            panel.destroy()
    if '--startup-single' in sys.argv:
        from unittest.mock import patch
        get_metric = win32api.GetSystemMetrics
        initial = {76: 0, 77: 0, 78: get_metric(0), 79: get_metric(1)}
        with patch.object(win32api, 'GetSystemMetrics',
                          side_effect=lambda n: initial[n] if n in initial else get_metric(n)):
            overlay = HintOverlay(root, Config(), lambda _: None, lambda _: root.destroy())
            # Include an existing incremental badge. It must be redrawn when
            # the virtual origin changes, even if its tag is unchanged.
            _, _, (l, t, r, b) = win32api.EnumDisplayMonitors()[0]
            first = SimpleNamespace(left=l+80, top=t+90, right=l+120, bottom=t+110)
            overlay.show([(first, None)], ['t0'])
            root.update()
    else:
        overlay = HintOverlay(root, Config(), lambda _: None, lambda _: root.destroy())
    overlay._top.title('KeyNavigator display calibration')
    elements = []
    for monitor, _, bounds in win32api.EnumDisplayMonitors():
        print('MONITOR', win32api.GetMonitorInfo(monitor), flush=True)
        l, t, r, b = bounds
        for x, y in ((l + 100, t + 100), ((l + r) // 2, (t + b) // 2), (r - 100, b - 100)):
            elements.append((SimpleNamespace(left=x-20, top=y-10, right=x+20, bottom=y+10), None))
    tags = [f't{i}' for i in range(len(elements))]
    overlay.show(elements, tags)
    root.update()
    failures = []
    def verify():
        failures.extend(report(root, overlay, elements, tags))
        overlay.hide()
        overlay.show(elements, tags)
        root.update_idletasks()
        failures.extend(report(root, overlay, elements, tags))
    root.after(500, verify)
    root.after(45000 if '--hold' in sys.argv else 1500, root.destroy)
    root.mainloop()
    if failures:
        raise AssertionError(f'Misaligned tags: {failures}')


def report(root, overlay, elements, tags):
    canvas = overlay._canvas
    origin = win32gui.ClientToScreen(canvas.winfo_id(), (0, 0))
    print('VIRTUAL', (overlay._vx, overlay._vy, overlay._vw, overlay._vh), flush=True)
    print('ACTUAL_CANVAS', origin, (canvas.winfo_width(), canvas.winfo_height()), flush=True)
    failures = []
    expected_origin = (win32api.GetSystemMetrics(76), win32api.GetSystemMetrics(77))
    expected_size = (win32api.GetSystemMetrics(78), win32api.GetSystemMetrics(79))
    if origin != expected_origin or (canvas.winfo_width(), canvas.winfo_height()) != expected_size:
        failures.append('desktop bounds')
    for (rect, _), tag in zip(elements, tags):
        expected = ((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
        local = canvas.coords(overlay._badge_items[tag][2])
        if not (0 <= local[0] < canvas.winfo_width() and 0 <= local[1] < canvas.winfo_height()):
            failures.append(f'{tag} clipped')
        actual = (origin[0] + local[0], origin[1] + local[1])
        print(tag, 'expected=', expected, 'actual=', actual, flush=True)
        if actual != expected:
            failures.append(tag)
    print('RESULT', 'FAIL ' + str(failures) if failures else 'PASS', flush=True)
    return failures


if __name__ == '__main__':
    if '--app' in sys.argv:
        # Run the normal app with measurement only; input, scanning and drawing
        # still go through the production event loop and global hotkeys.
        import main as entry
        original_show = HintOverlay.show
        def measured_show(self, elements, tags, scan_finished=False):
            original_show(self, elements, tags, scan_finished)
            self._top.update_idletasks()
            origin = win32gui.ClientToScreen(self._canvas.winfo_id(), (0, 0))
            assert origin == (self._vx, self._vy), (origin, self._vx, self._vy)
            counts = []
            for _, _, (l, t, r, b) in win32api.EnumDisplayMonitors():
                counts.append(sum(l <= (rect.left+rect.right)//2 < r
                                  and t <= (rect.top+rect.bottom)//2 < b for rect, _ in elements))
            print('LIVE OVERLAY PASS', 'origin=', origin, 'tags_per_monitor=', counts, flush=True)
        HintOverlay.show = measured_show
        entry.main()
    else:
        main()
