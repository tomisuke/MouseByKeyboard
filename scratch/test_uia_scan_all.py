import sys
import os
import time

# Add workspace root to path
workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(workspace_root)

from scanner import Scanner

class DummyConfig:
    scan_timeout_ms = 3000

config = DummyConfig()
scanner = Scanner(config)

print("Running scanner.scan_all()...")
t0 = time.time()
try:
    results = scanner.scan_all()
    t_elapsed = (time.time() - t0) * 1000
    print(f"Success! Found {len(results)} elements using optimized parallel UIA scan in {t_elapsed:.1f}ms")
except Exception as e:
    import traceback
    traceback.print_exc()

print("\nRunning scanner.scan_active()...")
t0 = time.time()
try:
    results_active = scanner.scan_active()
    t_elapsed_active = (time.time() - t0) * 1000
    print(f"Success! Found {len(results_active)} elements in active window in {t_elapsed_active:.1f}ms")
except Exception as e:
    import traceback
    traceback.print_exc()
