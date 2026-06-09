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
    print(f"Target Window: '{ctrl.Name}'")
    
    keywords = ['calendar', 'today', 'inbox', 'notification', 'statistic', 'search', 'star', 'task', 'profile', 'avatar', 'setting', 'custom', 'filter']
    
    found = []
    
    def search_tree(c, depth=0):
        if depth > 30:
            return
        try:
            name = c.Name.lower()
            c_type_name = c.ControlTypeName
            r = c.BoundingRectangle
            
            matches = [kw for kw in keywords if kw in name]
            if matches:
                invokable = False
                try:
                    invokable = c.GetInvokePattern() is not None
                except:
                    pass
                found.append({
                    'depth': depth,
                    'keyword': matches[0],
                    'type_name': c_type_name,
                    'name': c.Name, # Keep original case
                    'rect': (r.left, r.top, r.right, r.bottom),
                    'invokable': invokable
                })
        except Exception:
            pass
            
        try:
            child = c.GetFirstChildControl()
            while child:
                search_tree(child, depth + 1)
                child = child.GetNextSiblingControl()
        except Exception:
            pass
            
    search_tree(ctrl)
    
    print(f"\nFound {len(found)} English keyword matches:")
    for item in found:
        # Use repr() to prevent console encoding crash on non-ASCII names
        print(f"Depth {item['depth']}: Keyword={item['keyword']} -> Type={item['type_name']}, Name={repr(item['name'])}, Rect={item['rect']}, Invokable={item['invokable']}")
        
finally:
    comtypes.CoUninitialize()
