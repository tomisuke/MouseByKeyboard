from __future__ import annotations
import ctypes
import ctypes.wintypes
import time

import win32api
import win32con

_user32 = ctypes.windll.user32


def _physical_click(x: int, y: int, click_type: str) -> None:
    """Move mouse to (x, y), perform click, restore cursor position."""
    pt = ctypes.wintypes.POINT()
    _user32.GetCursorPos(ctypes.byref(pt))
    orig_x, orig_y = pt.x, pt.y

    _user32.SetCursorPos(x, y)
    time.sleep(0.025)

    if click_type == 'left':
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    elif click_type == 'right':
        win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
    elif click_type == 'double':
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.05)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    elif click_type == 'middle':
        win32api.mouse_event(win32con.MOUSEEVENTF_MIDDLEDOWN, 0, 0, 0, 0)
        win32api.mouse_event(win32con.MOUSEEVENTF_MIDDLEUP, 0, 0, 0, 0)

    time.sleep(0.025)
    _user32.SetCursorPos(orig_x, orig_y)


class Clicker:
    def click(self, element, rect, click_type: str = 'left') -> None:
        cx = (rect.left + rect.right) // 2
        cy = (rect.top + rect.bottom) // 2

        if click_type == 'left':
            # Try UIA InvokePattern first (no cursor movement)
            try:
                pattern = element.GetInvokePattern()
                if pattern:
                    pattern.Invoke()
                    return
            except Exception:
                pass
            # Try uiautomation's built-in Click (uses SendMessage internally)
            try:
                element.Click(simulateMove=False)
                return
            except Exception:
                pass

        # Fallback: physical mouse movement
        _physical_click(cx, cy, click_type)
