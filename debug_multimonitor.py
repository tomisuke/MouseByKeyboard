import os
import time
import win32gui
import win32api
import win32con
import ctypes
from ctypes import wintypes
from PIL import Image

def _get_screen_rect():
    try:
        x = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
        y = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
        w = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
        h = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        return (x, y, x + w, y + h)
    except Exception as e:
        print(f"Error getting virtual screen metrics: {e}")
        return (0, 0, 1920, 1080)

def grab_screen_gdi_test(rect=None, use_create_dc=False):
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    
    # 64-bit handle safety declarations
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    
    gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    
    gdi32.BitBlt.argtypes = [
        wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_uint32
    ]
    gdi32.BitBlt.restype = wintypes.BOOL
    
    gdi32.GetDIBits.argtypes = [
        wintypes.HDC, wintypes.HBITMAP, ctypes.c_uint, ctypes.c_uint,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint
    ]
    gdi32.GetDIBits.restype = ctypes.c_int
    
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteObject.restype = wintypes.BOOL
    
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.DeleteDC.restype = wintypes.BOOL
    
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.ReleaseDC.restype = ctypes.c_int

    # CreateDCW declaration if needed
    gdi32.CreateDCW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p]
    gdi32.CreateDCW.restype = wintypes.HDC

    if rect is None:
        left = user32.GetSystemMetrics(76) # SM_XVIRTUALSCREEN
        top = user32.GetSystemMetrics(77) # SM_YVIRTUALSCREEN
        width = user32.GetSystemMetrics(78) # SM_CXVIRTUALSCREEN
        height = user32.GetSystemMetrics(79) # SM_CYVIRTUALSCREEN
    else:
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top

    print(f"Capturing GDI: left={left}, top={top}, width={width}, height={height}")

    # Use GetDC(0) or CreateDCW("DISPLAY", ...)
    if use_create_dc:
        hdc_screen = gdi32.CreateDCW("DISPLAY", None, None, None)
        print("Using CreateDCW('DISPLAY')")
    else:
        hdc_screen = user32.GetDC(0)
        print("Using GetDC(0)")

    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    hbitmap = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
    hobj_old = gdi32.SelectObject(hdc_mem, hbitmap)
    
    # SRCCOPY = 0x00CC0020
    gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, left, top, 0x00CC0020)
    
    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ('biSize', ctypes.c_uint32),
            ('biWidth', ctypes.c_int32),
            ('biHeight', ctypes.c_int32),
            ('biPlanes', ctypes.c_uint16),
            ('biBitCount', ctypes.c_uint16),
            ('biCompression', ctypes.c_uint32),
            ('biSizeImage', ctypes.c_uint32),
            ('biXPelsPerMeter', ctypes.c_int32),
            ('biYPelsPerMeter', ctypes.c_int32),
            ('biClrUsed', ctypes.c_uint32),
            ('biClrImportant', ctypes.c_uint32),
        ]
        
    class BITMAPINFO(ctypes.Structure):
        _fields_ = [
            ('bmiHeader', BITMAPINFOHEADER),
            ('bmiColors', ctypes.c_uint32 * 3),
        ]
        
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = width
    bmi.bmiHeader.biHeight = -height
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0
    
    buffer_size = width * height * 4
    image_buffer = ctypes.create_string_buffer(buffer_size)
    
    gdi32.GetDIBits(hdc_screen, hbitmap, 0, height, image_buffer, ctypes.byref(bmi), 0)
    
    img = Image.frombuffer("RGBA", (width, height), image_buffer, "raw", "BGRA", 0, 1)
    img_rgb = img.convert("RGB")
    
    gdi32.SelectObject(hdc_mem, hobj_old)
    gdi32.DeleteObject(hbitmap)
    gdi32.DeleteDC(hdc_mem)
    if use_create_dc:
        gdi32.DeleteDC(hdc_screen)
    else:
        user32.ReleaseDC(0, hdc_screen)
    
    return img_rgb

def grab_screen_gdi_multimonitor(rect=None):
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    
    gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    
    gdi32.BitBlt.argtypes = [
        wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_uint32
    ]
    gdi32.BitBlt.restype = wintypes.BOOL
    
    gdi32.GetDIBits.argtypes = [
        wintypes.HDC, wintypes.HBITMAP, ctypes.c_uint, ctypes.c_uint,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint
    ]
    gdi32.GetDIBits.restype = ctypes.c_int
    
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteObject.restype = wintypes.BOOL
    
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.DeleteDC.restype = wintypes.BOOL
    
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.ReleaseDC.restype = ctypes.c_int

    gdi32.CreateDCW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_void_p]
    gdi32.CreateDCW.restype = wintypes.HDC

    gdi32.PatBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint32]
    gdi32.PatBlt.restype = wintypes.BOOL

    if rect is None:
        left = user32.GetSystemMetrics(76) # SM_XVIRTUALSCREEN
        top = user32.GetSystemMetrics(77) # SM_YVIRTUALSCREEN
        width = user32.GetSystemMetrics(78) # SM_CXVIRTUALSCREEN
        height = user32.GetSystemMetrics(79) # SM_CYVIRTUALSCREEN
        right = left + width
        bottom = top + height
    else:
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top

    print(f"Capturing Multi-Monitor: left={left}, top={top}, width={width}, height={height}")

    final_img = Image.new("RGB", (width, height), (0, 0, 0))
    
    import win32api
    monitors = win32api.EnumDisplayMonitors()
    for hMonitor, _, m_rect in monitors:
        ol = max(left, m_rect[0])
        ot = max(top, m_rect[1])
        or_ = min(right, m_rect[2])
        ob = min(bottom, m_rect[3])
        
        if ol < or_ and ot < ob:
            ow = or_ - ol
            oh = ob - ot
            
            info = win32api.GetMonitorInfo(hMonitor)
            device_name = info['Device']
            
            hdc_monitor = gdi32.CreateDCW(None, device_name, None, None)
            if hdc_monitor:
                hdc_mem = gdi32.CreateCompatibleDC(hdc_monitor)
                hbitmap = gdi32.CreateCompatibleBitmap(hdc_monitor, ow, oh)
                hobj_old = gdi32.SelectObject(hdc_mem, hbitmap)
                
                src_x = ol - m_rect[0]
                src_y = ot - m_rect[1]
                gdi32.BitBlt(hdc_mem, 0, 0, ow, oh, hdc_monitor, src_x, src_y, 0x00CC0020)
                
                class BITMAPINFOHEADER(ctypes.Structure):
                    _fields_ = [
                        ('biSize', ctypes.c_uint32),
                        ('biWidth', ctypes.c_int32),
                        ('biHeight', ctypes.c_int32),
                        ('biPlanes', ctypes.c_uint16),
                        ('biBitCount', ctypes.c_uint16),
                        ('biCompression', ctypes.c_uint32),
                        ('biSizeImage', ctypes.c_uint32),
                        ('biXPelsPerMeter', ctypes.c_int32),
                        ('biYPelsPerMeter', ctypes.c_int32),
                        ('biClrUsed', ctypes.c_uint32),
                        ('biClrImportant', ctypes.c_uint32),
                    ]
                    
                class BITMAPINFO(ctypes.Structure):
                    _fields_ = [
                        ('bmiHeader', BITMAPINFOHEADER),
                        ('bmiColors', ctypes.c_uint32 * 3),
                    ]
                    
                bmi = BITMAPINFO()
                bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
                bmi.bmiHeader.biWidth = ow
                bmi.bmiHeader.biHeight = -oh
                bmi.bmiHeader.biPlanes = 1
                bmi.bmiHeader.biBitCount = 32
                bmi.bmiHeader.biCompression = 0
                
                buffer_size = ow * oh * 4
                image_buffer = ctypes.create_string_buffer(buffer_size)
                
                # Deselect hbitmap from hdc_mem before calling GetDIBits
                gdi32.SelectObject(hdc_mem, hobj_old)
                
                gdi32.GetDIBits(hdc_monitor, hbitmap, 0, oh, image_buffer, ctypes.byref(bmi), 0)
                
                monitor_img = Image.frombuffer("RGBA", (ow, oh), image_buffer, "raw", "BGRA", 0, 1)
                monitor_img_rgb = monitor_img.convert("RGB")
                
                dest_x = ol - left
                dest_y = ot - top
                final_img.paste(monitor_img_rgb, (dest_x, dest_y))
                
                gdi32.DeleteObject(hbitmap)
                gdi32.DeleteDC(hdc_mem)
                gdi32.DeleteDC(hdc_monitor)
                
    return final_img

def main():
    print("--- Multi-Monitor Screen Capture Debug ---")
    screen_rect = _get_screen_rect()
    print(f"Virtual Screen Rect: {screen_rect}")
    
    monitors = win32api.EnumDisplayMonitors()
    print(f"Detected Monitors Count: {len(monitors)}")
    for idx, (hMonitor, hdcMonitor, rect) in enumerate(monitors):
        print(f"  Monitor [{idx}]: Rect={rect}")

    artifact_dir = r"C:\Users\Tomisuke\.gemini\antigravity\brain\1e4cd35e-2fe4-4e50-bc2e-dc73a7ef80f1"
    os.makedirs(artifact_dir, exist_ok=True)
    
    # 1. Test standard GetDC(0)
    try:
        t0 = time.time()
        img_getdc = grab_screen_gdi_test(screen_rect, use_create_dc=False)
        print(f"GetDC(0) Grab successful in {(time.time()-t0)*1000:.1f}ms. Size={img_getdc.size}")
        print(f"GetDC(0) Extrema: {img_getdc.getextrema()}")
        
        img_getdc.thumbnail((800, 600))
        save_path_getdc = os.path.join(artifact_dir, "test_getdc.png")
        img_getdc.save(save_path_getdc)
        print(f"Saved GetDC(0) thumbnail to: {save_path_getdc}")
    except Exception as e:
        print(f"GetDC(0) Grab failed: {e}")

    # 2. Test CreateDCW("DISPLAY")
    try:
        t0 = time.time()
        img_createdc = grab_screen_gdi_test(screen_rect, use_create_dc=True)
        print(f"CreateDCW Grab successful in {(time.time()-t0)*1000:.1f}ms. Size={img_createdc.size}")
        print(f"CreateDCW Extrema: {img_createdc.getextrema()}")
        
        img_createdc.thumbnail((800, 600))
        save_path_createdc = os.path.join(artifact_dir, "test_createdc.png")
        img_createdc.save(save_path_createdc)
        print(f"Saved CreateDCW thumbnail to: {save_path_createdc}")
    except Exception as e:
        print(f"CreateDCW Grab failed: {e}")

    # 3. Test Multi-Monitor GDI implementation
    try:
        t0 = time.time()
        img_multi = grab_screen_gdi_multimonitor(screen_rect)
        print(f"Multi-Monitor Grab successful in {(time.time()-t0)*1000:.1f}ms. Size={img_multi.size}")
        print(f"Multi-Monitor Extrema: {img_multi.getextrema()}")
        
        img_multi.thumbnail((800, 600))
        save_path_multi = os.path.join(artifact_dir, "test_multi.png")
        img_multi.save(save_path_multi)
        print(f"Saved Multi-Monitor thumbnail to: {save_path_multi}")
    except Exception as e:
        print(f"Multi-Monitor Grab failed: {e}")

if __name__ == '__main__':
    main()
