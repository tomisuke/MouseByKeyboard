import win32gui
import win32con
import traceback

def main():
    hwnds = []
    def enum_cb(hwnd, _):
        try:
            cls = win32gui.GetClassName(hwnd)
            title = win32gui.GetWindowText(hwnd)
            visible = win32gui.IsWindowVisible(hwnd)
            iconic = win32gui.IsIconic(hwnd)
            try:
                rect = win32gui.GetWindowRect(hwnd)
            except Exception:
                rect = (0,0,0,0)
            hwnds.append((hwnd, visible, iconic, rect, cls, title))
        except Exception as e:
            print(f"Error in enum_cb: {e}")
            traceback.print_exc()
        return True
        
    try:
        win32gui.EnumWindows(enum_cb, None)
    except Exception as e:
        print(f"Error in EnumWindows: {e}")
        traceback.print_exc()
        return

    print(f"{'HWND':<10} | {'Visible':<7} | {'Iconic':<7} | {'Rect':<25} | {'Class':<30} | {'Title'}")
    print("-" * 120)
    for hwnd, visible, iconic, rect, cls, title in hwnds:
        # 見やすいように、visibleなものだけ、あるいは気になるクラスのものだけ表示する
        # visible かつ iconic でないもの
        if visible and not iconic:
            print(f"{hwnd:<10} | {str(visible):<7} | {str(iconic):<7} | {str(rect):<25} | {cls:<30} | {title}")

if __name__ == "__main__":
    main()
