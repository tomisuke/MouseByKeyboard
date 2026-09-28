import win32gui
import win32con
import tkinter as tk
import sys
import os

# Add parent directory to path so we can import scanner
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scanner import _is_invalid_active_window, _get_fallback_active_window

def test_validation():
    print("Testing _is_invalid_active_window...")
    # NULL HWND
    assert _is_invalid_active_window(0) == True
    print("Null HWND test passed.")

    # Create tkinter window for testing
    root = tk.Tk()
    root.title("Test Valid Window")
    root.geometry("200x200")
    root.update() # Update to ensure window is created and visible
    
    hwnd = win32gui.FindWindow(None, "Test Valid Window")
    assert hwnd != 0, "Failed to find test window"
    
    # 正常なウィンドウは無効判定されないはず
    is_invalid = _is_invalid_active_window(hwnd)
    print(f"Test Window HWND: {hwnd}, IsInvalid: {is_invalid}")
    assert is_invalid == False, "Valid window was classified as invalid"
    
    # ウィンドウのタイトルを消す
    root.title("")
    root.update()
    is_invalid = _is_invalid_active_window(hwnd)
    print(f"Test Window with empty title, IsInvalid: {is_invalid}")
    assert is_invalid == True, "Window without title was not classified as invalid"
    
    # タイトルを戻して、サイズを小さくする
    root.title("Test Valid Window")
    root.geometry("50x50")
    root.update()
    is_invalid = _is_invalid_active_window(hwnd)
    print(f"Test Window with small size, IsInvalid: {is_invalid}")
    assert is_invalid == True, "Small window was not classified as invalid"
    
    # 最小化する
    root.geometry("200x200")
    root.iconify()
    root.update()
    is_invalid = _is_invalid_active_window(hwnd)
    print(f"Iconified Test Window, IsInvalid: {is_invalid}")
    assert is_invalid == True, "Iconified window was not classified as invalid"
    
    # 元に戻して visible に
    root.deiconify()
    root.update()
    
    # フォールバックのテスト
    fallback_hwnd = _get_fallback_active_window()
    print(f"Fallback Active Window HWND: {fallback_hwnd}")
    if fallback_hwnd != 0:
        cls = win32gui.GetClassName(fallback_hwnd)
        title = win32gui.GetWindowText(fallback_hwnd)
        print(f"Fallback Class: {cls}, Title: {title}")
        assert _is_invalid_active_window(fallback_hwnd) == False
    
    root.destroy()
    print("All tests passed successfully!")

if __name__ == "__main__":
    test_validation()
