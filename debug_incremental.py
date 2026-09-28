import time
import win32gui
from config import Config
from scanner import Scanner
from hint_manager import generate_tags

def test_fixed_incremental_scan():
    config = Config()
    config.parallel_sub_scan = True
    config.scan_timeout_ms = 2000
    
    scanner = Scanner(config)
    hwnd = win32gui.GetForegroundWindow()
    print(f"Active HWND: {hwnd}  class: {win32gui.GetClassName(hwnd)}")
    
    print("\n--- Testing scan_hybrid() [Generator with Fixed Tags] ---")
    
    from app import App
    import tkinter as tk
    
    root = tk.Tk()
    app = App(root, config)
    
    # スキャン全体の予測要素数を算出
    est_count = app._estimate_elements_count(active_only=True, method='hybrid')
    pregenerated_tags = generate_tags(est_count, config.hint_chars)
    print(f"Estimated Elements: {est_count}, Pregenerated Tags: {len(pregenerated_tags)}")
    
    t0 = time.time()
    accumulated_elements = []
    allocated_tags = {}  # index -> tag_string (インデックス単位でタグを固定化チェック)
    
    iteration = 0
    errors = 0
    
    for partial in scanner.scan_hybrid(active_only=True):
        iteration += 1
        elapsed = (time.time() - t0) * 1000
        
        # 重複排除
        new_unique = []
        for r, ctrl in partial:
            cx = (r.left + r.right) // 2
            cy = (r.top + r.bottom) // 2
            w = r.width()
            h = r.height()
            
            is_dup = False
            for ur, _ in accumulated_elements:
                ucx = (ur.left + ur.right) // 2
                ucy = (ur.top + ur.bottom) // 2
                uw = ur.width()
                uh = ur.height()
                if abs(cx - ucx) <= 3 and abs(cy - ucy) <= 3 and abs(w - uw) <= 5 and abs(h - uh) <= 5:
                    is_dup = True
                    break
            if not is_dup:
                new_unique.append((r, ctrl))
                
        if new_unique:
            accumulated_elements.extend(new_unique)
            
        current_len = len(accumulated_elements)
        if current_len > len(pregenerated_tags):
            print(f"  [RESIZE] Elements ({current_len}) exceeded pregenerated ({len(pregenerated_tags)}). Re-generating...")
            pregenerated_tags = generate_tags(current_len + 100, config.hint_chars)
            
        tags = pregenerated_tags[:current_len]
        
        # インデックスベースの厳格な不変性チェック
        iteration_changes = 0
        for idx, tag in enumerate(tags):
            if idx in allocated_tags:
                previous_tag = allocated_tags[idx]
                if previous_tag != tag:
                    print(f"  [ERROR] Tag changed at index {idx}! '{previous_tag}' -> '{tag}'")
                    errors += 1
                    iteration_changes += 1
            else:
                allocated_tags[idx] = tag
                
        print(f"Iteration {iteration}: batch_size={len(partial)}, accumulated={current_len}, errors_in_tags={iteration_changes} (elapsed: {elapsed:.0f}ms)")
    
    print(f"\nScan finished in {(time.time() - t0)*1000:.0f}ms")
    print(f"Total elements: {len(accumulated_elements)}")
    print(f"Total validation errors (tag changes): {errors}")
    
    scanner.shutdown()
    root.destroy()
    
    assert errors == 0, "Assertion failed: some tags were modified during scan iterations!"
    print("SUCCESS: Verified that no tags changed their characters during incremental scan!")

if __name__ == "__main__":
    test_fixed_incremental_scan()
