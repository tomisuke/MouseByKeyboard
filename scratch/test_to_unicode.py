import ctypes
from ctypes import wintypes

_user32 = ctypes.windll.user32
_user32.ToUnicode.argtypes = [
    wintypes.UINT,
    wintypes.UINT,
    ctypes.POINTER(ctypes.c_byte * 256),
    wintypes.LPWSTR,
    ctypes.c_int,
    wintypes.UINT
]
_user32.ToUnicode.restype = ctypes.c_int

def test_to_unicode(vk, scan=0, shift=False):
    key_state = (ctypes.c_byte * 256)()
    if shift:
        key_state[0x10] = 0x80 # VK_SHIFT
        
    buf = ctypes.create_unicode_buffer(5)
    n = _user32.ToUnicode(vk, scan, ctypes.byref(key_state), buf, len(buf), 0)
    char = buf.value if n > 0 else "N/A"
    print(f"VK: 0x{vk:02X}, Shift: {shift} -> Char: {char!r} (returned {n})")

# Test 7 key (0x37) with and without Shift
test_to_unicode(0x37, shift=False)
test_to_unicode(0x37, shift=True)

# Test VK_OEM_PLUS (0xBB)
test_to_unicode(0xBB, shift=False)
test_to_unicode(0xBB, shift=True)

# Test VK_OEM_1 (0xBA)
test_to_unicode(0xBA, shift=False)
test_to_unicode(0xBA, shift=True)
