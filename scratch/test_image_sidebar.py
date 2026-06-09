import sys
import os
import win32gui
import time

# Add workspace root to path
workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(workspace_root)

from scanner import Scanner

class DummyConfig:
    scan_timeout_ms = 3000

config = DummyConfig()
scanner = Scanner(config)

print("Please click/activate the TickTick window now! Waiting 3 seconds...")
time.sleep(3)

hwnd = win32gui.GetForegroundWindow()
print(f"Current Active Window: Title='{win32gui.GetWindowText(hwnd)}', Class='{win32gui.GetClassName(hwnd)}'")

# Let's perform image scanning and see what rectangles are found on the left side
print("Running scan_active_image()...")
results = scanner.scan_active_image()
print(f"Total elements found via Image Scan in active window: {len(results)}")

try:
    win_rect = win32gui.GetWindowRect(hwnd)
    wl, wt, wr, wb = win_rect
    print(f"Active Window Rect: {win_rect}")
    
    left_elements = []
    for rect, elem in results:
        if rect.left < wl + 60:
            left_elements.append(rect)
            
    print(f"\nFound {len(left_elements)} image-scan elements in far left side (X < window_left + 60):")
    left_elements.sort(key=lambda r: r.top)
    for idx, r in enumerate(left_elements):
        print(f"[{idx}] Rect=({r.left}, {r.top}, {r.right}, {r.bottom}), WxH={r.right-r.left}x{r.bottom-r.top}")
except Exception as e:
    import traceback
    traceback.print_exc()
