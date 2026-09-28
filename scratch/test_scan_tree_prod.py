import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import win32gui
import time
from config import Config
from scanner import Scanner
from scanner import _scan_hwnd, _resolve_uia_duplicates

def run_test():
    config = Config()
    
    hwnds = []
    def enum_cb(h, _):
        if win32gui.IsWindowVisible(h) and not win32gui.IsIconic(h):
            title = win32gui.GetWindowText(h).strip()
            cls = win32gui.GetClassName(h)
            if title and cls not in ('Shell_TrayWnd', 'Progman', 'WorkerW'):
                hwnds.append((h, cls, title))
        return True
    win32gui.EnumWindows(enum_cb, None)
    
    print(f"Testing current scanner implementation on {len(hwnds)} visible windows...\n")
    
    import comtypes
    comtypes.CoInitialize()
    try:
        for hwnd, cls, title in hwnds[:10]:
            print(f"Window: {hwnd} | Class: {cls} | Title: '{title[:40]}'")
            try:
                t0 = time.time()
                res = _scan_hwnd(hwnd, config.scan_timeout_ms)
                res_dedup = _resolve_uia_duplicates(res)
                elapsed = (time.time() - t0) * 1000
                print(f"  Scanned: {len(res)} elements | After Dedup: {len(res_dedup)} | Time: {elapsed:.1f}ms")
                
                if "Discord" in title and res_dedup:
                    links = [el for el in res_dedup if el[1] and el[1].ControlType == 50005]
                    print(f"  Found {len(links)} Hyperlink (50005) elements:")
                    for r, c in links:
                        try:
                            print(f"    - URL/Link: '{c.Name}' | Rect: ({r.left}, {r.top}, {r.right}, {r.bottom})")
                        except:
                            pass
            except Exception as e:
                print(f"  Error: {e}")
            print("-" * 50)
    finally:
        comtypes.CoUninitialize()

if __name__ == '__main__':
    run_test()
