import sys
import os
import win32gui
import comtypes
import uiautomation as auto

hwnd = 0
def cb(h, _):
    global hwnd
    title = win32gui.GetWindowText(h)
    if 'TickTick' in title or 'TickTick' in win32gui.GetClassName(h):
        hwnd = h
        return False
    return True

win32gui.EnumWindows(cb, None)
if not hwnd:
    hwnd = win32gui.GetForegroundWindow()

comtypes.CoInitialize()
try:
    ctrl = auto.ControlFromHandle(hwnd)
    
    sidebar_container = None
    child = ctrl.GetFirstChildControl()
    while child:
        r = child.BoundingRectangle
        if -5 <= r.left <= 5 and r.width() < 100 and r.height() > 500:
            sidebar_container = child
            break
        child = child.GetNextSiblingControl()
        
    if sidebar_container is None:
        print("Sidebar container not found.")
        sys.exit(0)
        
    print(f"Found Sidebar Container: Type={sidebar_container.ControlTypeName}, Rect={sidebar_container.BoundingRectangle}")
    
    # Dump using RawViewWalker
    walker = auto.RawViewWalker
    elements = []
    
    def dump_raw(c, depth=0):
        if depth > 10:
            return
        try:
            r = c.BoundingRectangle
            elements.append((depth, c.ControlTypeName, c.ControlType, c.Name, (r.left, r.top, r.right, r.bottom)))
        except Exception:
            pass
            
        try:
            child = walker.GetFirstChildElement(c)
            while child:
                dump_raw(child, depth + 1)
                child = walker.GetNextSiblingElement(child)
        except Exception as e:
            print(f"Error traversing raw children: {e}")
            
    dump_raw(sidebar_container)
    
    print(f"\n[RawViewWalker] Dumped {len(elements)} elements:")
    for item in elements:
        print(f"Depth {item[0]}: {item[1]} ({item[2]}), Name={repr(item[3])}, Rect={item[4]}")
        
finally:
    comtypes.CoUninitialize()
