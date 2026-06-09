# keyboard_hook.py
from __future__ import annotations
import ctypes
from ctypes import wintypes
from typing import Callable, Optional

# Win32 API Definitions
LRESULT = ctypes.c_longlong
HHOOK = wintypes.HANDLE
HINSTANCE = wintypes.HINSTANCE
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_KEYUP = 0x0101
WM_SYSKEYUP = 0x0105

VK_ESCAPE = 0x1B
VK_BACK = 0x08
VK_TAB = 0x09
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt
VK_LWIN = 0x5B
VK_RWIN = 0x5C

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

_user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, HINSTANCE, wintypes.DWORD]
_user32.SetWindowsHookExW.restype = HHOOK

_kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
_kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE

_user32.UnhookWindowsHookEx.argtypes = [HHOOK]
_user32.UnhookWindowsHookEx.restype = wintypes.BOOL

_user32.CallNextHookEx.argtypes = [HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
_user32.CallNextHookEx.restype = LRESULT

_user32.ToUnicode.argtypes = [
    wintypes.UINT,
    wintypes.UINT,
    ctypes.POINTER(ctypes.c_ubyte * 256),
    wintypes.LPWSTR,
    ctypes.c_int,
    wintypes.UINT
]
_user32.ToUnicode.restype = ctypes.c_int

_user32.GetKeyState.argtypes = [ctypes.c_int]
_user32.GetKeyState.restype = ctypes.c_short


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulong),
    ]


class SelectiveKeyboardHook:
    """
    Windowsの低レベルキーボードフック (WH_KEYBOARD_LL) を使用し、
    KeyNavigatorで処理したい特定のキー (ヒント文字、Esc、Backspace、プレフィックスキー) のみを
    選択的にブロック (suppress) するクラス。
    これ以外のキー (修飾キーを伴うショートカットや矢印キーなど) はパススルーするため、
    AutoHotkey (AHK) などの外部スクリプトの動作を阻害しない。
    """

    def __init__(self, callback: Callable[[str], None], hint_chars: str, prefix_keys: list[str]) -> None:
        self._callback = callback
        self._hint_chars = set(hint_chars.lower())
        self._prefix_keys = set(prefix_keys)
        self._h_hook: Optional[HHOOK] = None
        self._hook_proc_ref: Optional[HOOKPROC] = None
        self._blocked_vks: set[int] = set()

    def install(self) -> bool:
        if self._h_hook is not None:
            return True

        # 元のPython関数への参照をインスタンス変数として保持し、GCを防ぐ
        self._raw_hook_proc = lambda nCode, wParam, lParam: self._hook_proc(nCode, wParam, lParam)
        self._hook_proc_ref = HOOKPROC(self._raw_hook_proc)
        
        # WH_KEYBOARD_LL フックを設置
        # スレッドIDに 0 を指定するとグローバルフックになる (WH_KEYBOARD_LLは0である必要がある)
        h_inst = _kernel32.GetModuleHandleW(None)
        self._h_hook = _user32.SetWindowsHookExW(
            WH_KEYBOARD_LL,
            self._hook_proc_ref,
            h_inst,
            0
        )
        
        try:
            with open("hook_debug.log", "a", encoding="utf-8") as f:
                f.write(f"install: h_inst={h_inst}, h_hook={self._h_hook}\n")
        except Exception:
            pass
        
        if not self._h_hook:
            err = ctypes.get_last_error()
            print(f"[KeyboardHook] Hook installation failed, error={err}")
            try:
                with open("hook_debug.log", "a", encoding="utf-8") as f:
                    f.write(f"Hook installation failed, error={err}\n")
            except Exception:
                pass
            self._hook_proc_ref = None
            self._raw_hook_proc = None
            return False
            
        print("[KeyboardHook] Hook installed successfully")
        return True

    def uninstall(self) -> None:
        if self._h_hook is not None:
            _user32.UnhookWindowsHookEx(self._h_hook)
            self._h_hook = None
            self._hook_proc_ref = None
            self._raw_hook_proc = None
            self._blocked_vks.clear()
            print("[KeyboardHook] Hook uninstalled")

    def __del__(self) -> None:
        self.uninstall()

    def _vk_to_char(self, vk: int, scan: int) -> str:
        # Shiftキーの状態を取得して反映
        shift_pressed = (_user32.GetKeyState(VK_SHIFT) & 0x8000) != 0
        
        key_state = (ctypes.c_ubyte * 256)()
        if shift_pressed:
            key_state[VK_SHIFT] = 0x80
            
        buf = ctypes.create_unicode_buffer(5)
        n = _user32.ToUnicode(vk, scan, ctypes.byref(key_state), buf, len(buf), 0)
        if n > 0:
            return buf.value
        return ""

    def _hook_proc(self, nCode: int, wParam: int, lParam: int) -> int:
        try:
            if nCode == 0:  # HC_ACTION
                kbd = KBDLLHOOKSTRUCT.from_address(lParam)
                vk = kbd.vkCode
                
                # 修飾キー (Ctrl, Alt, Win) が押されている場合は無条件でパススルー
                ctrl_pressed = (_user32.GetKeyState(VK_CONTROL) & 0x8000) != 0
                alt_pressed = (_user32.GetKeyState(VK_MENU) & 0x8000) != 0
                win_pressed = ((_user32.GetKeyState(VK_LWIN) & 0x8000) != 0) or \
                              ((_user32.GetKeyState(VK_RWIN) & 0x8000) != 0)
                
                if ctrl_pressed or alt_pressed or win_pressed:
                    return _user32.CallNextHookEx(self._h_hook, nCode, wParam, lParam)
                
                is_target = False
                key_name = ""
                
                if vk == VK_ESCAPE:
                    is_target = True
                    key_name = "escape"
                elif vk == VK_BACK:
                    is_target = True
                    key_name = "backspace"
                elif vk == VK_TAB:
                    is_target = True
                    key_name = "tab"
                else:
                    # ToUnicode を使ってキーボードレイアウトに応じた文字を取得
                    char = self._vk_to_char(vk, kbd.scanCode)
                    if char:
                        char_lower = char.lower()
                        if char_lower in self._hint_chars or char_lower in self._prefix_keys:
                            is_target = True
                            key_name = char_lower
                
                is_down = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
                is_up = wParam in (WM_KEYUP, WM_SYSKEYUP)
                
                if is_down:
                    if is_target:
                        self._blocked_vks.add(vk)
                        # メインスレッドのキューに送信
                        self._callback(key_name)
                        return 1  # Suppress (ブロック)
                elif is_up:
                    if vk in self._blocked_vks:
                        self._blocked_vks.discard(vk)
                        return 1  # Suppress (ブロック)
                        
        except Exception as e:
            print(f"[KeyboardHook] Error in hook callback: {e}")
            import traceback
            try:
                with open("hook_debug.log", "a", encoding="utf-8") as f:
                    f.write(f"Error in hook callback: {e}\n")
                    traceback.print_exc(file=f)
            except Exception:
                pass
            
        return _user32.CallNextHookEx(self._h_hook, nCode, wParam, lParam)
