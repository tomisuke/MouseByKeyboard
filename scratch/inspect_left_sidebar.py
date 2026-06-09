import sys
import os
import time
import win32gui
import comtypes
import uiautomation as auto

# Find TickTick or active window
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
    # Fallback to waiting 3 seconds to let user focus the target window
    print("No TickTick window found. Waiting 3 seconds to capture active window...")
    time.sleep(3)
    hwnd = win32gui.GetForegroundWindow()

print(f"Target HWND: {hwnd}, Class: {win32gui.GetClassName(hwnd)}, Title: {win32gui.GetWindowText(hwnd)}")

comtypes.CoInitialize()
try:
    ctrl = auto.ControlFromHandle(hwnd)
    win_rect = win32gui.GetWindowRect(hwnd)
    print(f"Window Rect: {win_rect}")
    
    # We want to traverse the entire UIA tree and print elements located on the left side of the window (x offset < 100)
    # Let's write a recursive dumper that gathers elements with coordinates.
    dumped = []
    
    def dump_tree(c, depth=0):
        if depth > 20:
            return
        try:
            r = c.BoundingRectangle
            name = c.Name
            c_type = c.ControlType
            # We want to see if it is clickable according to UIA
            # Check patterns
            invokable = False
            clickable = False
            try:
                # IsInvokePatternAvailable
                # We can check if it supports InvokePattern
                invokable = c.GetInvokePattern() is not None
            except Exception:
                pass
                
            try:
                clickable = c.IsClickable
            except Exception:
                pass
                
            # Keep track of everything on the left side
            # TickTick's left window edge is win_rect[0]
            if r.left < win_rect[0] + 150 and r.width() > 0 and r.height() > 0:
                dumped.append({
                    'depth': depth,
                    'type': c_type,
                    'type_name': c.ControlTypeName,
                    'name': name,
                    'rect': (r.left, r.top, r.right, r.bottom),
                    'invokable': invokable,
                    'clickable': clickable
                })
                
            child = c.GetFirstChildControl()
            while child:
                dump_tree(child, depth + 1)
                child = child.GetNextSiblingControl()
        except Exception as e:
            pass
            
    dump_tree(ctrl)
    
    print(f"\nDumped {len(dumped)} elements on the left side (X < window_left + 150):")
    # Sort by Y position, then X position
    dumped.sort(key=lambda x: (x['rect'][1], x['rect'][0]))
    for item in dumped:
        print(f"Depth {item['depth']}: Type={item['type']} ({item['type_name']}), Name='{item['name']}', Rect={item['rect']}, Invokable={item['invokable']}, Clickable={item['clickable']}")
        
finally:
    comtypes.CoUninitialize()
