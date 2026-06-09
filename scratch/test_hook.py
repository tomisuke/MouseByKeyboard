# scratch/test_hook.py
import sys
import os
import time
import ctypes
from ctypes import wintypes

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from keyboard_hook import SelectiveKeyboardHook

_user32 = ctypes.windll.user32

def on_key(name):
    print(f"[TEST] Key pressed: {name} (Blocked)")

hook = SelectiveKeyboardHook(
    callback=on_key,
    hint_chars="fj", # 'f' and 'j' are hints
    prefix_keys=[";", ","] # ';' and ',' are prefixes
)

print("Installing hook...")
if not hook.install():
    print("Failed to install hook!")
    sys.exit(1)

print("Hook installed. Testing selective suppression for 15 seconds.")
print("  - Press 'f', 'j', ';', or ',' -> should show [TEST] Key pressed... and be BLOCKED from reaching other apps.")
print("  - Press other keys (e.g. 'a', 'space', 'enter') -> should NOT show [TEST]... and pass through to other apps.")

# Run message loop
msg = wintypes.MSG()
start_time = time.time()
try:
    while time.time() - start_time < 15:
        # PM_REMOVE = 1
        ret = _user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1)
        if ret:
            _user32.TranslateMessage(ctypes.byref(msg))
            _user32.DispatchMessageW(ctypes.byref(msg))
        time.sleep(0.01)
finally:
    print("Uninstalling hook...")
    hook.uninstall()
    print("Done")
