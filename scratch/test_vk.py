import ctypes
from ctypes import wintypes

_user32 = ctypes.windll.user32
MAPVK_VK_TO_CHAR = 2

_user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
_user32.MapVirtualKeyW.restype = wintypes.UINT

def test_vk(vk):
    char_code = _user32.MapVirtualKeyW(vk, MAPVK_VK_TO_CHAR)
    char = chr(char_code) if char_code > 0 else "N/A"
    print(f"VK: 0x{vk:02X} -> Code: {char_code} -> Char: {char!r}")

# Test some key codes
# VK_A (0x41)
test_vk(0x41)
# VK_OEM_COMMA (0xBC)
test_vk(0xBC)
# VK_OEM_PERIOD (0xBE)
test_vk(0xBE)
# VK_OEM_1 (0xBA)
test_vk(0xBA)
# VK_OEM_PLUS (0xBB)
test_vk(0xBB)
# VK_OEM_7 (0xDE)
test_vk(0xDE)
