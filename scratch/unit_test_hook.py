# scratch/unit_test_hook.py
import sys
import os
import ctypes
from ctypes import wintypes

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from keyboard_hook import SelectiveKeyboardHook, KBDLLHOOKSTRUCT

_user32 = ctypes.windll.user32

# Test configurations
hint_chars = "fj"
prefix_keys = [";", ","]

called_keys = []
def mock_callback(name):
    called_keys.append(name)

# Create hook instance
hook = SelectiveKeyboardHook(
    callback=mock_callback,
    hint_chars=hint_chars,
    prefix_keys=prefix_keys
)

# Mock GetKeyState to simulate modifier keys
original_GetKeyState = _user32.GetKeyState
modifier_states = {
    0x10: 0, # VK_SHIFT
    0x11: 0, # VK_CONTROL
    0x12: 0, # VK_MENU (Alt)
    0x5B: 0, # VK_LWIN
    0x5C: 0, # VK_RWIN
}

def mock_GetKeyState(vk):
    return modifier_states.get(vk, original_GetKeyState(vk))

# Override GetKeyState with our mock
# ctypes.windll.user32.GetKeyState = mock_GetKeyState
# Note: Since ctypes functions are bound to dlls, patching ctypes.windll is sometimes tricky.
# Instead of patching at DLL level, we can mock _user32.GetKeyState inside the hook instance.
import keyboard_hook
keyboard_hook._user32.GetKeyState = mock_GetKeyState

# Helper to invoke the hook proc
def invoke_hook_proc(vk, is_down=True, scan=0):
    struct = KBDLLHOOKSTRUCT()
    struct.vkCode = vk
    struct.scanCode = scan
    struct.flags = 0
    struct.time = 0
    struct.dwExtraInfo = 0
    
    wParam = 0x0100 if is_down else 0x0101 # WM_KEYDOWN / WM_KEYUP
    lParam = ctypes.addressof(struct)
    
    # We pass a dummy HHOOK as 0
    # To prevent CallNextHookEx from actual DLL execution (which might crash with dummy HHOOK),
    # we can also mock CallNextHookEx.
    original_CallNextHookEx = keyboard_hook._user32.CallNextHookEx
    keyboard_hook._user32.CallNextHookEx = lambda h, code, w, l: 999 # return 999 as default pass-through indicator
    
    try:
        res = hook._hook_proc(0, wParam, lParam)
    finally:
        keyboard_hook._user32.CallNextHookEx = original_CallNextHookEx
        
    return res

# Test Suite
def run_tests():
    global called_keys
    print("Running unit tests for SelectiveKeyboardHook logic...")
    
    # Reset states
    modifier_states[0x10] = 0
    modifier_states[0x11] = 0
    modifier_states[0x12] = 0
    called_keys = []
    hook._blocked_vks.clear()
    
    # Case 1: Hint key 'f' (0x46) pressed, no modifiers
    # MapVirtualKeyW for 0x46 returns 'F' which lowers to 'f'.
    res = invoke_hook_proc(0x46, is_down=True)
    assert res == 1, f"Expected suppress (1), got {res}"
    assert called_keys == ["f"], f"Expected callback with 'f', got {called_keys}"
    assert 0x46 in hook._blocked_vks, "Expected 0x46 to be added to blocked list"
    print("Pass: Case 1 (Hint key block)")
    
    # Case 2: Hint key 'f' (0x46) released
    res = invoke_hook_proc(0x46, is_down=False)
    assert res == 1, f"Expected suppress (1) for release of blocked key, got {res}"
    assert 0x46 not in hook._blocked_vks, "Expected 0x46 to be removed from blocked list"
    print("Pass: Case 2 (Hint key release block)")
    
    # Case 3: Non-hint key 'a' (0x41) pressed
    called_keys = []
    res = invoke_hook_proc(0x41, is_down=True)
    assert res == 999, f"Expected pass-through (999), got {res}"
    assert called_keys == [], f"Expected no callback, got {called_keys}"
    assert 0x41 not in hook._blocked_vks, "Expected 0x41 not to be blocked"
    print("Pass: Case 3 (Non-hint key pass-through)")
    
    # Case 4: Non-hint key 'a' (0x41) released
    res = invoke_hook_proc(0x41, is_down=False)
    assert res == 999, f"Expected pass-through (999), got {res}"
    print("Pass: Case 4 (Non-hint key release pass-through)")
    
    # Case 5: Hint key 'f' (0x46) pressed WITH Control modifier (Ctrl+F)
    called_keys = []
    modifier_states[0x11] = 0x8000 # Simulating VK_CONTROL down
    res = invoke_hook_proc(0x46, is_down=True)
    assert res == 999, f"Expected pass-through (999) when Ctrl is pressed, got {res}"
    assert called_keys == [], f"Expected no callback under modifiers, got {called_keys}"
    print("Pass: Case 5 (Hint key with Ctrl pass-through)")
    
    # Case 6: JIS semicolon key (VK_OEM_PLUS = 0xBB) which maps to ';'
    modifier_states[0x11] = 0 # reset Ctrl
    called_keys = []
    res = invoke_hook_proc(0xBB, is_down=True)
    # Depending on active keyboard layout, MapVirtualKeyW(0xBB, 2) returns ';'
    # In user's system it returned 59 (';'). Let's see if the test runs successfully.
    # Note: On different systems, MapVirtualKeyW(0xBB, 2) might return different char.
    # So we print the result for verification, but if it is ';', it should suppress.
    char_mapped = chr(_user32.MapVirtualKeyW(0xBB, 2)).lower()
    if char_mapped == ';':
        assert res == 1, f"Expected suppress (1) for semicolon, got {res}"
        assert called_keys == [";"], f"Expected callback ';', got {called_keys}"
        print("Pass: Case 6 (Prefix key ';' block)")
    else:
        print(f"Skipping Case 6 assertion because VK_OEM_PLUS mapped to {char_mapped!r} instead of ';'")
        
    print("\nAll unit tests passed successfully!")

if __name__ == "__main__":
    run_tests()
