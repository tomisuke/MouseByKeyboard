from __future__ import annotations
import ctypes
import ctypes.wintypes
import time

import win32api
import win32con
import win32gui

import os

_user32 = ctypes.windll.user32

# VSCode (code.exe) はUIA InvokePatternが例外なしで無視されるため、
# 物理クリックにフォールバックが必要なプロセス名のセット
_FORCE_PHYSICAL_PROCESSES = frozenset({'code.exe'})


def _get_process_name_from_hwnd(hwnd: int) -> str:
    """ウィンドウハンドルからプロセスのEXE名を取得する。"""
    try:
        pid = ctypes.wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        # PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h_process = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)
        if h_process:
            try:
                buf = ctypes.create_unicode_buffer(1024)
                size = ctypes.wintypes.DWORD(1024)
                if ctypes.windll.kernel32.QueryFullProcessImageNameW(
                        h_process, 0, buf, ctypes.byref(size)):
                    return os.path.basename(buf.value).lower()
            finally:
                ctypes.windll.kernel32.CloseHandle(h_process)
    except Exception:
        pass
    return ''


def _physical_click(x: int, y: int, click_type: str, orig_pos: tuple[int, int] | None = None) -> None:
    """Move mouse to (x, y), perform click, restore cursor position."""
    if orig_pos is not None:
        orig_x, orig_y = orig_pos
    else:
        pt = ctypes.wintypes.POINT()
        _user32.GetCursorPos(ctypes.byref(pt))
        orig_x, orig_y = pt.x, pt.y

    try:
        _user32.SetCursorPos(x, y)
        time.sleep(0.04)

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

        time.sleep(0.04)
    finally:
        _user32.SetCursorPos(orig_x, orig_y)

_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'click_debug.log')

def _log(msg: str) -> None:
    with open(_LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")


class Clicker:
    def __init__(self, config) -> None:
        self.config = config

    def click(self, element, rect, click_type: str = 'left', orig_pos: tuple[int, int] | None = None) -> None:
        cx = (rect.left + rect.right) // 2
        cy = (rect.top + rect.bottom) // 2

        _log(f"click called: cx={cx}, cy={cy}, click_type={click_type}, force_physical={self.config.force_physical_click}")

        # VSCode等、UIA Invokeが無視されるプロセスかどうかを判定
        skip_uia = False
        try:
            top_level = element.GetTopLevelControl()
            hwnd = top_level.NativeWindowHandle if top_level else None
            _log(f"top_level={top_level}, hwnd={hwnd}")
            if top_level and hwnd:
                proc_name = _get_process_name_from_hwnd(hwnd)
                class_name = win32gui.GetClassName(hwnd)
                _log(f"proc_name='{proc_name}', class_name='{class_name}'")
                if proc_name in _FORCE_PHYSICAL_PROCESSES:
                    skip_uia = True
                    _log(f"skip_uia=True (process in _FORCE_PHYSICAL_PROCESSES)")
        except Exception as e:
            _log(f"Exception during process detection: {e}")

        _log(f"skip_uia={skip_uia}")

        if not self.config.force_physical_click and not skip_uia:
            if click_type == 'left':
                # Try UIA InvokePattern first (no cursor movement)
                try:
                    pattern = element.GetInvokePattern()
                    _log(f"InvokePattern={pattern}")
                    if pattern:
                        pattern.Invoke()
                        _log(f"InvokePattern.Invoke() succeeded, returning")
                        return
                except Exception as e:
                    _log(f"InvokePattern failed: {e}")
                # Try uiautomation's built-in Click (uses SendMessage internally)
                try:
                    element.Click(simulateMove=False)
                    _log(f"element.Click() succeeded, returning")
                    return
                except Exception as e:
                    _log(f"element.Click() failed: {e}")

        # Fallback: physical mouse movement
        _log(f"Falling back to physical click at ({cx}, {cy})")
        _physical_click(cx, cy, click_type, orig_pos)
        _log(f"Physical click done")

