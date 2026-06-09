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
    print(f"Target Window: Title='{ctrl.Name}', Rect={win_rect}")
    
    matched = []
    
    def dump_tree(c, depth=0):
        if depth > 30:
            return
        try:
            r = c.BoundingRectangle
            
            # Filter elements in the middle vertical zone of the left sidebar:
            # X between window_left - 10 and window_left + 50 (sidebar area)
            # Y between window_top + 60 and window_bottom - 100 (excluding top menu/bottom settings)
            if (win_rect[0] - 10 <= r.left < win_rect[0] + 50 and 
                win_rect[1] + 60 <= r.top < win_rect[3] - 100 and
                r.width() > 0 and r.height() > 0):
                
                # Check patterns
                invokable = False
                try:
                    invokable = c.GetInvokePattern() is not None
                except:
                    pass
                
                matched.append({
                    'depth': depth,
                    'type_name': c.ControlTypeName,
                    'type_id': c.ControlType,
                    'name': c.Name,
                    'rect': (r.left, r.top, r.right, r.bottom),
                    'invokable': invokable
                })
                
            child = c.GetFirstChildControl()
            while child:
                dump_tree(child, depth + 1)
                child = child.GetNextSiblingControl()
        except Exception:
            pass
            
    dump_tree(ctrl)
    
    print(f"\nFound {len(matched)} elements in middle sidebar zone:")
    matched.sort(key=lambda x: x['rect'][1])
    for item in matched:
        print(f"Depth {item['depth']}: {item['type_name']} ({item['type_id']}), Name='{item['name']}', Rect={item['rect']}, Invokable={item['invokable']}")
        
finally:
    comtypes.CoUninitialize()
