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
    
    elements = []
    def dump_children(c, depth=0):
        if depth > 10:
            return
        
        # Access properties individually to find what throws exception
        try:
            r = c.BoundingRectangle
            l, t, right, b = r.left, r.top, r.right, r.bottom
        except Exception as e:
            print(f"Error getting BoundingRectangle at depth {depth}: {e}")
            return
            
        try:
            c_type_name = c.ControlTypeName
        except Exception as e:
            c_type_name = "Unknown"
            print(f"Error getting ControlTypeName: {e}")
            
        try:
            c_type = c.ControlType
        except Exception as e:
            c_type = 0
            print(f"Error getting ControlType: {e}")
            
        try:
            name = c.Name
        except Exception as e:
            name = "ErrorName"
            print(f"Error getting Name: {e}")
            
        try:
            clickable = c.IsClickable
        except Exception as e:
            clickable = "ErrorClickable"
            
        elements.append((depth, c_type_name, c_type, name, (l, t, right, b), clickable))
        
        # Traverse children
        try:
            child = c.GetFirstChildControl()
            while child:
                dump_children(child, depth + 1)
                child = child.GetNextSiblingControl()
        except Exception as e:
            print(f"Error traversing children at depth {depth}: {e}")
            
    dump_children(sidebar_container)
    
    print(f"\nDumped {len(elements)} elements inside sidebar container:")
    for item in elements:
        print(f"Depth {item[0]}: {item[1]} ({item[2]}), Name='{item[3]}', Rect={item[4]}, Clickable={item[5]}")
        
finally:
    comtypes.CoUninitialize()
