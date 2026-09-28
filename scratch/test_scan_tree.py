import win32gui
import comtypes
import time
import threading
import uiautomation as auto

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
    50025,  # Custom (追加)
    50029,  # DataItem
    50031,  # SplitButton
})

# 末端要素（子要素をこれ以上探索しない）
LEAF_TYPE_IDS = frozenset({
    50000,  # Button
    50002,  # CheckBox
    50004,  # Edit
    50005,  # Hyperlink
    50011,  # MenuItem
    50013,  # RadioButton
    50031,  # SplitButton
})

def scan_tree_original(ctrl, results, stop, depth=0):
    if stop.is_set() or depth > 18:
        return
    try:
        r = ctrl.BoundingRectangle
        if r.width() <= 0 or r.height() <= 0:
            return
        # 元の定義（50025なし、かつ見つかったら即終了）
        orig_clickable_ids = CLICKABLE_TYPE_IDS - {50025}
        if ctrl.ControlType in orig_clickable_ids:
            results.append((r, ctrl))
            return
        if not stop.is_set():
            child = ctrl.GetFirstChildControl()
            while child and not stop.is_set():
                scan_tree_original(child, results, stop, depth + 1)
                child = child.GetNextSiblingControl()
    except Exception:
        pass

def scan_tree_improved(ctrl, results, stop, depth=0):
    if stop.is_set() or depth > 18:
        return
    try:
        r = ctrl.BoundingRectangle
        if r.width() <= 0 or r.height() <= 0:
            return
        
        is_clickable = False
        if ctrl.ControlType in CLICKABLE_TYPE_IDS:
            is_clickable = True
        elif ctrl.ControlType in (50020, 50030):  # Text, Document
            # Text/DocumentでかつIsClickableがTrueの場合のみクリック可能とする
            try:
                if ctrl.IsClickable:
                    is_clickable = True
            except:
                pass
                
        if is_clickable:
            results.append((r, ctrl))
            
        # 改善ロジック：末端要素（LEAF）以外は子要素の探索を継続する
        # Custom (50025) や Text (50020) はLEAFに入っていないので子探索される
        if is_clickable and (ctrl.ControlType in LEAF_TYPE_IDS):
            return
            
        if not stop.is_set():
            child = ctrl.GetFirstChildControl()
            while child and not stop.is_set():
                scan_tree_improved(child, results, stop, depth + 1)
                child = child.GetNextSiblingControl()
    except Exception:
        pass

def run_test():
    import win32gui
    
    hwnds = []
    def enum_cb(h, _):
        if win32gui.IsWindowVisible(h) and not win32gui.IsIconic(h):
            title = win32gui.GetWindowText(h).strip()
            cls = win32gui.GetClassName(h)
            if title and cls not in ('Shell_TrayWnd', 'Progman', 'WorkerW'):
                hwnds.append((h, cls, title))
        return True
    win32gui.EnumWindows(enum_cb, None)
    
    print(f"Found {len(hwnds)} visible windows to test.\n")
    
    comtypes.CoInitialize()
    try:
        for hwnd, cls, title in hwnds[:10]: # テスト対象を最初の10個に制限
            print(f"Testing Window: {hwnd} | Class: {cls} | Title: '{title[:40]}'")
            try:
                ctrl = auto.ControlFromHandle(hwnd)
                if not ctrl:
                    print("  Failed to get control from handle.")
                    continue
                
                # 1. 元のロジックでスキャン
                results_orig = []
                stop_orig = threading.Event()
                t0 = time.time()
                scan_tree_original(ctrl, results_orig, stop_orig)
                t_orig = (time.time() - t0) * 1000
                
                # 2. 改善後のロジックでスキャン
                results_imp = []
                stop_imp = threading.Event()
                t0 = time.time()
                scan_tree_improved(ctrl, results_imp, stop_imp)
                t_imp = (time.time() - t0) * 1000
                
                diff = len(results_imp) - len(results_orig)
                print(f"  Original: {len(results_orig)} elements ({t_orig:.1f}ms) | Improved: {len(results_imp)} elements ({t_imp:.1f}ms) | Diff: +{diff}")
                
                if diff > 0:
                    orig_paths = set(c.GetRuntimeId() for _, c in results_orig if c)
                    added = []
                    for r, c in results_imp:
                        try:
                            if c.GetRuntimeId() not in orig_paths:
                                added.append(c)
                        except:
                            pass
                    print(f"  Sample added elements (up to 5):")
                    for c in added[:5]:
                        try:
                            print(f"    - Type: {c.ControlType} | Name: '{c.Name}'")
                        except:
                            pass
            except Exception as e:
                print(f"  Error testing window: {e}")
            print("-" * 50)
                
    finally:
        comtypes.CoUninitialize()

if __name__ == '__main__':
    run_test()
