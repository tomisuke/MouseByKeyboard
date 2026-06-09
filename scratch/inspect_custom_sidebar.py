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
    win_rect = win32gui.GetWindowRect(hwnd)
    
    # We use a list container to bypass nonlocal scoping issue
    found_target = []
    
    def find_target(c, depth=0):
        if depth > 25 or len(found_target) > 0:
            return
        try:
            r = c.BoundingRectangle
            # Left should be near 49, top near 197
            # We also check window relative coordinates to be robust
            rel_left = r.left - win_rect[0]
            rel_top = r.top - win_rect[1]
            if c.ControlType == 50025 and 45 <= rel_left <= 65 and 190 <= rel_top <= 220:
                found_target.append(c)
                return
        except:
            pass
            
        try:
            child = c.GetFirstChildControl()
            while child:
                find_target(child, depth + 1)
                child = child.GetNextSiblingControl()
        except:
            pass
            
    find_target(ctrl)
    
    if not found_target:
        print("Target CustomControl not found. Listing all depth-2 immediate candidates under TickTick:")
        # Fallback to search list of immediate descendants
        child = ctrl.GetFirstChildControl()
        while child:
            r = child.BoundingRectangle
            print(f"Depth 1: Type={child.ControlTypeName}, Rect=({r.left}, {r.top}), WxH={r.width()}x{r.height()}")
            # search grandchild
            gchild = child.GetFirstChildControl()
            while gchild:
                gr = gchild.BoundingRectangle
                print(f"  Depth 2: Type={gchild.ControlTypeName}, Rect=({gr.left}, {gr.top}), WxH={gr.width()}x{gr.height()}")
                gchild = gchild.GetNextSiblingControl()
            child = child.GetNextSiblingControl()
        sys.exit(0)
        
    target = found_target[0]
    print(f"Found Target: Type={target.ControlTypeName}, Rect={target.BoundingRectangle}")
    
    # Dump the tree under this target CustomControl
    elements = []
    def dump_tree(c, depth=0):
        if depth > 10:
            return
        try:
            r = c.BoundingRectangle
            elements.append((depth, c.ControlTypeName, c.ControlType, c.Name, (r.left, r.top, r.right, r.bottom)))
            
            child = c.GetFirstChildControl()
            while child:
                dump_tree(child, depth + 1)
                child = child.GetNextSiblingControl()
        except Exception:
            pass
            
    dump_tree(target)
    
    print(f"\nDumped {len(elements)} elements under target:")
    for item in elements:
        print(f"Depth {item[0]}: {item[1]} ({item[2]}), Name={repr(item[3])}, Rect={item[4]}")
        
finally:
    comtypes.CoUninitialize()
