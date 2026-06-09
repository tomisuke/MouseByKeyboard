"""
Win32 RegisterHotKey を使ったグローバルホットキー登録。
keyboard ライブラリの add_hotkey は Shift/CapsLock の状態を汚染することがある
ため、OS API を直接使うことで副作用を排除する。
"""
from __future__ import annotations
import ctypes
import ctypes.wintypes
import queue
import threading
import time

_user32 = ctypes.windll.user32

WM_HOTKEY   = 0x0312
MOD_ALT     = 0x0001
MOD_CTRL    = 0x0002
MOD_SHIFT   = 0x0004
MOD_WIN     = 0x0008
MOD_NOREPEAT = 0x4000

_VK_MAP: dict = {
    'a':0x41,'b':0x42,'c':0x43,'d':0x44,'e':0x45,'f':0x46,'g':0x47,'h':0x48,
    'i':0x49,'j':0x4A,'k':0x4B,'l':0x4C,'m':0x4D,'n':0x4E,'o':0x4F,'p':0x50,
    'q':0x51,'r':0x52,'s':0x53,'t':0x54,'u':0x55,'v':0x56,'w':0x57,'x':0x58,
    'y':0x59,'z':0x5A,
    '0':0x30,'1':0x31,'2':0x32,'3':0x33,'4':0x34,
    '5':0x35,'6':0x36,'7':0x37,'8':0x38,'9':0x39,
    'f1':0x70,'f2':0x71,'f3':0x72,'f4':0x73,'f5':0x74,'f6':0x75,
    'f7':0x76,'f8':0x77,'f9':0x78,'f10':0x79,'f11':0x7A,'f12':0x7B,
    'space':0x20,'enter':0x0D,'return':0x0D,'tab':0x09,
    'backspace':0x08,'delete':0x2E,'insert':0x2D,
    'home':0x24,'end':0x23,'pageup':0x21,'pagedown':0x22,
    'left':0x25,'up':0x26,'right':0x27,'down':0x28,
    'escape':0x1B,
}


def _parse_hotkey(hk: str) -> tuple[int, int]:
    """'ctrl+shift+q' -> (modifiers, vk_code)"""
    mods = 0
    vk = 0
    for part in hk.lower().split('+'):
        part = part.strip()
        if part == 'ctrl':    mods |= MOD_CTRL
        elif part == 'shift': mods |= MOD_SHIFT
        elif part == 'alt':   mods |= MOD_ALT
        elif part == 'win':   mods |= MOD_WIN
        else:
            vk = _VK_MAP.get(part, ord(part.upper()) if len(part) == 1 else 0)
    return mods, vk


class HotkeyManager(threading.Thread):
    """
    バックグラウンドスレッドで Win32 メッセージポンプを回し、
    RegisterHotKey で登録したホットキーを受信して event_queue に送る。
    keyboard ライブラリを使わないのでキーボード状態に副作用がない。
    """

    def __init__(self, event_queue: queue.Queue) -> None:
        super().__init__(daemon=True, name='HotkeyManager')
        self._queue = event_queue
        self._pending: list[tuple[str, str]] = []   # [(hk_str, event_type)]
        self._registered: dict[int, str] = {}        # hk_id -> event_type
        self._next_id = 300
        self._ready = threading.Event()
        self._running = True

    def add(self, hk_str: str, event_type: str) -> None:
        """スレッド起動前にホットキーを予約する。"""
        self._pending.append((hk_str, event_type))

    def wait_ready(self, timeout: float = 5.0) -> None:
        self._ready.wait(timeout)

    def run(self) -> None:
        for hk_str, etype in self._pending:
            mods, vk = _parse_hotkey(hk_str)
            if not vk:
                print(f'[HotkeyManager] 解析失敗: {hk_str!r}')
                continue
            hid = self._next_id
            self._next_id += 1
            ok = _user32.RegisterHotKey(None, hid, mods | MOD_NOREPEAT, vk)
            if ok:
                self._registered[hid] = etype
                print(f'[HotkeyManager] 登録: {hk_str!r} -> {etype} (id={hid})')
            else:
                err = ctypes.get_last_error()
                print(f'[HotkeyManager] 登録失敗: {hk_str!r} err={err}')

        self._ready.set()

        msg = ctypes.wintypes.MSG()
        while self._running:
            # PeekMessage はブロックしないので CPU 消費を抑えるため短い sleep
            ret = _user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1)  # PM_REMOVE
            if ret:
                if msg.message == WM_HOTKEY:
                    etype = self._registered.get(msg.wParam)
                    if etype:
                        self._queue.put({'type': etype})
            else:
                time.sleep(0.01)

        for hid in list(self._registered):
            _user32.UnregisterHotKey(None, hid)
        print('[HotkeyManager] 停止')

    def stop(self) -> None:
        self._running = False
