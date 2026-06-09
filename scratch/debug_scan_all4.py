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
    'DV2ControlHost',
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

def _rect_contains(parent_rect: tuple, child_rect: tuple) -> bool:
    """Return True if parent_rect completely contains child_rect."""
    pl, pt, pr, pb = parent_rect
    cl, ct, cr, cb = child_rect
    return pl <= cl and pt <= ct and pr >= cr and pb >= cb

def _is_hidden_by_opaque_windows(r, opaque_rects: list) -> bool:
    try:
        rl, rt, rr, rb = r.left, r.top, r.right, r.bottom
        for op_r in opaque_rects:
            ol, ot, orig_r, ob = op_r
            if ol <= rl and ot <= rt and orig_r >= rr and ob >= rb:
                return True
    except Exception:
        pass
    return False

def _scan_tree(ctrl, results: list, stop: threading.Event, depth: int = 0) -> None:
    if stop.is_set() or depth > 35:
        return
    try:
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
            pass
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
    opaque_rects = []
    screen_rect = get_screen_rect()
    screen_w = screen_rect[2] - screen_rect[0]
    screen_h = screen_rect[3] - screen_rect[1]
    screen_area = screen_w * screen_h
    
    foreground_hwnd = 264352 # win32gui.GetForegroundWindow()
    print(f"Foreground HWND: {foreground_hwnd} | Screen Area: {screen_area}")

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
            
        is_special = cls in ('Shell_TrayWnd', 'Progman', 'WorkerW')
        if not is_special and not title.strip():
            return True
            
        try:
            r = win32gui.GetWindowRect(hwnd)
            rect_tuple = (r[0], r[1], r[2], r[3])
            w = rect_tuple[2] - rect_tuple[0]
            h = rect_tuple[3] - rect_tuple[1]
            if not is_special and (w <= 100 or h <= 100):
                return True
        except Exception:
            return True
            
        owner = win32gui.GetWindow(hwnd, win32con.GW_OWNER)
        if owner != 0:
            return True
            
        # Refined Overlapping Check
        # 1. Active window is NEVER skipped
        is_active = (hwnd == foreground_hwnd)
        
        if not is_active:
            # Check if this window is completely covered by already registered foreground opaque windows
            covered = False
            for op_r in opaque_rects:
                if _rect_contains(op_r, rect_tuple):
                    covered = True
                    break
            if covered:
                print(f"HWND: {hwnd:8d} | Title: {title[:20]:20} | Class: {cls[:15]:15} -> SKIPPED (Covered)")
                return True
        
        # 2. Add to opaque blockers ONLY IF:
        # - It is the active window
        # - OR it is not fullscreen-like (takes less than 90% of screen)
        # This prevents background full screen windows from blocking everything.
        win_area = w * h
        is_fullscreen_like = win_area > (screen_area * 0.9)
        
        should_block = is_active or not is_fullscreen_like
        
        print(f"HWND: {hwnd:8d} | Title: {title[:20]:20} | Class: {cls[:15]:15} | Rect: {rect_tuple} ({w}x{h}) -> ADDED (Blocks: {should_block})")
        hwnds.append((hwnd, rect_tuple, should_block, title, cls))
        
        if should_block:
            opaque_rects.append(rect_tuple)
            
        return True

    win32gui.EnumWindows(enum_cb, None)
    
    # Process candidates
    candidates = hwnds[:12]
    print(f"\nTotal candidate windows: {len(candidates)}")
    
    processed_opaque_rects = []
    
    for i, (hwnd, rect, should_block, title, cls) in enumerate(candidates):
        t0 = time.time()
        elements = _scan_hwnd(hwnd, 1500)
        elapsed = (time.time() - t0) * 1000
        
        # Filter elements of this window
        valid_elements = []
        for r, ctrl_type, name in elements:
            if r.right <= screen_rect[0] or r.left >= screen_rect[2] or r.bottom <= screen_rect[1] or r.top >= screen_rect[3]:
                continue
            # Check if hidden by opaque windows processed so far
            if _is_hidden_by_opaque_windows(r, processed_opaque_rects):
                continue
            valid_elements.append((r, ctrl_type, name))
            
        print(f"[{i}] HWND: {hwnd:8d} | Title: {title[:20]:20} | Class: {cls[:15]:15} | Found {len(elements)} raw, {len(valid_elements)} filtered elements in {elapsed:.0f}ms")
        
        if len(valid_elements) > 0:
            for r, ctrl_type, name in valid_elements[:3]:
                print(f"    Element: type={ctrl_type} name='{name[:15]}' rect={r}")
                
        if should_block:
            processed_opaque_rects.append(rect)

if __name__ == '__main__':
    debug_scan_all()
