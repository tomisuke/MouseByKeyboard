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
    print(f"Target Window: Title='{ctrl.Name}', WindowRect={win_rect}")
    
    all_elements = []
    
    def find_all(c, depth=0):
        if depth > 25:
            return
        try:
            r = c.BoundingRectangle
            # Store info
            all_elements.append({
                'depth': depth,
                'type': c.ControlTypeName,
                'name': c.Name,
                'rect': (r.left, r.top, r.right, r.bottom),
                'width': r.width(),
                'height': r.height()
            })
        except:
            pass
            
        try:
            child = c.GetFirstChildControl()
            while child:
                find_all(child, depth + 1)
                child = child.GetNextSiblingControl()
        except:
            pass
            
    find_all(ctrl)
    
    print(f"Total elements: {len(all_elements)}")
    
    # Let's filter elements that have positive width and height
    valid_elements = [e for e in all_elements if e['width'] > 0 and e['height'] > 0]
    print(f"Elements with valid size (WxH > 0): {len(valid_elements)}")
    
    # Print the 20 elements that have the smallest left coordinate (X)
    print("\nTop 30 elements with the smallest X (left) coordinates:")
    valid_elements.sort(key=lambda x: x['rect'][0])
    for idx, e in enumerate(valid_elements[:30]):
        print(f"[{idx}] Left={e['rect'][0]}: Type={e['type']}, Name={repr(e['name'])}, Rect={e['rect']} (WxH={e['width']}x{e['height']})")
        
finally:
    comtypes.CoUninitialize()
