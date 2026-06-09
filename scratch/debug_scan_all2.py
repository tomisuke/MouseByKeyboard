import win32gui
import win32con
import win32api
import ctypes
import threading
import time
from ctypes import byref, c_int

dwmapi = ctypes.windll.dwmapi
DWMWA_CLOAKED = 14

EXCLUDED_WINDOW_CLASSES = frozenset({
    'Progman', 'WorkerW', 'Shell_TrayWnd', 'DV2ControlHost',
    'tooltips_class32', 'Windows.UI.Core.CoreWindow', 'InputTip'
})

_auto = None
def _get_auto():
    global _auto
    if _auto is None:
        import uiautomation as auto
        _auto = auto
    return _auto

CLICKABLE_TYPE_IDS = frozenset({
    50000, 50005, 50007, 50008, 50010, 50012, 50015, 50021, 50025, 50028, 50031, 50034
})

def _is_cloaked(hwnd: int) -> bool:
    try:
        cloaked = c_int(0)
        hr = dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, byref(cloaked), ctypes.sizeof(cloaked))
        if hr == 0:
            return cloaked.value != 0
    except Exception:
        pass
    return False

def _scan_tree(ctrl, results: list, stop: threading.Event, depth: int = 0) -> None:
    if stop.is_set() or depth > 35:
        return
    try:
        # Get properties inside the UIA thread to avoid COM apartment errors later
        ctrl_type = ctrl.ControlType
        if ctrl_type in CLICKABLE_TYPE_IDS:
            r = ctrl.BoundingRectangle
            name = ctrl.Name or ""
            if r.width() > 0 and r.height() > 0:
                results.append((r, ctrl_type, name))
            return
        if not stop.is_set():
            for child in ctrl.GetChildren():
                _scan_tree(child, results, stop, depth + 1)
    except Exception:
        pass

def _scan_hwnd(hwnd: int, timeout_ms: int) -> list:
    results: list = []
    stop = threading.Event()

    def _run() -> None:
        import comtypes
        comtypes.CoInitialize()
        try:
            auto = _get_auto()
            ctrl = auto.ControlFromHandle(hwnd)
            _scan_tree(ctrl, results, stop)
        except Exception as e:
            print(f"Error scanning hwnd {hwnd}: {e}")
        finally:
            try:
                comtypes.CoUninitialize()
            except Exception:
                pass

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout_ms / 1000.0)
    stop.set()
    return results

def get_screen_rect():
    try:
        x = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
        y = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
        w = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
        h = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        return (x, y, x + w, y + h)
    except Exception:
        return (0, 0, 1920, 1080)

def debug_scan_all():
    hwnds = []
    screen_rect = get_screen_rect()
    
    print(f"Screen Rect: {screen_rect}")
    print("\n--- Listing top-level windows (Improved Filter) ---")

    def enum_cb(hwnd, _):
        title = win32gui.GetWindowText(hwnd)
        cls = win32gui.GetClassName(hwnd)
        
        if not win32gui.IsWindowVisible(hwnd):
            return True
        if win32gui.IsIconic(hwnd):
            return True
        if _is_cloaked(hwnd):
            return True
        if cls in EXCLUDED_WINDOW_CLASSES:
            return True
            
        # Filter out windows without a title (often background/system windows)
        if not title.strip():
            return True
            
        try:
            r = win32gui.GetWindowRect(hwnd)
            rect_tuple = (r[0], r[1], r[2], r[3])
            w = rect_tuple[2] - rect_tuple[0]
            h = rect_tuple[3] - rect_tuple[1]
            if w <= 100 or h <= 100:  # Filter out very small windows
                return True
        except Exception:
            return True
            
        # Get owner to ensure it's a primary window
        owner = win32gui.GetWindow(hwnd, win32con.GW_OWNER)
        if owner != 0:
            return True
            
        print(f"HWND: {hwnd:8d} | Title: {title[:30]:30} | Class: {cls[:20]:20} | Rect: {rect_tuple} ({w}x{h}) -> ADDED")
        hwnds.append((hwnd, rect_tuple, title, cls))
        return True

    win32gui.EnumWindows(enum_cb, None)
    
    print(f"\nTotal candidate windows: {len(hwnds)}")
    
    # Scan top 8 candidates
    candidates = hwnds[:8]
    print("\n--- Starting scanning candidates ---")
    for i, (hwnd, rect, title, cls) in enumerate(candidates):
        t0 = time.time()
        elements = _scan_hwnd(hwnd, 1500)
        elapsed = (time.time() - t0) * 1000
        print(f"[{i}] HWND: {hwnd:8d} | Title: {title[:20]:20} | Class: {cls[:15]:15} | Scan: found {len(elements)} elements in {elapsed:.0f}ms")
        if len(elements) > 0:
            for r, ctrl_type, name in elements[:3]:
                # Print details without calling UIA properties on invalid COM wrapper
                print(f"    Element: type={ctrl_type} name='{name[:15]}' rect={r}")

if __name__ == '__main__':
    debug_scan_all()
