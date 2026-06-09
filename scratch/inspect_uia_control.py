import uiautomation as auto
import win32gui
import comtypes

hwnd = win32gui.GetForegroundWindow()
comtypes.CoInitialize()
try:
    ctrl = auto.ControlFromHandle(hwnd)
    print("Control attributes:")
    for attr in dir(ctrl):
        if 'child' in attr.lower() or 'sibling' in attr.lower() or 'next' in attr.lower() or 'walk' in attr.lower() or 'find' in attr.lower():
            print("  ", attr)
finally:
    comtypes.CoUninitialize()
