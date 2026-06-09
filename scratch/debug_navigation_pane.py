import win32gui, comtypes, time
import uiautomation as auto
import sys

sys.stdout.reconfigure(encoding='utf-8')

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
ctrl = auto.ControlFromHandle(hwnd)

# ナビゲーションペインらしきもの、または TreeItemControl を探す
all_elements = []
def walk_all(c, depth=0):
    if depth > 40:
        return
    try:
        all_elements.append(c)
        for child in c.GetChildren():
            walk_all(child, depth+1)
    except Exception:
        pass

t0 = time.time()
walk_all(ctrl)
print(f"Walk took {(time.time()-t0)*1000:.0f}ms, found {len(all_elements)} elements")

# TreeItemControl またはそれに類するものをフィルタして出力
print("\n--- TreeItemControl elements in the tree ---")
tree_items = [c for c in all_elements if c.ControlType in (50024, 50023)] # TreeItemControl (50024), TreeControl (50023)
for i, c in enumerate(tree_items):
    r = c.BoundingRectangle
    print(f"{i:2d}: type={c.ControlType} name='{c.Name}' rect=({r.left},{r.top},{r.right},{r.bottom})")

# 'ホーム' や 'ダウンロード' や 'Local' という名前を含む要素を探す
print("\n--- Elements containing specific navigation names ---")
target_names = ["ホーム", "ダウンロード", "Local", "Tomisuke", "ローカル ディスク", "ゴミ箱"]
found_targets = []
for c in all_elements:
    try:
        name = c.Name
        if any(t in name for t in target_names):
            found_targets.append(c)
    except Exception:
        pass

for i, c in enumerate(found_targets[:40]):
    r = c.BoundingRectangle
    print(f"{i:2d}: type={c.ControlType} type_name={c.ControlTypeName} name='{c.Name}' rect=({r.left},{r.top},{r.right},{r.bottom})")

comtypes.CoUninitialize()
