from config import Config
from scanner import Scanner
import win32gui
import time

def test_hybrid():
    config = Config()
    scanner = Scanner(config)
    
    hwnd = win32gui.GetForegroundWindow()
    cls = win32gui.GetClassName(hwnd)
    title = win32gui.GetWindowText(hwnd)
    print(f"Foreground Window: {hwnd} | Class: {cls} | Title: {title}")
    
    print("\n--- Running UIA Scan (Active) ---")
    t0 = time.time()
    uia_res = []
    for partial in scanner.scan_active():
        uia_res.extend(partial)
    print(f"UIA Scan took {(time.time()-t0)*1000:.0f}ms, found {len(uia_res)} elements")
    
    print("\n--- Running Image Scan (Active) ---")
    t0 = time.time()
    img_res = []
    for partial in scanner.scan_active_image():
        img_res.extend(partial)
    print(f"Image Scan took {(time.time()-t0)*1000:.0f}ms, found {len(img_res)} elements")
    
    print("\n--- Running Hybrid Scan (Active) ---")
    t0 = time.time()
    hybrid_res = []
    for partial in scanner.scan_hybrid(active_only=True):
        hybrid_res.extend(partial)
    print(f"Hybrid Scan took {(time.time()-t0)*1000:.0f}ms, found {len(hybrid_res)} elements")
    
    # 比較表示
    print(f"\nSummary:")
    print(f"  UIA Elements: {len(uia_res)}")
    print(f"  Image Elements: {len(img_res)}")
    print(f"  Hybrid Elements: {len(hybrid_res)}")
    
    # ハイブリッド要素の内訳（UIAか画像認識か）
    uia_count = sum(1 for _, ctrl in hybrid_res if ctrl is not None)
    img_count = sum(1 for _, ctrl in hybrid_res if ctrl is None)
    print(f"  Hybrid breakdown -> UIA: {uia_count}, Image: {img_count}")

if __name__ == '__main__':
    test_hybrid()
