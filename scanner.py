from __future__ import annotations
import ctypes
from ctypes import byref, c_int
import threading
from typing import List

import win32gui
import win32api
import win32con

_auto = None
dwmapi = ctypes.windll.dwmapi
DWMWA_CLOAKED = 14


def _get_auto():
    global _auto
    if _auto is None:
        import uiautomation as auto
        _auto = auto
    return _auto


CLICKABLE_TYPE_IDS = frozenset({
    50000,  # Button
    50002,  # CheckBox
    50003,  # ComboBox
    50004,  # Edit
    50005,  # Hyperlink
    50007,  # ListItem
    50011,  # MenuItem
    50013,  # RadioButton
    50019,  # TabItem
    50024,  # TreeItem
    50029,  # DataItem
    50031,  # SplitButton
})

EXCLUDED_WINDOW_CLASSES = frozenset({
    'DV2ControlHost',
    'tooltips_class32', 'Windows.UI.Core.CoreWindow', 'InputTip'
})


def _is_cloaked(hwnd: int) -> bool:
    """Check if the window is cloaked (hidden by DWM, e.g., suspended UWP apps)."""
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
    """Return True if the element rectangle is completely covered by any foreground opaque window."""
    try:
        rl, rt, rr, rb = r.left, r.top, r.right, r.bottom
        for op_r in opaque_rects:
            ol, ot, orig_r, ob = op_r
            if ol <= rl and ot <= rt and orig_r >= rr and ob >= rb:
                return True
    except Exception:
        pass
    return False


def _is_out_of_screen(r, screen_rect: tuple) -> bool:
    """Return True if the element rectangle is completely outside the screen bounds."""
    sl, st, sr, sb = screen_rect
    try:
        return r.right <= sl or r.left >= sr or r.bottom <= st or r.top >= sb
    except Exception:
        return True


def _scan_tree(ctrl, results: list, stop: threading.Event, depth: int = 0) -> None:
    if stop.is_set() or depth > 18:
        return
    try:
        r = ctrl.BoundingRectangle
        if r.width() <= 0 or r.height() <= 0:
            return
        if ctrl.ControlType in CLICKABLE_TYPE_IDS:
            results.append((r, ctrl))
            return
        if not stop.is_set():
            child = ctrl.GetFirstChildControl()
            while child and not stop.is_set():
                _scan_tree(child, results, stop, depth + 1)
                child = child.GetNextSiblingControl()
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
        except Exception:
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


class Scanner:
    def __init__(self, config) -> None:
        self.config = config

    def _get_screen_rect(self) -> tuple[int, int, int, int]:
        try:
            x = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
            y = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
            w = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
            h = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
            return (x, y, x + w, y + h)
        except Exception:
            return (0, 0, 1920, 1080)

    def scan_active(self) -> list:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return []
        
        raw_elements = _scan_hwnd(hwnd, self.config.scan_timeout_ms)
        screen_rect = self._get_screen_rect()
        
        try:
            wl, wt, wr, wb = win32gui.GetWindowRect(hwnd)
        except Exception:
            wl, wt, wr, wb = screen_rect
        
        # Filter out elements that are off-screen or outside the active window bounds
        filtered = []
        for r, ctrl in raw_elements:
            if not _is_out_of_screen(r, screen_rect):
                cx = (r.left + r.right) // 2
                cy = (r.top + r.bottom) // 2
                if wl <= cx <= wr and wt <= cy <= wb:
                    filtered.append((r, ctrl))
        return filtered

    def scan_all(self) -> list:
        # Collect visible, non-minimized, non-cloaked top-level HWNDs
        hwnds: list = []
        opaque_rects: list = []
        screen_rect = self._get_screen_rect()
        
        screen_w = screen_rect[2] - screen_rect[0]
        screen_h = screen_rect[3] - screen_rect[1]
        screen_area = screen_w * screen_h
        
        foreground_hwnd = win32gui.GetForegroundWindow()

        def enum_cb(hwnd, _) -> bool:
            if not win32gui.IsWindowVisible(hwnd):
                return True
            if win32gui.IsIconic(hwnd):
                return True
            if _is_cloaked(hwnd):
                return True
            
            cls = win32gui.GetClassName(hwnd)
            if cls in EXCLUDED_WINDOW_CLASSES:
                return True
            
            is_special = cls in ('Shell_TrayWnd', 'Progman', 'WorkerW')
            
            # Skip windows without a title unless it's a special system window (like taskbar)
            title = win32gui.GetWindowText(hwnd).strip()
            if not is_special and not title:
                return True
            
            try:
                r = win32gui.GetWindowRect(hwnd)
                rect_tuple = (r[0], r[1], r[2], r[3])
                w = rect_tuple[2] - rect_tuple[0]
                h = rect_tuple[3] - rect_tuple[1]
                # Filter out very small windows unless it's a special system window (taskbar height is small)
                if not is_special and (w <= 100 or h <= 100):
                    return True
                
                # Overlap check: active window is never skipped, others can be skipped if covered by blockers
                is_active = (hwnd == foreground_hwnd)
                if not is_active:
                    covered = False
                    for op_r in opaque_rects:
                        if _rect_contains(op_r, rect_tuple):
                            covered = True
                            break
                    if covered:
                        return True
                
                # Only register as an opaque blocker if active OR not fullscreen-like (background fullscreen shouldn't block)
                win_area = w * h
                is_fullscreen_like = win_area > (screen_area * 0.9)
                should_block = is_active or not is_fullscreen_like
                
                hwnds.append((hwnd, rect_tuple, should_block))
                if should_block:
                    opaque_rects.append(rect_tuple)
            except Exception:
                return True
            return True

        win32gui.EnumWindows(enum_cb, None)

        if not hwnds:
            return []

        # Scan top-most windows first, up to a maximum of 12 visible windows
        hwnds = hwnds[:12]

        timeout = self.config.scan_timeout_ms
        all_results: list = []
        
        # Keep track of opaque windows processed so far to filter out hidden elements
        processed_opaque_rects: list = []

        # Parallel scanning using ThreadPoolExecutor
        from concurrent.futures import ThreadPoolExecutor
        
        futures_ordered = []
        max_workers = min(8, len(hwnds))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for hwnd, win_rect, should_block in hwnds:
                future = executor.submit(_scan_hwnd, hwnd, timeout)
                futures_ordered.append((future, hwnd, win_rect, should_block))
            
            for future, hwnd, win_rect, should_block in futures_ordered:
                try:
                    partial = future.result()
                    if partial:
                        for r, ctrl in partial:
                            if _is_out_of_screen(r, screen_rect):
                                continue
                            if _is_hidden_by_opaque_windows(r, processed_opaque_rects):
                                continue
                            all_results.append((r, ctrl))
                except Exception as e:
                    print(f"[KN] Parallel scan error for hwnd {hwnd}: {e}")
                
                if should_block:
                    processed_opaque_rects.append(win_rect)

        return all_results

    def scan_all_image(self) -> list:
        # Collect clickable elements via image analysis (Pillow edge/contour detection)
        from PIL import Image, ImageGrab, ImageOps, ImageFilter
        import uiautomation as auto
        
        screen_rect = self._get_screen_rect()
        screen_w = screen_rect[2] - screen_rect[0]
        screen_h = screen_rect[3] - screen_rect[1]
        
        # Grab screen matching virtual virtual screen size
        try:
            screen = ImageGrab.grab(bbox=screen_rect)
        except Exception:
            screen = ImageGrab.grab() # fallback
            
        width, height = screen.size
        
        # Resize to speed up (factor of 3)
        scale = 3
        small = screen.resize((width // scale, height // scale), Image.Resampling.BILINEAR)
        
        # Grayscale and edge detection
        gray = ImageOps.grayscale(small)
        edges = gray.filter(ImageFilter.FIND_EDGES)
        
        # Binarize (using a slightly lower threshold to catch thin/faint icon edges)
        binary = edges.point(lambda p: 255 if p > 25 else 0)
        
        pixels = binary.load()
        w, h = binary.size
        
        visited = set()
        rects = []
        
        # BFS to trace contours and find UI bounding rectangles
        for y in range(0, h, 2):
            for x in range(0, w, 2):
                if pixels[x, y] == 255 and (x, y) not in visited:
                    min_x, max_x = x, x
                    min_y, max_y = y, y
                    
                    queue = [(x, y)]
                    visited.add((x, y))
                    count = 0
                    
                    while queue and count < 500:
                        cx, cy = queue.pop(0)
                        count += 1
                        
                        min_x = min(min_x, cx)
                        max_x = max(max_x, cx)
                        min_y = min(min_y, cy)
                        max_y = max(max_y, cy)
                        
                        for nx, ny in [(cx+2, cy), (cx-2, cy), (cx, cy+2), (cx, cy-2)]:
                            if 0 <= nx < w and 0 <= ny < h:
                                if pixels[nx, ny] == 255 and (nx, ny) not in visited:
                                    visited.add((nx, ny))
                                    queue.append((nx, ny))
                    
                    rw = (max_x - min_x) * scale
                    rh = (max_y - min_y) * scale
                    
                    # Mark only the boundary pixels of the detected box as visited to prevent redundant scans,
                    # keeping the inside empty to allow detecting nested child elements.
                    # This must be done for all boxes (including large ones) to prevent duplicate scans of container edges.
                    for vy in range(min_y, max_y + 1):
                        visited.add((min_x, vy))
                        visited.add((max_x, vy))
                    for vx in range(min_x, max_x + 1):
                        visited.add((vx, min_y))
                        visited.add((vx, max_y))
                    
                    # Accept size typical of buttons, inputs, icons (relaxed minimum to catch small/flat icons, min area 60)
                    if rw >= 6 and rh >= 6 and rw * rh >= 60 and rw <= 300 and rh <= 100:
                        rx1 = screen_rect[0] + min_x * scale
                        ry1 = screen_rect[1] + min_y * scale
                        rx2 = screen_rect[0] + max_x * scale
                        ry2 = screen_rect[1] + max_y * scale
                        rects.append((rx1, ry1, rx2, ry2))
                                
        # Overlapping resolution (similar to Non-Maximum Suppression) using IoU
        filtered_rects = []
        rects.sort(key=lambda r: (r[2]-r[0])*(r[3]-r[1]), reverse=True)
        for r in rects:
            r_area = (r[2]-r[0]) * (r[3]-r[1])
            contained = False
            for fr in filtered_rects:
                fr_area = (fr[2]-fr[0]) * (fr[3]-fr[1])
                overlap_x = max(0, min(r[2], fr[2]) - max(r[0], fr[0]))
                overlap_y = max(0, min(r[3], fr[3]) - max(r[1], fr[1]))
                overlap_area = overlap_x * overlap_y
                
                # Calculate Intersection over Union (IoU) to avoid filtering smaller nested items (like icons in panels)
                union_area = r_area + fr_area - overlap_area
                iou = overlap_area / union_area if union_area > 0 else 0
                if iou > 0.4:
                    contained = True
                    break
            if not contained:
                filtered_rects.append(r)
                
        # Return as (auto.Rect, None) so it matches the UIA scan return signature
        results = []
        for r in filtered_rects:
            uia_rect = auto.Rect(r[0], r[1], r[2], r[3])
            results.append((uia_rect, None))
            
        return results

    def scan_active_image(self) -> list:
        # Perform global image analysis, then filter elements located inside the active window
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return []
            
        try:
            win_rect = win32gui.GetWindowRect(hwnd)
        except Exception:
            return []
            
        all_elements = self.scan_all_image()
        
        filtered = []
        wl, wt, wr, wb = win_rect
        for rect, elem in all_elements:
            cx = (rect.left + rect.right) // 2
            cy = (rect.top + rect.bottom) // 2
            if wl <= cx <= wr and wt <= cy <= wb:
                filtered.append((rect, elem))
        return filtered

    def scan_hybrid(self, active_only: bool) -> list:
        # Run UIA and image scans in parallel using separate threads
        uia_results = []
        image_results = []
        
        def run_uia():
            nonlocal uia_results
            try:
                uia_results = self.scan_active() if active_only else self.scan_all()
            except Exception as e:
                print(f"[KN] Hybrid UIA scan error: {e}")
                
        def run_image():
            nonlocal image_results
            try:
                image_results = self.scan_active_image() if active_only else self.scan_all_image()
            except Exception as e:
                print(f"[KN] Hybrid image scan error: {e}")
                
        t_uia = threading.Thread(target=run_uia, daemon=True)
        t_img = threading.Thread(target=run_image, daemon=True)
        
        t_uia.start()
        t_img.start()
        
        t_uia.join()
        t_img.join()
        
        # Merge results and resolve overlaps
        final_elements = list(uia_results)
        uia_rects = [r for r, _ in uia_results]
        
        import comtypes
        import uiautomation as auto
        
        com_initialized = False
        try:
            comtypes.CoInitialize()
            com_initialized = True
        except Exception:
            pass
            
        try:
            for img_rect, _ in image_results:
                cx = (img_rect.left + img_rect.right) // 2
                cy = (img_rect.top + img_rect.bottom) // 2
                
                # Overlap check with existing UIA elements
                is_duplicate = False
                for uia_r in uia_rects:
                    if uia_r.left <= cx <= uia_r.right and uia_r.top <= cy <= uia_r.bottom:
                        is_duplicate = True
                        break
                        
                if is_duplicate:
                    continue
                    
                # Validation using ElementFromPoint
                try:
                    ctrl = auto.ElementFromPoint(cx, cy)
                    if ctrl:
                        # If it is a known clickable type, upgrade it to a full UIA element
                        if ctrl.ControlType in CLICKABLE_TYPE_IDS:
                            final_elements.append((ctrl.BoundingRectangle, ctrl))
                            uia_rects.append(ctrl.BoundingRectangle)
                            continue
                        # Filter out very large window/pane containers as background noise
                        elif ctrl.ControlType in (50033, 50020):  # Window, Pane
                            if img_rect.width() > 400 or img_rect.height() > 400:
                                continue
                except Exception:
                    pass
                    
                # Pass through the image rect if it represents a distinct element
                final_elements.append((img_rect, None))
        finally:
            if com_initialized:
                try:
                    comtypes.CoUninitialize()
                except Exception:
                    pass
                    
        return final_elements

