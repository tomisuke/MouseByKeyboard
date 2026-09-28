import io
import asyncio
from PIL import Image, ImageGrab

import ctypes

def grab_screen_ctypes(rect=None):
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    from ctypes import wintypes
    
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
    
    if rect is None:
        left = user32.GetSystemMetrics(76) # SM_XVIRTUALSCREEN
        top = user32.GetSystemMetrics(77) # SM_YVIRTUALSCREEN
        width = user32.GetSystemMetrics(78) # SM_CXVIRTUALSCREEN
        height = user32.GetSystemMetrics(79) # SM_CYVIRTUALSCREEN
    else:
        left, top, right, bottom = rect
        width = right - left
        height = bottom - top

    hdc_screen = user32.GetDC(0)
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
    bmi.bmiHeader.biHeight = -height  # top-down
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
    user32.ReleaseDC(0, hdc_screen)
    
    return img_rgb

async def test_ocr():
    print("Taking screenshot...")
    try:
        screen = grab_screen_ctypes()
    except Exception as e:
        print(f"grab_screen_ctypes failed: {e}")
        print("Falling back to ImageGrab.grab()...")
        screen = ImageGrab.grab()
    width, height = screen.size
    print(f"Screen size: {width}x{height}")
    
    bytes_io = io.BytesIO()
    screen.save(bytes_io, format='PNG')
    bytes_data = bytes_io.getvalue()
    
    print("Initializing winrt.windows.media.ocr...")
    try:
        import winrt.windows.media.ocr as ocr
        import winrt.windows.graphics.imaging as imaging
        import winrt.windows.storage.streams as streams
    except ImportError as e:
        print(f"Failed to import winsdk: {e}")
        return
        
    print("Writing bytes to WinRT stream...")
    writer = streams.DataWriter()
    writer.write_bytes(bytes_data)
    buffer = writer.detach_buffer()
    
    stream = streams.InMemoryRandomAccessStream()
    await stream.write_async(buffer)
    stream.seek(0)
    
    print("Decoding bitmap...")
    decoder = await imaging.BitmapDecoder.create_async(stream)
    software_bitmap = await decoder.get_software_bitmap_async()
    
    print("Creating OCR engine...")
    engine = ocr.OcrEngine.try_create_from_user_profile_languages()
    if not engine:
        print("Failed to create OcrEngine.")
        return
        
    print(f"OcrEngine Language: {engine.recognizer_language.language_tag}")
    
    print("Recognizing text...")
    result = await engine.recognize_async(software_bitmap)
    
    print("\n--- OCR Results ---")
    print(f"Lines detected: {len(result.lines)}")
    
    found_any = False
    for i, line in enumerate(result.lines):
        print(f"Line {i}: '{line.text}'")
        for word in line.words:
            r = word.bounding_rect
            print(f"  Word: '{word.text}' at x={r.x:.1f}, y={r.y:.1f}, w={r.width:.1f}, h={r.height:.1f}")
            found_any = True
            
    if not found_any:
        print("No text detected.")

if __name__ == '__main__':
    asyncio.run(test_ocr())
