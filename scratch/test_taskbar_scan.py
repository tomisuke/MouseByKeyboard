import win32gui, comtypes, time
import uiautomation as auto

CLICKABLE = frozenset({50000, 50002, 50003, 50004, 50005, 50007, 50011, 50013, 50019, 50024, 50029, 50031})

# Find Taskbar window
hwnd = win32gui.FindWindow("Shell_TrayWnd", None)
if not hwnd:
    print("Taskbar window not found.")
    exit(1)

print(f"HWND: {hwnd}  class: {win32gui.GetClassName(hwnd)}  title: {win32gui.GetWindowText(hwnd)}")

comtypes.CoInitialize()
t0 = time.time()
ctrl = auto.ControlFromHandle(hwnd)
print(f"ControlFromHandle took {(time.time()-t0)*1000:.0f}ms")
if not ctrl:
    print("Could not get control from handle.")
    comtypes.CoUninitialize()
    exit(1)

print(f"ControlType: {ctrl.ControlType}")

results = []
def walk(c, depth=0):
    if depth > 30:
        return
    try:
        if c.ControlType in CLICKABLE:
            r = c.BoundingRectangle
            if r.width() > 0 and r.height() > 0:
                results.append((r, c))
        # Use GetChildren or GetFirstChildControl/GetNextSiblingControl to iterate
        child = c.GetFirstChildControl()
        while child:
            walk(child, depth+1)
            child = child.GetNextSiblingControl()
    except Exception as e:
        pass

t0 = time.time()
walk(ctrl)
elapsed = (time.time()-t0)*1000
print(f"Walk took {elapsed:.0f}ms, found {len(results)} elements")
for r, c in results[:20]:
    try:
        print(f"  type={c.ControlType} name='{c.Name[:30]}' at ({r.left},{r.top}, {r.right}, {r.bottom})")
    except Exception as e:
        print(f"  error reading element: {e}")

comtypes.CoUninitialize()
