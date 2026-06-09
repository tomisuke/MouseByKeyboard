import win32gui
import win32con
import win32api
import ctypes
from ctypes import byref, c_int

dwmapi = ctypes.windll.dwmapi
DWMWA_CLOAKED = 14

EXCLUDED_WINDOW_CLASSES = frozenset({
    'Progman', 'WorkerW', 'Shell_TrayWnd', 'DV2ControlHost',
    'tooltips_class32', 'Windows.UI.Core.CoreWindow', 'InputTip'
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

def _rect_contains(parent_rect: tuple, child_rect: tuple) -> bool:
    pl, pt, pr, pb = parent_rect
    cl, ct, cr, cb = child_rect
    return pl <= cl and pt <= ct and pr >= cr and pb >= cb

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
    opaque_rects = []
    screen_rect = get_screen_rect()
    
    print(f"Screen Rect: {screen_rect}")
    print("\n--- Listing top-level windows ---")

    def enum_cb(hwnd, _):
        title = win32gui.GetWindowText(hwnd)
        cls = win32gui.GetClassName(hwnd)
        
        # Log visible windows details
        if not win32gui.IsWindowVisible(hwnd):
            return True
        
        iconic = win32gui.IsIconic(hwnd)
        cloaked = _is_cloaked(hwnd)
        excluded = cls in EXCLUDED_WINDOW_CLASSES
        
        try:
            r = win32gui.GetWindowRect(hwnd)
            rect_tuple = (r[0], r[1], r[2], r[3])
            w = rect_tuple[2] - rect_tuple[0]
            h = rect_tuple[3] - rect_tuple[1]
        except Exception as e:
            rect_tuple = (0, 0, 0, 0)
            w, h = 0, 0
            
        print(f"HWND: {hwnd:8d} | Title: {title[:30]:30} | Class: {cls[:20]:20} | Rect: {rect_tuple} ({w}x{h}) | Iconic: {iconic} | Cloaked: {cloaked} | Excluded: {excluded}")
        
        if iconic or cloaked or excluded or w <= 0 or h <= 0:
            return True
            
        # Check coverage
        covered = False
        covering_win = None
        for i, op_r in enumerate(opaque_rects):
            if _rect_contains(op_r, rect_tuple):
                covered = True
                covering_win = i
                break
                
        if covered:
            print(f"  -> SKIPPED: Completely covered by opaque rect {opaque_rects[covering_win]}")
            return True
            
        hwnds.append((hwnd, rect_tuple, title, cls))
        opaque_rects.append(rect_tuple)
        print(f"  -> ADDED. Opaque rect count now: {len(opaque_rects)}")
        return True

    win32gui.EnumWindows(enum_cb, None)
    
    print("\n--- Final selected windows (top 8) ---")
    for i, (hwnd, rect, title, cls) in enumerate(hwnds[:8]):
        print(f"[{i}] HWND: {hwnd:8d} | Title: {title[:30]:30} | Class: {cls[:20]:20} | Rect: {rect}")
        
    print(f"Total candidate windows in list: {len(hwnds)}")

if __name__ == '__main__':
    debug_scan_all()
