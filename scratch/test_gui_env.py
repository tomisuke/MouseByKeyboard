import win32gui

desktop = win32gui.GetDesktopWindow()
fg = win32gui.GetForegroundWindow()

print(f"Desktop HWND: {desktop}")
print(f"Foreground HWND: {fg}")

# Try to list all children of the desktop window
children = []
def enum_child_cb(hwnd, _):
    children.append(hwnd)
    return True

try:
    win32gui.EnumChildWindows(desktop, enum_child_cb, None)
    print(f"Found {len(children)} child windows of Desktop.")
    for h in children[:10]:
        cls = win32gui.GetClassName(h)
        title = win32gui.GetWindowText(h)
        print(f"  HWND: {h} | Class: {cls} | Title: {title}")
except Exception as e:
    print(f"EnumChildWindows failed: {e}")
