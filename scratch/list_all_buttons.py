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
    print(f"Target Window: Rect={win_rect}")
    
    buttons = []
    
    def find_buttons(c, depth=0):
        if depth > 25:
            return
        try:
            c_type = c.ControlType
            # We look for Buttons (50000) or ImageControls (50006)
            if c_type in (50000, 50006):
                r = c.BoundingRectangle
                buttons.append({
                    'depth': depth,
                    'type': c.ControlTypeName,
                    'name': c.Name,
                    'rect': (r.left, r.top, r.right, r.bottom),
                    'width': r.width(),
                    'height': r.height()
                })
        except Exception:
            pass
            
        try:
            child = c.GetFirstChildControl()
            while child:
                find_buttons(child, depth + 1)
                child = child.GetNextSiblingControl()
        except Exception:
            pass
            
    find_buttons(ctrl)
    
    print(f"\nFound {len(buttons)} button/image elements in total:")
    # Filter buttons that are near the left edge of the window (X < window_left + 100)
    buttons_left = [b for b in buttons if b['rect'][0] < win_rect[0] + 100]
    print(f"Found {len(buttons_left)} of them on the left side (X < window_left + 100):")
    # Sort by Y position
    buttons_left.sort(key=lambda x: x['rect'][1])
    for idx, b in enumerate(buttons_left):
        print(f"[{idx}] Depth {b['depth']}: {b['type']}, Name={repr(b['name'])}, Rect={b['rect']} (WxH={b['width']}x{b['height']})")
        
finally:
    comtypes.CoUninitialize()
