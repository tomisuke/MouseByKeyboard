import time
import win32gui
import win32process
import uiautomation as auto
import comtypes
from PIL import ImageGrab
from config import Config
from scanner import Scanner, _scan_ocr, _scan_cv, _is_invalid_active_window, _grab_screen_gdi

def main():
    print("5秒後にスキャンを開始します。対象のウィンドウ（Claudeなど）をアクティブにしてください...")
    for i in range(5, 0, -1):
        print(f"{i}...")
        time.sleep(1)
        
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd or _is_invalid_active_window(hwnd):
        from scanner import _get_fallback_active_window
        hwnd = _get_fallback_active_window()
        if not hwnd:
            hwnd = win32gui.GetDesktopWindow()
            
    title = win32gui.GetWindowText(hwnd)
    cls = win32gui.GetClassName(hwnd)
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    print(f"\n--- 対象ウィンドウ情報 ---")
    print(f"HWND: {hwnd}")
    print(f"Title: {title}")
    print(f"Class: {cls}")
    print(f"PID: {pid}")
    print(f"Is invalid active window?: {_is_invalid_active_window(hwnd)}")
    
    # 1. UIAスキャンテスト
    print("\n--- 1. UIAスキャンのテスト ---")
    comtypes.CoInitialize()
    t0 = time.time()
    try:
        ctrl = auto.ControlFromHandle(hwnd)
        print(f"ControlFromHandle 取得時間: {(time.time()-t0)*1000:.1f}ms")
        if ctrl:
            print(f"ControlType: {ctrl.ControlType} (Name: {ctrl.Name})")
            
            # 子要素数の確認
            t_child = time.time()
            children = ctrl.GetChildren()
            print(f"GetChildren 取得時間: {(time.time()-t_child)*1000:.1f}ms, 子要素数: {len(children)}")
            
            # _scan_hwnd のシミュレーション
            print("ツリー探索を開始します...")
            from scanner import _scan_hwnd
            # screen_rect の取得
            try:
                import win32api, win32con
                x = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
                y = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
                w = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
                h = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
                screen_rect = (x, y, x + w, y + h)
            except:
                screen_rect = (0, 0, 1920, 1080)
            
            t_scan = time.time()
            uia_elements = _scan_hwnd(hwnd, 2000, screen_rect)
            print(f"UIAツリー探索完了: {(time.time()-t_scan)*1000:.1f}ms, 検出要素数: {len(uia_elements)}")
            for idx, (r, item) in enumerate(uia_elements[:10]):
                name = item.Name if hasattr(item, 'Name') else 'N/A'
                print(f"  [{idx}] Rect: ({r.left}, {r.top}, {r.right}, {r.bottom}), Type: {item.ControlType}, Name: {name}")
        else:
            print("ControlFromHandle が None を返しました。")
    except Exception as e:
        print(f"UIAスキャン中に例外が発生しました: {e}")
    finally:
        comtypes.CoUninitialize()

    # 2. 画像スキャンテスト
    print("\n--- 2. 画像スキャンのテスト ---")
    try:
        t_grab = time.time()
        # ウィンドウの矩形を取得
        wl, wt, wr, wb = win32gui.GetWindowRect(hwnd)
        win_rect = (wl, wt, wr, wb)
        print(f"GetWindowRect: {win_rect}")
        
        # 画面全体のキャプチャ
        screen_rect = (0, 0, win32api.GetSystemMetrics(win32con.SM_CXSCREEN), win32api.GetSystemMetrics(win32con.SM_CYSCREEN))
        try:
            screen_img = _grab_screen_gdi(screen_rect)
            print(f"_grab_screen_gdi 完了: {(time.time()-t_grab)*1000:.1f}ms, サイズ: {screen_img.size}")
        except Exception as e:
            print(f"_grab_screen_gdi 失敗: {e}. ImageGrab にフォールバックします...")
            screen_img = ImageGrab.grab(bbox=screen_rect)
            print(f"ImageGrab.grab 完了: {(time.time()-t_grab)*1000:.1f}ms, サイズ: {screen_img.size}")
        
        # OCR
        print("OCRスキャンを開始します...")
        t_ocr = time.time()
        ocr_elements = _scan_ocr(screen_img, screen_rect)
        print(f"OCRスキャン完了: {(time.time()-t_ocr)*1000:.1f}ms, 要素数: {len(ocr_elements)}")
        
        # CV
        print("CVスキャンを開始します...")
        t_cv = time.time()
        cv_elements = _scan_cv(screen_img, screen_rect)
        print(f"CVスキャン完了: {(time.time()-t_cv)*1000:.1f}ms, 要素数: {len(cv_elements)}")
        
    except Exception as e:
        print(f"画像スキャン中に例外が発生しました: {e}")

if __name__ == '__main__':
    main()
