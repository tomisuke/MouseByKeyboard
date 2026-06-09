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
    
    keywords = ['カレンダー', 'タスク', '検索', '統計', '通知', '概要', '全て', '今日', 'カレンダ']
    
    found = []
    
    def search_tree(c, depth=0):
        if depth > 30:
            return
        try:
            name = c.Name
            c_type_name = c.ControlTypeName
            r = c.BoundingRectangle
            
            # Check if any keyword matches
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
                    'name': name,
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
    
    print(f"\nFound {len(found)} keyword matches:")
    for item in found:
        print(f"Depth {item['depth']}: Keyword={item['keyword']} -> Type={item['type_name']}, Name='{item['name']}', Rect={item['rect']}, Invokable={item['invokable']}")
        
finally:
    comtypes.CoUninitialize()
