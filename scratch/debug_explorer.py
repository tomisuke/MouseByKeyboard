import win32gui, comtypes, time
import uiautomation as auto
import sys

# Windows Terminal / cmd.exe の文字化け対策（UTF-8出力）
sys.stdout.reconfigure(encoding='utf-8')

CLICKABLE = frozenset({50000,50005,50007,50008,50010,50012,50015,50021,50025,50028,50031,50034})

# Find File Explorer window
hwnd = 0
def cb(h, _):
    global hwnd
    cls = win32gui.GetClassName(h)
    if cls in ('CabinetWClass', 'ExploreWClass'):
        hwnd = h
        return False
    return True

win32gui.EnumWindows(cb, None)
if not hwnd:
    hwnd = win32gui.GetForegroundWindow()

print(f"HWND: {hwnd}  class: {win32gui.GetClassName(hwnd)}")

comtypes.CoInitialize()
t0 = time.time()
ctrl = auto.ControlFromHandle(hwnd)
print(f"ControlFromHandle took {(time.time()-t0)*1000:.0f}ms")

# プルーニングあり (scanner.py と同じロジック) での走査
results_pruned = []
def walk_pruned(c, depth=0):
    if depth > 35:
        return
    try:
        if c.ControlType in CLICKABLE:
            r = c.BoundingRectangle
            if r.width() > 0 and r.height() > 0:
                results_pruned.append((r, c))
            return  # プルーニング
        for child in c.GetChildren():
            walk_pruned(child, depth+1)
    except Exception as e:
        pass

# プルーニングなしでの走査
results_full = []
def walk_full(c, depth=0):
    if depth > 35:
        return
    try:
        if c.ControlType in CLICKABLE:
            r = c.BoundingRectangle
            if r.width() > 0 and r.height() > 0:
                results_full.append((r, c))
        for child in c.GetChildren():
            walk_full(child, depth+1)
    except Exception as e:
        pass

t0 = time.time()
walk_pruned(ctrl)
print(f"Pruned walk took {(time.time()-t0)*1000:.0f}ms, found {len(results_pruned)} elements")

t0 = time.time()
walk_full(ctrl)
print(f"Full walk took {(time.time()-t0)*1000:.0f}ms, found {len(results_full)} elements")

print("\n--- Pruned walk results (first 40) ---")
for i, (r, c) in enumerate(results_pruned[:40]):
    try:
        print(f"{i:2d}: type={c.ControlType} control_type_name={c.ControlTypeName} name='{c.Name}' rect=({r.left},{r.top},{r.right},{r.bottom})")
    except Exception as e:
        print(f"{i:2d}: Error printing: {e}")

print("\n--- Full walk results (elements in Full but NOT in Pruned, first 40) ---")
pruned_names = {c.Name for r, c in results_pruned}
diff_count = 0
for i, (r, c) in enumerate(results_full):
    if c.Name not in pruned_names:
        diff_count += 1
        try:
            print(f"{diff_count:2d}: type={c.ControlType} control_type_name={c.ControlTypeName} name='{c.Name}' rect=({r.left},{r.top},{r.right},{r.bottom})")
        except Exception as e:
            print(f"{diff_count:2d}: Error printing: {e}")
        if diff_count >= 40:
            break

comtypes.CoUninitialize()
