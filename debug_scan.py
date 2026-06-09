import win32gui, comtypes, time
import uiautomation as auto

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
        for child in c.GetChildren():
            walk(child, depth+1)
    except Exception as e:
        pass

t0 = time.time()
walk(ctrl)
elapsed = (time.time()-t0)*1000
print(f"Walk took {elapsed:.0f}ms, found {len(results)} elements")
for r, c in results[:10]:
    try:
        print(f"  type={c.ControlType} name='{c.Name[:20]}' at ({r.left},{r.top})")
    except:
        pass

comtypes.CoUninitialize()
