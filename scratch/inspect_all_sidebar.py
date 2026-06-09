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
    
    all_elements = []
    
    def dump_tree(c, depth=0):
        if depth > 25:
            return
        try:
            r = c.BoundingRectangle
            all_elements.append((depth, c.ControlType, c.ControlTypeName, c.Name, (r.left, r.top, r.right, r.bottom)))
            
            child = c.GetFirstChildControl()
            while child:
                dump_tree(child, depth + 1)
                child = child.GetNextSiblingControl()
        except Exception as e:
            pass
            
    dump_tree(ctrl)
    
    print(f"\nTotal elements found in UIA tree: {len(all_elements)}")
    print("First 20 elements:")
    for idx, item in enumerate(all_elements[:20]):
        print(f"[{idx}] Depth {item[0]}: {item[2]} ({item[1]}), Name='{item[3]}', Rect={item[4]}")
        
finally:
    comtypes.CoUninitialize()
