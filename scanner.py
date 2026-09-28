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


def _worker_init_dpi_aware() -> None:
    """ProcessPoolExecutor のワーカープロセスを Per-Monitor DPI Aware v2 に設定する。

    未設定だと UIA の BoundingRectangle がプライマリモニタ基準に仮想化され、
    サブディスプレイ上の要素座標がズレる（要素が画面外判定で消える等）。
    """
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


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

LEAF_TYPE_IDS = frozenset({
    50000,  # Button
    50002,  # CheckBox
    50004,  # Edit
    50005,  # Hyperlink
    50011,  # MenuItem
    50013,  # RadioButton
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


def _is_invalid_active_window(hwnd: int) -> bool:
    if not hwnd:
        return True
    try:
        import win32gui
        
        # 1. 可視性および最小化のチェック
        if not win32gui.IsWindowVisible(hwnd):
            return True
        if win32gui.IsIconic(hwnd):
            return True
            
        # 2. クローク状態のチェック
        if _is_cloaked(hwnd):
            return True
            
        cls = win32gui.GetClassName(hwnd)
        # 3. クラス名のチェック (DDMExtension やタスクバー等も無効とする)
        invalid_classes = {'Progman', 'WorkerW', 'DDMExtension', 'Shell_TrayWnd'} | EXCLUDED_WINDOW_CLASSES
        if cls in invalid_classes:
            return True
            
        # 4. タイトルチェック (タイトルが無いものは除外)
        title = win32gui.GetWindowText(hwnd).strip()
        if not title:
            return True
            
        # 5. サイズチェック (極小ウィンドウは除外)
        try:
            r = win32gui.GetWindowRect(hwnd)
            w = r[2] - r[0]
            h = r[3] - r[1]
            if w <= 100 or h <= 100:
                return True
        except Exception:
            return True
            
    except Exception:
        return True
    return False


def _get_fallback_active_window() -> int:
    """Zオーダー順にウィンドウを走査し、最初に見つかった有効なウィンドウのHWNDを返す"""
    found_hwnd = [0]
    
    def enum_cb(hwnd, _):
        if not _is_invalid_active_window(hwnd):
            found_hwnd[0] = hwnd
            return False  # 列挙終了
        return True
        
    try:
        import win32gui
        win32gui.EnumWindows(enum_cb, None)
    except Exception:
        pass
    return found_hwnd[0]


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


def _scan_tree(ctrl, results: list, stop: threading.Event, screen_rect: tuple, start_time: float, timeout_sec: float, depth: int = 0) -> None:
    import time
    if stop.is_set() or depth > 30 or (time.time() - start_time > timeout_sec):
        return
    try:
        r = ctrl.BoundingRectangle
        if r.width() <= 0 or r.height() <= 0:
            return
            
        # 画面外の要素は子要素も含めてスキップ (depth <= 2 の上位コンテナに限定してオーバーヘッドを防ぐ)
        if depth <= 2 and _is_out_of_screen(r, screen_rect):
            return
        
        is_clickable = ctrl.ControlType in CLICKABLE_TYPE_IDS
        if is_clickable:
            results.append((r, ctrl))
            
        if is_clickable and (ctrl.ControlType in LEAF_TYPE_IDS):
            return
            
        if not stop.is_set() and (time.time() - start_time <= timeout_sec):
            child = ctrl.GetFirstChildControl()
            while child and not stop.is_set():
                if time.time() - start_time > timeout_sec:
                    break
                _scan_tree(child, results, stop, screen_rect, start_time, timeout_sec, depth + 1)
                child = child.GetNextSiblingControl()
    except Exception:
        pass


def _resolve_uia_duplicates(elements: list) -> list:
    """Resolve duplicates in UIA scan elements by removing items with nearly identical centers and sizes."""
    unique_elements = []
    for r, ctrl in elements:
        cx = (r.left + r.right) // 2
        cy = (r.top + r.bottom) // 2
        w = r.width()
        h = r.height()
        
        is_dup = False
        for ur, _ in unique_elements:
            ucx = (ur.left + ur.right) // 2
            ucy = (ur.top + ur.bottom) // 2
            uw = ur.width()
            uh = ur.height()
            
            # If center distance is <= 3px and size difference is <= 5px, treat as duplicate
            if abs(cx - ucx) <= 3 and abs(cy - ucy) <= 3 and abs(w - uw) <= 5 and abs(h - uh) <= 5:
                is_dup = True
                break
        if not is_dup:
            unique_elements.append((r, ctrl))
    return unique_elements


def _scan_hwnd(hwnd: int, timeout_ms: int, screen_rect: tuple[int, int, int, int]) -> list:
    import time
    import comtypes
    results: list = []
    stop = threading.Event()

    comtypes.CoInitialize()
    try:
        auto = _get_auto()
        ctrl = auto.ControlFromHandle(hwnd)
        start_time = time.time()
        timeout_sec = timeout_ms / 1000.0
        _scan_tree(ctrl, results, stop, screen_rect, start_time, timeout_sec)
    except Exception:
        pass
    finally:
        try:
            comtypes.CoUninitialize()
        except Exception:
            pass

    return results


def _scan_hwnd_process(hwnd: int, timeout_ms: int, screen_rect: tuple[int, int, int, int]) -> list:
    import time
    import comtypes
    import threading
    results: list = []
    stop = threading.Event()

    comtypes.CoInitialize()
    try:
        auto_module = _get_auto()
        ctrl = auto_module.ControlFromHandle(hwnd)
        if ctrl:
            start_time = time.time()
            timeout_sec = timeout_ms / 1000.0
            _scan_tree(ctrl, results, stop, screen_rect, start_time, timeout_sec)
    except Exception:
        pass
    finally:
        try:
            comtypes.CoUninitialize()
        except Exception:
            pass

    # シリアライズ可能なプレーンデータ（Rect座標のタプル）のみ返却
    return [(r.left, r.top, r.right, r.bottom) for r, _ in results]


def _scan_hwnd_process_path(hwnd: int, path: list[int], timeout_ms: int, screen_rect: tuple[int, int, int, int]) -> list:
    import time
    import comtypes
    import threading
    import uiautomation as auto
    
    results: list = []
    stop = threading.Event()

    comtypes.CoInitialize()
    try:
        auto_module = _get_auto()
        ctrl = auto_module.ControlFromHandle(hwnd)
        if ctrl:
            # 経路パスを解決してターゲット要素を特定
            target = ctrl
            for index in path:
                children = target.GetChildren()
                if 0 <= index < len(children):
                    target = children[index]
                else:
                    target = None
                    break
            
            if target:
                start_time = time.time()
                timeout_sec = timeout_ms / 1000.0
                _scan_tree(target, results, stop, screen_rect, start_time, timeout_sec)
    except Exception:
        pass
    finally:
        try:
            comtypes.CoUninitialize()
        except Exception:
            pass

    return [(r.left, r.top, r.right, r.bottom) for r, _ in results]


def _scan_ocr(screen_img, screen_rect) -> list:
    """Scan the screen using Windows.Media.Ocr (via winrt)."""
    try:
        import winrt.windows.media.ocr as ocr
        import winrt.windows.graphics.imaging as imaging
        import winrt.windows.storage.streams as streams
        import io
        import asyncio
        import uiautomation as auto

        bytes_io = io.BytesIO()
        screen_img.save(bytes_io, format='PNG')
        bytes_data = bytes_io.getvalue()

        async def _run():
            writer = streams.DataWriter()
            writer.write_bytes(bytes_data)
            buffer = writer.detach_buffer()

            stream = streams.InMemoryRandomAccessStream()
            await stream.write_async(buffer)
            stream.seek(0)

            decoder = await imaging.BitmapDecoder.create_async(stream)
            software_bitmap = await decoder.get_software_bitmap_async()

            engine = ocr.OcrEngine.try_create_from_user_profile_languages()
            if not engine:
                return []

            result = await engine.recognize_async(software_bitmap)
            
            elements = []
            for line in result.lines:
                words = list(line.words)
                if not words:
                    continue
                
                # Sort words from left to right to ensure physical order
                words.sort(key=lambda w: w.bounding_rect.x)
                
                # Group nearby words
                groups = []
                current_group = [words[0]]
                
                for word in words[1:]:
                    prev_word = current_group[-1]
                    prev_r = prev_word.bounding_rect
                    curr_r = word.bounding_rect
                    
                    # Horizontal gap between words
                    gap = curr_r.x - (prev_r.x + prev_r.width)
                    # Threshold for grouping (height of words * 1.3 to handle normal spaces and small segmentations)
                    threshold = ((prev_r.height + curr_r.height) / 2.0) * 1.3
                    
                    # Check vertical overlap to ensure they are on the same general row
                    y_overlap = max(0, min(prev_r.y + prev_r.height, curr_r.y + curr_r.height) - max(prev_r.y, curr_r.y))
                    is_same_row = y_overlap > 0
                    
                    if gap <= threshold and is_same_row:
                        current_group.append(word)
                    else:
                        groups.append(current_group)
                        current_group = [word]
                groups.append(current_group)
                
                # Calculate bounding box for each group
                for gp in groups:
                    first_r = gp[0].bounding_rect
                    min_x = first_r.x
                    min_y = first_r.y
                    max_x = min_x + first_r.width
                    max_y = min_y + first_r.height
                    
                    for w in gp[1:]:
                        r = w.bounding_rect
                        min_x = min(min_x, r.x)
                        min_y = min(min_y, r.y)
                        max_x = max(max_x, r.x + r.width)
                        max_y = max(max_y, r.y + r.height)
                        
                    rx1 = screen_rect[0] + min_x
                    ry1 = screen_rect[1] + min_y
                    rx2 = screen_rect[0] + max_x
                    ry2 = screen_rect[1] + max_y
                    
                    uia_rect = auto.Rect(int(rx1), int(ry1), int(rx2), int(ry2))
                    elements.append((uia_rect, None))
            return elements

        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(_run())
        finally:
            loop.close()

    except Exception as e:
        print(f"[KN] winrt OCR scanner failed: {e}")
        return []


def _scan_cv(screen_img, screen_rect) -> list:
    """Scan the screen using Pillow edge/contour detection."""
    from PIL import Image, ImageOps, ImageFilter
    import uiautomation as auto
    
    width, height = screen_img.size
    
    # Scale factor (2 instead of 3 for better accuracy)
    scale = 2
    small = screen_img.resize((width // scale, height // scale), Image.Resampling.BILINEAR)
    
    # Grayscale and edge detection
    gray = ImageOps.grayscale(small)
    edges = gray.filter(ImageFilter.FIND_EDGES)
    
    # Binarize with a lower threshold (15 instead of 25 to catch faint boundaries)
    binary = edges.point(lambda p: 255 if p > 15 else 0)
    
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
                
                while queue and count < 600:
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
                
                for vy in range(min_y, max_y + 1):
                    visited.add((min_x, vy))
                    visited.add((max_x, vy))
                for vx in range(min_x, max_x + 1):
                    visited.add((vx, min_y))
                    visited.add((vx, max_y))
                
                # Extended size limits (rw <= 600, rh <= 120) to capture tabs and inputs
                if rw >= 6 and rh >= 6 and rw * rh >= 60 and rw <= 600 and rh <= 120:
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
            
            union_area = r_area + fr_area - overlap_area
            iou = overlap_area / union_area if union_area > 0 else 0
            if iou > 0.4:
                contained = True
                break
        if not contained:
            filtered_rects.append(r)
            
    results = []
    for r in filtered_rects:
        uia_rect = auto.Rect(r[0], r[1], r[2], r[3])
        results.append((uia_rect, None))
        
    return results
def _grab_screen_gdi(rect=None):
    """Grab the screen using Windows GDI API via ctypes, supporting multiple monitors."""
    import ctypes
    from ctypes import wintypes
    from PIL import Image
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    
    # 64-bit handle safety declarations
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    
    gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    
    gdi32.BitBlt.argtypes = [
        wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_uint32
    ]
    gdi32.BitBlt.restype = wintypes.BOOL
    
    gdi32.GetDIBits.argtypes = [
        wintypes.HDC, wintypes.HBITMAP, ctypes.c_uint, ctypes.c_uint,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint
    ]
    gdi32.GetDIBits.restype = ctypes.c_int
    
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteObject.restype = wintypes.BOOL
    
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.DeleteDC.restype = wintypes.BOOL
    
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.ReleaseDC.restype = ctypes.c_int

    gdi32.CreateDCW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p]
    gdi32.CreateDCW.restype = wintypes.HDC

    gdi32.PatBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint32]
    gdi32.PatBlt.restype = wintypes.BOOL
    
    if rect is None:
        left = user32.GetSystemMetrics(76) # SM_XVIRTUALSCREEN
        top = user32.GetSystemMetrics(77) # SM_YVIRTUALSCREEN
        width = user32.GetSystemMetrics(78) # SM_CXVIRTUALSCREEN
        height = user32.GetSystemMetrics(79) # SM_CYVIRTUALSCREEN
        right = left + width
        bottom = top + height
    else:
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top

    # Create target Pillow Image
    final_img = Image.new("RGB", (width, height), (0, 0, 0))
    
    import win32api
    monitors = win32api.EnumDisplayMonitors()
    for hMonitor, _, m_rect in monitors:
        # Calculate overlapping bounding box
        ol = max(left, m_rect[0])
        ot = max(top, m_rect[1])
        or_ = min(right, m_rect[2])
        ob = min(bottom, m_rect[3])
        
        if ol < or_ and ot < ob:
            ow = or_ - ol
            oh = ob - ot
            
            info = win32api.GetMonitorInfo(hMonitor)
            device_name = info['Device']
            
            hdc_monitor = gdi32.CreateDCW(None, device_name, None, None)
            if hdc_monitor:
                hdc_mem = gdi32.CreateCompatibleDC(hdc_monitor)
                hbitmap = gdi32.CreateCompatibleBitmap(hdc_monitor, ow, oh)
                hobj_old = gdi32.SelectObject(hdc_mem, hbitmap)
                
                # Source coords relative to monitor left-top (0, 0)
                src_x = ol - m_rect[0]
                src_y = ot - m_rect[1]
                gdi32.BitBlt(hdc_mem, 0, 0, ow, oh, hdc_monitor, src_x, src_y, 0x00CC0020)
                
                class BITMAPINFOHEADER(ctypes.Structure):
                    _fields_ = [
                        ('biSize', ctypes.c_uint32),
                        ('biWidth', ctypes.c_int32),
                        ('biHeight', ctypes.c_int32),
                        ('biPlanes', ctypes.c_uint16),
                        ('biBitCount', ctypes.c_uint16),
                        ('biCompression', ctypes.c_uint32),
                        ('biSizeImage', ctypes.c_uint32),
                        ('biXPelsPerMeter', ctypes.c_int32),
                        ('biYPelsPerMeter', ctypes.c_int32),
                        ('biClrUsed', ctypes.c_uint32),
                        ('biClrImportant', ctypes.c_uint32),
                    ]
                    
                class BITMAPINFO(ctypes.Structure):
                    _fields_ = [
                        ('bmiHeader', BITMAPINFOHEADER),
                        ('bmiColors', ctypes.c_uint32 * 3),
                    ]
                    
                bmi = BITMAPINFO()
                bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
                bmi.bmiHeader.biWidth = ow
                bmi.bmiHeader.biHeight = -oh  # top-down
                bmi.bmiHeader.biPlanes = 1
                bmi.bmiHeader.biBitCount = 32
                bmi.bmiHeader.biCompression = 0
                
                buffer_size = ow * oh * 4
                image_buffer = ctypes.create_string_buffer(buffer_size)
                
                # Deselect hbitmap from hdc_mem before calling GetDIBits
                gdi32.SelectObject(hdc_mem, hobj_old)
                
                gdi32.GetDIBits(hdc_monitor, hbitmap, 0, oh, image_buffer, ctypes.byref(bmi), 0)
                
                monitor_img = Image.frombuffer("RGBA", (ow, oh), image_buffer, "raw", "BGRA", 0, 1)
                monitor_img_rgb = monitor_img.convert("RGB")
                
                # Destination coords relative to target rect left-top
                dest_x = ol - left
                dest_y = ot - top
                final_img.paste(monitor_img_rgb, (dest_x, dest_y))
                
                gdi32.DeleteObject(hbitmap)
                gdi32.DeleteDC(hdc_mem)
                gdi32.DeleteDC(hdc_monitor)
                
    return final_img


class Scanner:
    def __init__(self, config) -> None:
        self.config = config
        
        # 常駐型プロセスプールの初期化とウォームアップ (GIL競合を回避するため)
        from concurrent.futures import ProcessPoolExecutor
        max_workers = max(1, self.config.max_scan_windows)
        self._process_pool = ProcessPoolExecutor(max_workers=max_workers, initializer=_worker_init_dpi_aware)
        try:
            # プロセスを事前に立ち上げてスキャン実行時のラグを防ぐ
            futures = [self._process_pool.submit(abs, -1) for _ in range(max_workers)]
            for f in futures:
                f.result()
        except Exception as e:
            print(f"[KN] ProcessPool Warmup error: {e}")

    def shutdown(self) -> None:
        if hasattr(self, '_process_pool'):
            try:
                # Force terminate all running worker processes to prevent them from hanging
                for proc in self._process_pool._processes.values():
                    if proc.is_alive():
                        proc.terminate()
            except Exception as e:
                print(f"[KN] Failed to terminate scanner sub-processes: {e}")

            try:
                self._process_pool.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                # Fallback for Python versions < 3.9 which do not support cancel_futures
                try:
                    self._process_pool.shutdown(wait=False)
                except Exception:
                    pass
            except Exception:
                pass

    def _get_screen_rect(self) -> tuple[int, int, int, int]:
        try:
            x = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
            y = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
            w = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
            h = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
            return (x, y, x + w, y + h)
        except Exception:
            return (0, 0, 1920, 1080)

    def scan_active(self):
        hwnd = win32gui.GetForegroundWindow()
        if _is_invalid_active_window(hwnd):
            hwnd = _get_fallback_active_window()
            if not hwnd:
                hwnd = win32gui.FindWindow("Shell_TrayWnd", None)
                if not hwnd:
                    return
        
        screen_rect = self._get_screen_rect()
        
        try:
            wl, wt, wr, wb = win32gui.GetWindowRect(hwnd)
        except Exception:
            wl, wt, wr, wb = screen_rect

        def filter_elements(elements):
            import uiautomation as auto
            filtered = []
            for item in elements:
                if isinstance(item[0], (tuple, list)):
                    left, top, right, bottom = item[0]
                    r = auto.Rect(left, top, right, bottom)
                    ctrl = None
                elif hasattr(item[0], 'left'):
                    r = item[0]
                    ctrl = item[1]
                else:
                    left, top, right, bottom = item
                    r = auto.Rect(left, top, right, bottom)
                    ctrl = None

                if not _is_out_of_screen(r, screen_rect):
                    cx = (r.left + r.right) // 2
                    cy = (r.top + r.bottom) // 2
                    if wl <= cx <= wr and wt <= cy <= wb:
                        filtered.append((r, ctrl))
            return filtered

        if self.config.parallel_sub_scan:
            # 単一ウィンドウ内並列化（オプトイン）
            import comtypes
            import uiautomation as auto
            children_count = 0
            com_initialized = False
            try:
                comtypes.CoInitialize()
                com_initialized = True
                ctrl = auto.ControlFromHandle(hwnd)
                if ctrl:
                    children_count = len(ctrl.GetChildren())
            except Exception as e:
                print(f"[KN] Error getting children count: {e}")
            finally:
                if com_initialized:
                    try:
                        comtypes.CoUninitialize()
                    except Exception:
                        pass
            
            if children_count > 0:
                futures = []
                # 最大8分割に制限してオーバーヘッドを防ぐ
                limit_children = min(8, children_count)
                for i in range(limit_children):
                    future = self._process_pool.submit(
                        _scan_hwnd_process_path, hwnd, [i], self.config.scan_timeout_ms, screen_rect
                    )
                    futures.append(future)
                
                for future in futures:
                    try:
                        partial = future.result()
                        if partial:
                            partial_elements = [((left, top, right, bottom), None) for left, top, right, bottom in partial]
                            filtered_partial = filter_elements(partial_elements)
                            if filtered_partial:
                                yield filtered_partial
                    except Exception as e:
                        print(f"[KN] Parallel sub-scan error for active window: {e}")
            else:
                raw_elements = _scan_hwnd(hwnd, self.config.scan_timeout_ms, screen_rect)
                filtered = filter_elements(raw_elements)
                if filtered:
                    yield filtered
        else:
            raw_elements = _scan_hwnd(hwnd, self.config.scan_timeout_ms, screen_rect)
            filtered = filter_elements(raw_elements)
            if filtered:
                yield filtered

    def scan_all(self):
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
            return

        # Scan top-most windows first, up to a maximum of visible windows based on config
        hwnds = hwnds[:self.config.max_scan_windows]

        timeout = self.config.scan_timeout_ms
        
        # Keep track of opaque windows processed so far to filter out hidden elements
        processed_opaque_rects: list = []

        # Parallel UIA scanning using Warm ProcessPoolExecutor to avoid GIL bottlenecks
        import uiautomation as auto
        futures_ordered = []
        
        for idx, (hwnd, win_rect, should_block) in enumerate(hwnds):
            is_active_win = (idx == 0)
            
            if self.config.parallel_sub_scan and is_active_win:
                # アクティブウィンドウのみ内部を分割スキャン
                import comtypes
                children_count = 0
                com_initialized = False
                try:
                    comtypes.CoInitialize()
                    com_initialized = True
                    ctrl = auto.ControlFromHandle(hwnd)
                    if ctrl:
                        children_count = len(ctrl.GetChildren())
                except Exception:
                    pass
                finally:
                    if com_initialized:
                        try:
                            comtypes.CoUninitialize()
                        except Exception:
                            pass
                            
                if children_count > 0:
                    limit_children = min(8, children_count)
                    for i in range(limit_children):
                        future = self._process_pool.submit(
                            _scan_hwnd_process_path, hwnd, [i], timeout, screen_rect
                        )
                        futures_ordered.append((future, hwnd, win_rect, should_block))
                else:
                    future = self._process_pool.submit(_scan_hwnd_process, hwnd, timeout, screen_rect)
                    futures_ordered.append((future, hwnd, win_rect, should_block))
            else:
                # 他のウィンドウは通常通り丸ごとスキャン
                future = self._process_pool.submit(_scan_hwnd_process, hwnd, timeout, screen_rect)
                futures_ordered.append((future, hwnd, win_rect, should_block))
        
        for future, hwnd, win_rect, should_block in futures_ordered:
            partial_elements = []
            try:
                partial = future.result()
                if partial:
                    for left, top, right, bottom in partial:
                        r = auto.Rect(left, top, right, bottom)
                        if _is_out_of_screen(r, screen_rect):
                            continue
                        if _is_hidden_by_opaque_windows(r, processed_opaque_rects):
                            continue
                        # プロセス間通信のため element は None として格納 (物理クリックで動作するため問題なし)
                        partial_elements.append((r, None))
            except Exception as e:
                print(f"[KN] Parallel scan error for hwnd {hwnd}: {e}")
            
            if should_block:
                processed_opaque_rects.append(win_rect)

            if partial_elements:
                yield partial_elements

    def scan_all_image(self):
        # Collect clickable elements via image analysis (OCR & Pillow contour detection)
        from PIL import Image, ImageGrab
        
        screen_rect = self._get_screen_rect()
        
        # Grab screen matching virtual virtual screen size
        try:
            screen = _grab_screen_gdi(screen_rect)
        except Exception as e:
            print(f"[KN] GDI screen grab failed: {e}. Falling back to PIL ImageGrab.")
            try:
                screen = ImageGrab.grab(bbox=screen_rect)
            except Exception:
                screen = ImageGrab.grab() # fallback
            
        # 1. OCR scan (highest priority for text detection)
        ocr_elements = _scan_ocr(screen, screen_rect)
        
        # 2. CV scan (for icons and non-text visual elements)
        cv_elements = _scan_cv(screen, screen_rect)
        
        # 3. Merge and resolve duplicates
        # Exclude CV boxes that heavily overlap with OCR text regions to avoid double boxes
        merged_elements = list(ocr_elements)
        
        for cv_rect, _ in cv_elements:
            is_dup = False
            cv_area = cv_rect.width() * cv_rect.height()
            
            for ocr_rect, _ in ocr_elements:
                # Calculate intersection area
                ox = max(0, min(cv_rect.right, ocr_rect.right) - max(cv_rect.left, ocr_rect.left))
                oy = max(0, min(cv_rect.bottom, ocr_rect.bottom) - max(cv_rect.top, ocr_rect.top))
                overlap_area = ox * oy
                
                # Check how much of the OCR text region is covered by this CV box
                ocr_area = ocr_rect.width() * ocr_rect.height()
                overlap_ratio = overlap_area / ocr_area if ocr_area > 0 else 0
                
                # If CV covers more than 50% of the OCR text, treat it as a duplicate
                if overlap_ratio > 0.5:
                    is_dup = True
                    break
                    
            if not is_dup:
                merged_elements.append((cv_rect, None))
                
        if merged_elements:
            yield merged_elements

    def scan_active_image(self):
        # Perform targeted image analysis on the active window only
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        if _is_invalid_active_window(hwnd):
            hwnd = _get_fallback_active_window()
            if not hwnd:
                return
            
        try:
            win_rect = win32gui.GetWindowRect(hwnd)
        except Exception:
            return
            
        wl, wt, wr, wb = win_rect
        ww = wr - wl
        wh = wb - wt
        if ww <= 0 or wh <= 0:
            return

        # Grab only the active window's screen region
        try:
            screen_img = _grab_screen_gdi(win_rect)
        except Exception as e:
            print(f"[KN] GDI active window grab failed: {e}. Falling back to PIL ImageGrab.")
            from PIL import ImageGrab
            try:
                screen_img = ImageGrab.grab(bbox=win_rect)
            except Exception:
                return

        # 1. OCR scan within the window image (pass win_rect as screen_rect for offset conversion)
        ocr_elements = _scan_ocr(screen_img, win_rect)
        
        # 2. CV scan within the window image
        cv_elements = _scan_cv(screen_img, win_rect)
        
        # 3. Merge and resolve duplicates
        merged_elements = list(ocr_elements)
        for cv_rect, _ in cv_elements:
            is_dup = False
            cv_area = cv_rect.width() * cv_rect.height()
            
            for ocr_rect, _ in ocr_elements:
                ox = max(0, min(cv_rect.right, ocr_rect.right) - max(cv_rect.left, ocr_rect.left))
                oy = max(0, min(cv_rect.bottom, ocr_rect.bottom) - max(cv_rect.top, ocr_rect.top))
                overlap_area = ox * oy
                
                ocr_area = ocr_rect.width() * ocr_rect.height()
                overlap_ratio = overlap_area / ocr_area if ocr_area > 0 else 0
                
                if overlap_ratio > 0.5:
                    is_dup = True
                    break
                    
            if not is_dup:
                merged_elements.append((cv_rect, None))
                
        if merged_elements:
            yield merged_elements

    def scan_hybrid(self, active_only: bool):
        # Run UIA and image scans in parallel using separate threads
        import queue
        q = queue.Queue()
        active_threads = 2
        
        def run_uia():
            try:
                gen = self.scan_active() if active_only else self.scan_all()
                for partial in gen:
                    q.put(('uia', partial))
            except Exception as e:
                print(f"[KN] Hybrid UIA scan error: {e}")
            finally:
                q.put(('done', None))
                
        def run_image():
            try:
                gen = self.scan_active_image() if active_only else self.scan_all_image()
                for partial in gen:
                    q.put(('image', partial))
            except Exception as e:
                print(f"[KN] Hybrid image scan error: {e}")
            finally:
                q.put(('done', None))
                
        t_uia = threading.Thread(target=run_uia, daemon=True)
        t_img = threading.Thread(target=run_image, daemon=True)
        
        t_uia.start()
        t_img.start()
        
        import comtypes
        import uiautomation as auto
        
        com_initialized = False
        try:
            comtypes.CoInitialize()
            com_initialized = True
        except Exception:
            pass
            
        uia_rects = []
        
        try:
            while active_threads > 0:
                try:
                    tag, data = q.get(timeout=2.0)
                except queue.Empty:
                    break
                    
                if tag == 'done':
                    active_threads -= 1
                    continue
                    
                if tag == 'uia':
                    for r, _ in data:
                        uia_rects.append(r)
                    yield data
                    
                elif tag == 'image':
                    filtered_img = []
                    for img_rect, _ in data:
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
                            
                        # Filter out very large window/pane containers as background noise
                        if img_rect.width() > 400 or img_rect.height() > 400:
                            continue
                            
                        filtered_img.append((img_rect, None))
                        
                    if filtered_img:
                        yield filtered_img
        finally:
            if com_initialized:
                try:
                    comtypes.CoUninitialize()
                except Exception:
                    pass

