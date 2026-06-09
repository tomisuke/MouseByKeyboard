import sys
import os

# Add workspace root to path
workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(workspace_root)

from scanner import Scanner

class DummyConfig:
    scan_timeout_ms = 2000

config = DummyConfig()
scanner = Scanner(config)

print("Starting scan_all_image...")
try:
    results = scanner.scan_all_image()
    print(f"Success! Found {len(results)} elements using image scan.")
    for rect, _ in results[:5]:
        print(f"  Rect: ({rect.left}, {rect.top}, {rect.right}, {rect.bottom})")
except Exception as e:
    import traceback
    traceback.print_exc()

print("\nStarting scan_active_image...")
try:
    results_active = scanner.scan_active_image()
    print(f"Success! Found {len(results_active)} elements in active window using image scan.")
    for rect, _ in results_active[:5]:
        print(f"  Rect: ({rect.left}, {rect.top}, {rect.right}, {rect.bottom})")
except Exception as e:
    import traceback
    traceback.print_exc()
