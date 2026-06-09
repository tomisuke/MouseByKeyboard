import win32gui, comtypes, time
import uiautomation as auto
import sys

sys.stdout.reconfigure(encoding='utf-8')

# 修正後のクリック可能コントロールタイプID
CLICKABLE = frozenset({
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
    50029,  # DataItem
    50031,  # SplitButton
})

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

results_pruned = []
def walk_pruned(c, depth=0):
    if depth > 35:
        return
    try:
        if c.ControlType in CLICKABLE:
            r = c.BoundingRectangle
            if r.width() > 0 and r.height() > 0:
                results_pruned.append((r, c))
                return  # 有効なクリック可能要素の場合のみプルーニング
        for child in c.GetChildren():
            walk_pruned(child, depth+1)
    except Exception as e:
        pass

t0 = time.time()
walk_pruned(ctrl)
print(f"Fixed2 pruned walk took {(time.time()-t0)*1000:.0f}ms, found {len(results_pruned)} elements")

print("\n--- Fixed2 pruned walk results ---")
for i, (r, c) in enumerate(results_pruned):
    try:
        print(f"{i:2d}: type={c.ControlType} control_type_name={c.ControlTypeName} name='{c.Name}' rect=({r.left},{r.top},{r.right},{r.bottom})")
    except Exception as e:
        print(f"{i:2d}: Error printing: {e}")

comtypes.CoUninitialize()
