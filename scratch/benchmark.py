import time
import win32gui
import win32api
import win32con
import comtypes
import threading
from concurrent.futures import ProcessPoolExecutor
import uiautomation as auto

CLICKABLE_TYPE_IDS = {50000, 50002, 50003, 50004, 50005, 50007, 50011, 50013, 50019, 50024, 50029, 50031}
LEAF_TYPE_IDS = {50000, 50002, 50004, 50005, 50011, 50013, 50031}

# Sub-tree scan worker that resolves a path of child indices
def _sub_scan_worker(hwnd, path, timeout_ms, screen_rect):
    import comtypes
    import time
    import uiautomation as auto
    
    results = []
    
    def _is_out_of_screen(r, s_rect):
        sl, st, sr, sb = s_rect
        try:
            return r.right <= sl or r.left >= sr or r.bottom <= st or r.top >= sb
        except Exception:
            return True

    def _walk(ctrl, depth=0):
        if depth > 30 or (time.time() - start_time > timeout_sec):
            return
        try:
            r = ctrl.BoundingRectangle
            if r.width() <= 0 or r.height() <= 0:
                return
            if depth <= 2 and _is_out_of_screen(r, screen_rect):
                return
                
            ctype = ctrl.ControlType
            is_clickable = ctype in CLICKABLE_TYPE_IDS
            if is_clickable:
                results.append((r.left, r.top, r.right, r.bottom))
                
            if is_clickable and (ctype in LEAF_TYPE_IDS):
                return
                
            child = ctrl.GetFirstChildControl()
            while child:
                if time.time() - start_time > timeout_sec:
                    break
                _walk(child, depth + 1)
                child = child.GetNextSiblingControl()
        except Exception:
            pass

    comtypes.CoInitialize()
    start_time = time.time()
    timeout_sec = timeout_ms / 1000.0
    try:
        ctrl = auto.ControlFromHandle(hwnd)
        if ctrl:
            # Resolve the path to the target sub-tree
            target = ctrl
            for index in path:
                children = target.GetChildren()
                if 0 <= index < len(children):
                    target = children[index]
                else:
                    target = None
                    break
            
            if target:
                _walk(target)
    except Exception:
        pass
    finally:
        comtypes.CoUninitialize()
        
    return results

# Standard single-window scan worker
def _single_scan_worker(hwnd, timeout_ms, screen_rect):
    return _sub_scan_worker(hwnd, [], timeout_ms, screen_rect)

def run_benchmark():
    hwnd = win32gui.GetForegroundWindow()
    title = win32gui.GetWindowText(hwnd).strip()
    cls = win32gui.GetClassName(hwnd)
    print(f"Target HWND: {hwnd} | Class: {cls} | Title: {title[:30]}")
    screen_rect = (0, 0, 1920, 1080)
    
    # 1. Warm-up ProcessPool
    t_init = time.time()
    pool = ProcessPoolExecutor(max_workers=8)
    # Warm up 8 processes
    warm_up_futures = [pool.submit(abs, -1) for _ in range(8)]
    for f in warm_up_futures:
        f.result()
    print(f"ProcessPool Initialization and Warmup took: {(time.time() - t_init)*1000:.1f}ms")
    
    # 2. Measure Single-process scan on the same window
    t0 = time.time()
    single_res = pool.submit(_single_scan_worker, hwnd, 2000, screen_rect).result()
    t_single = (time.time() - t0) * 1000
    print(f"Single-process Window Scan took: {t_single:.1f}ms, found {len(single_res)} elements")
    
    # 3. Window internal parallel scan:
    # First, main process fetches 1st-level children indices
    comtypes.CoInitialize()
    children_count = 0
    try:
        ctrl = auto.ControlFromHandle(hwnd)
        if ctrl:
            children_count = len(ctrl.GetChildren())
    except Exception:
        pass
    finally:
        comtypes.CoUninitialize()
        
    print(f"Window has {children_count} first-level children. Spawning sub-scans in parallel...")
    
    if children_count > 0:
        t0 = time.time()
        parallel_results = []
        # Submit each first-level child index as a path [i]
        futures = [pool.submit(_sub_scan_worker, hwnd, [i], 2000, screen_rect) for i in range(children_count)]
        for f in futures:
            parallel_results.extend(f.result())
        t_parallel = (time.time() - t0) * 1000
        print(f"Parallel Sub-tree Window Scan took: {t_parallel:.1f}ms, found {len(parallel_results)} elements")
    else:
        print("No children to parallelize")
        
    pool.shutdown()

if __name__ == '__main__':
    run_benchmark()
