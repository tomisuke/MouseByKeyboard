import sys
import os
import time
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

print(f"Target HWND: {hwnd}, Class: {win32gui.GetClassName(hwnd)}, Title: {win32gui.GetWindowText(hwnd)}")

comtypes.CoInitialize()
try:
    ctrl = auto.ControlFromHandle(hwnd)
    win_rect = win32gui.GetWindowRect(hwnd)
    print(f"Window Rect: {win_rect}")
    
    dumped = []
    
    def dump_tree(c, depth=0):
        if depth > 25:
            return
        try:
            r = c.BoundingRectangle
            name = c.Name
            c_type = c.ControlType
            
            # Print specifically elements in the left sidebar area:
            # X between window_left - 10 and window_left + 60
            # Y between window_top and window_bottom
            if win_rect[0] - 10 <= r.left < win_rect[0] + 60 and r.width() > 0 and r.height() > 0:
                dumped.append({
                    'depth': depth,
                    'type': c_type,
                    'type_name': c.ControlTypeName,
                    'name': name,
                    'rect': (r.left, r.top, r.right, r.bottom),
                    'is_clickable': c.IsClickable,
                    'invokable': c.GetInvokePattern() is not None if hasattr(c, 'GetInvokePattern') else False
                })
                
            child = c.GetFirstChildControl()
            while child:
                dump_tree(child, depth + 1)
                child = child.GetNextSiblingControl()
        except Exception:
            pass
            
    dump_tree(ctrl)
    
    print(f"\nDumped {len(dumped)} elements in left sidebar zone:")
    for item in dumped:
        print(f"Depth {item['depth']}: Type={item['type']} ({item['type_name']}), Name='{item['name']}', Rect={item['rect']}, Clickable={item['is_clickable']}, Invokable={item['invokable']}")
        
finally:
    comtypes.CoUninitialize()
