import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import win32gui
import comtypes
import uiautomation as auto

def dump_tree():
    # Find Discord window
    discord_hwnd = 0
    def enum_cb(hwnd, _):
        nonlocal discord_hwnd
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            cls = win32gui.GetClassName(hwnd)
            if "Discord" in title and cls == "Chrome_WidgetWin_1":
                discord_hwnd = hwnd
                return False
        return True
    win32gui.EnumWindows(enum_cb, None)
    
    if not discord_hwnd:
        print("Discord window not found.")
        return
        
    print(f"Found Discord HWND: {discord_hwnd}")
    
    comtypes.CoInitialize()
    try:
        ctrl = auto.ControlFromHandle(discord_hwnd)
        if not ctrl:
            print("Failed to get ControlFromHandle.")
            return
            
        with open("scratch/discord_tree.txt", "w", encoding="utf-8") as f:
            f.write(f"Discord HWND: {discord_hwnd}\n")
            
            def walk(c, depth=0):
                if depth > 25:
                    return
                try:
                    name = c.Name
                    ctype = c.ControlType
                    r = c.BoundingRectangle
                    cls = c.ClassName
                    
                    # インデント
                    indent = "  " * depth
                    line = f"{indent}Type: {ctype} | Class: {cls} | Name: '{name}' | Rect: ({r.left}, {r.top}, {r.right}, {r.bottom})\n"
                    f.write(line)
                    
                    # 子要素の探索
                    # 速度向上のため、特定の巨大なコンテナの子要素で不要そうなものは省略しても良いが、
                    # まずはすべてダンプしてみる（ただし最大深度を設定）
                    child = c.GetFirstChildControl()
                    while child:
                        walk(child, depth + 1)
                        child = child.GetNextSiblingControl()
                except Exception as e:
                    pass
            
            print("Dumping tree... (this may take a while)")
            walk(ctrl)
            print("Dump completed. Output written to scratch/discord_tree.txt")
            
    finally:
        comtypes.CoUninitialize()

if __name__ == '__main__':
    dump_tree()
