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
    print(f"Target Window: Title='{ctrl.Name}', Rect={ctrl.BoundingRectangle}")
    
    # List all immediate children (Depth 1)
    child = ctrl.GetFirstChildControl()
    idx = 0
    while child:
        r = child.BoundingRectangle
        print(f"Child [{idx}]: Type={child.ControlTypeName} ({child.ControlType}), Name='{child.Name}', Rect=({r.left}, {r.top}, {r.right}, {r.bottom}), WxH={r.width()}x{r.height()}")
        child = child.GetNextSiblingControl()
        idx += 1
finally:
    comtypes.CoUninitialize()
