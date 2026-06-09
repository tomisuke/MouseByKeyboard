from __future__ import annotations
import queue
import threading
from typing import Optional

import win32gui

from config import Config
from scanner import Scanner
from hint_manager import HintState, generate_tags
from overlay import HintOverlay
from clicker import Clicker

# 安全タイムアウト: ヒントモードが30秒以上継続した場合は自動キャンセル
_HINT_SAFETY_TIMEOUT = 30.0


class App:
    _MODE_IDLE     = 'idle'
    _MODE_SCANNING = 'scanning'
    _MODE_HINT     = 'hint'

    def __init__(self, root, config: Config) -> None:
        import tkinter as tk
        self._root: tk.Tk = root
        self.config = config
        self._scanner = Scanner(config)
        self._clicker = Clicker()
        self._queue: queue.Queue = queue.Queue()
        self._mode = self._MODE_IDLE
        self._state: Optional[HintState] = None
        self._focus_hwnd: int = 0
        self._registered_hotkeys: list = []
        self._kb_hook = None          # keyboard suppress フック
        self._safety_timer: Optional[threading.Timer] = None
        self._search_method = 'uia'
        self._last_active_only = False

        # オーバーレイ: tkinterキーバインドも持つ（フォーカスが取れた場合の補助）
        self._overlay = HintOverlay(
            root, config,
            on_key=self._on_key_char,
            on_special=self._on_special_key,
        )

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._register_hotkeys()
        self._root.after(10, self._poll)

    # ------------------------------------------------------------------
    # Event loop (main thread)
    # ------------------------------------------------------------------

    def _poll(self) -> None:
        try:
            while True:
                event = self._queue.get_nowait()
                self._dispatch(event)
        except queue.Empty:
            pass
        self._root.after(10, self._poll)

    def _dispatch(self, event: dict) -> None:
        t = event['type']
        if t == 'hotkey_active':
            self._start_scan(active_only=True)
        elif t == 'hotkey_all':
            self._start_scan(active_only=False)
        elif t == 'scan_done':
            self._on_scan_done(event['elements'])
        elif t == 'key_down':
            self._on_key_name(event['name'])
        elif t == 'safety_cancel':
            print('[KN] Safety timeout: cancelling hint mode')
            self._cancel()
        elif t == 'open_settings':
            self._open_settings()
        elif t == 'quit':
            self._quit()

    # ------------------------------------------------------------------
    # Hotkeys  (Win32 RegisterHotKey — keyboard ライブラリ不使用)
    # ------------------------------------------------------------------

    def _register_hotkeys(self) -> None:
        from hotkey_manager import HotkeyManager
        mgr = HotkeyManager(self._queue)
        mgr.add(self.config.hotkey_active, 'hotkey_active')
        mgr.add(self.config.hotkey_all,    'hotkey_all')
        mgr.start()
        mgr.wait_ready()
        self._hotkey_manager = mgr

    def _unregister_hotkeys(self) -> None:
        if hasattr(self, '_hotkey_manager'):
            self._hotkey_manager.stop()

    # ------------------------------------------------------------------
    # Keyboard hook (suppress, active only during hint mode)
    # ------------------------------------------------------------------

    def _install_kb_hook(self) -> None:
        from keyboard_hook import SelectiveKeyboardHook

        def on_key(name: str) -> None:
            self._queue.put({'type': 'key_down', 'name': name})

        # フック前に修飾キーの状態をリセット（押しっぱなし判定を防ぐ）
        self._release_modifiers()

        # プレフィックスキーのリストを作成
        prefix_keys = []
        if self.config.prefix_double: prefix_keys.append(self.config.prefix_double)
        if self.config.prefix_right:  prefix_keys.append(self.config.prefix_right)
        if self.config.prefix_middle: prefix_keys.append(self.config.prefix_middle)

        self._kb_hook = SelectiveKeyboardHook(
            callback=on_key,
            hint_chars=self.config.hint_chars,
            prefix_keys=prefix_keys
        )
        self._kb_hook.install()

        # 安全タイマー: 30秒で自動キャンセル
        self._safety_timer = threading.Timer(
            _HINT_SAFETY_TIMEOUT,
            lambda: self._queue.put({'type': 'safety_cancel'})
        )
        self._safety_timer.daemon = True
        self._safety_timer.start()

    def _remove_kb_hook(self) -> None:
        if self._safety_timer is not None:
            self._safety_timer.cancel()
            self._safety_timer = None
        if self._kb_hook is not None:
            try:
                self._kb_hook.uninstall()
            except Exception as e:
                print(f"[KN] Hook uninstall error: {e}")
            self._kb_hook = None
        # フック解除時にも修飾キーの状態をリセット
        self._release_modifiers()

    def _release_modifiers(self) -> None:
        """強制的に修飾キーのKeyUpイベントを送り、キーのスタックを防止する"""
        import ctypes
        user32 = ctypes.windll.user32
        KEYEVENTF_KEYUP = 0x0002
        vks = [
            0x10, 0xA0, 0xA1,  # VK_SHIFT, VK_LSHIFT, VK_RSHIFT
            0x11, 0xA2, 0xA3,  # VK_CONTROL, VK_LCONTROL, VK_RCONTROL
            0x12, 0xA4, 0xA5,  # VK_MENU, VK_LMENU, VK_RMENU
            0x5B, 0x5C         # VK_LWIN, VK_RWIN
        ]
        for vk in vks:
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------

    def _start_scan(self, active_only: bool, force_method: Optional[str] = None) -> None:
        # Allow initiating rescan even when in hint mode
        if self._mode != self._MODE_IDLE and self._mode != self._MODE_HINT:
            if self._mode == self._MODE_SCANNING:
                return
                
        was_in_hint = (self._mode == self._MODE_HINT)
        if was_in_hint:
            self._remove_kb_hook()
            self._overlay.hide()

        self._mode = self._MODE_SCANNING
        self._last_active_only = active_only
        self._focus_hwnd = win32gui.GetForegroundWindow()
        
        # Determine default search method if not forced
        if force_method is None:
            if self._focus_hwnd:
                cls = win32gui.GetClassName(self._focus_hwnd)
                # Auto-select image mode for browsers and Electron apps (e.g. Chrome, VS Code, Discord)
                if cls in ('Chrome_WidgetWin_1', 'MozillaWindowClass'):
                    self._search_method = 'image'
                else:
                    self._search_method = 'uia'
            else:
                self._search_method = 'uia'
        else:
            self._search_method = force_method

        print(f'[KN] Scan start hwnd={self._focus_hwnd} method={self._search_method}')

        def _run() -> None:
            import time
            t0 = time.time()
            if self._search_method == 'image':
                elements = (self._scanner.scan_active_image() if active_only
                            else self._scanner.scan_all_image())
            else:
                elements = (self._scanner.scan_active() if active_only
                            else self._scanner.scan_all())
            print(f'[KN] Scan done: {len(elements)} elements in {(time.time()-t0)*1000:.0f}ms')
            self._queue.put({'type': 'scan_done', 'elements': elements})

        threading.Thread(target=_run, daemon=True).start()

    def _on_scan_done(self, elements: list) -> None:
        if not elements:
            print('[KN] No elements, aborting')
            self._mode = self._MODE_IDLE
            
            # Fallback to image mode if UIA returns nothing
            if self._search_method == 'uia':
                print('[KN] Fallback: UIA found 0 elements. Retrying with image mode.')
                self._search_method = 'image'
                self._start_scan(active_only=self._last_active_only, force_method='image')
            return
            
        tags = generate_tags(len(elements), self.config.hint_chars)
        self._state = HintState(elements, tags)
        self._mode = self._MODE_HINT

        # suppressフックを先に入れてからオーバーレイ表示
        # → フォーカスに依存せずキー入力を確実に捕捉
        self._install_kb_hook()
        print(f'[KN] Showing overlay ({len(elements)} elements)')
        self._overlay.show(elements, tags)
        self._overlay.show_search_method_indicator(self._search_method)

    # ------------------------------------------------------------------
    # Key handling  (keyboard hookから呼ばれる / overlayのtkinterバインドから呼ばれる)
    # ------------------------------------------------------------------

    def _on_key_name(self, name: str) -> None:
        """keyboard hookスレッド経由: キー名（例: 'a', 'escape', 'backspace'）"""
        if self._mode != self._MODE_HINT:
            return
        state = self._state
        if state is None:
            return

        if name in ('esc', 'escape'):
            self._cancel()
            return
        if name == 'backspace':
            state.backspace()
            self._overlay.update_filter(state.typed, state.visible, state.tags)
            return
        if name == 'tab':
            self._toggle_search_method()
            return

        # プレフィックスキー（タグ入力前のみ有効）
        if not state.typed:
            if name == self.config.prefix_double:
                state.set_click_mode(HintState.CLICK_DOUBLE)
                self._overlay.show_mode_indicator('double')
                return
            if name == self.config.prefix_right:
                state.set_click_mode(HintState.CLICK_RIGHT)
                self._overlay.show_mode_indicator('right')
                return
            if name == self.config.prefix_middle:
                state.set_click_mode(HintState.CLICK_MIDDLE)
                self._overlay.show_mode_indicator('middle')
                return

        # ヒント文字
        if len(name) == 1 and name in self.config.hint_chars:
            self._process_hint_char(name)

    def _toggle_search_method(self) -> None:
        next_method = 'image' if self._search_method == 'uia' else 'uia'
        print(f'[KN] Toggling search method to {next_method}')
        self._start_scan(active_only=self._last_active_only, force_method=next_method)

    def _on_key_char(self, char: str) -> None:
        """overlayのtkinterキーバインド経由（フォーカスが取れた場合の補助）"""
        # keyboard hookが既に処理するので二重処理を防ぐ
        # suppress=Trueのhookがある場合はここには来ないが、念のためガード
        if self._kb_hook is not None:
            return
        self._process_hint_char(char)

    def _on_special_key(self, name: str) -> None:
        """overlayのtkinterキーバインド経由（フォーカスが取れた場合の補助）"""
        if self._kb_hook is not None:
            return  # hookが処理するのでスキップ
        if name == 'escape':
            self._cancel()
        elif name == 'backspace' and self._state:
            self._state.backspace()
            self._overlay.update_filter(
                self._state.typed, self._state.visible, self._state.tags)

    def _process_hint_char(self, char: str) -> None:
        if self._mode != self._MODE_HINT:
            return
        state = self._state
        if state is None:
            return
        if char not in self.config.hint_chars:
            return

        result = state.input_char(char)
        if result == 'invalid':
            return
        if result == 'filter':
            self._overlay.update_filter(state.typed, state.visible, state.tags)
            return
        if result == 'match':
            match = state.get_match()
            if match:
                rect, element = match
                self._finish(element, rect, state.click_mode)

    # ------------------------------------------------------------------
    # Click & cleanup
    # ------------------------------------------------------------------

    def _finish(self, element, rect, click_mode: str) -> None:
        self._remove_kb_hook()
        self._overlay.hide()
        self._state = None
        self._mode = self._MODE_IDLE
        self._restore_focus()
        self._root.after(60, lambda: self._clicker.click(element, rect, click_mode))

    def _cancel(self) -> None:
        self._remove_kb_hook()
        self._overlay.hide()
        self._state = None
        self._mode = self._MODE_IDLE
        self._restore_focus()

    def _restore_focus(self) -> None:
        if self._focus_hwnd:
            try:
                win32gui.SetForegroundWindow(self._focus_hwnd)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _open_settings(self) -> None:
        from settings_window import SettingsWindow
        SettingsWindow(self._root, self.config, self._apply_new_config)

    def _apply_new_config(self, new_config: Config) -> None:
        self._unregister_hotkeys()
        self.config.__dict__.update(new_config.__dict__)
        self._register_hotkeys()

    # ------------------------------------------------------------------
    # Exit
    # ------------------------------------------------------------------

    def _quit(self) -> None:
        self._remove_kb_hook()
        self._unregister_hotkeys()
        self._root.destroy()
