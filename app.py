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
        self._clicker = Clicker(config)
        self._queue: queue.Queue = queue.Queue()
        self._mode = self._MODE_IDLE
        self._state: Optional[HintState] = None
        self._focus_hwnd: int = 0
        self._registered_hotkeys: list = []
        self._kb_hook = None          # keyboard suppress フック
        self._mouse_hook = None       # mouse フック
        self._safety_timer: Optional[threading.Timer] = None
        self._current_shown_method = None  # 'uia' or 'image'
        self._default_method = None        # 'uia' or 'image'
        self._last_active_only = True

        # スキャン処理用データ
        self._accumulated_uia = []
        self._accumulated_image = []
        self._done_uia = False
        self._done_image = False
        self._decision_timer_id = None

        import time
        self._last_activity_time = time.time()

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

        # ヒントモード中のウィンドウ切り替え監視
        if self._mode == self._MODE_HINT:
            curr_hwnd = win32gui.GetForegroundWindow()
            overlay_hwnd = 0
            if hasattr(self, '_overlay') and self._overlay._top:
                try:
                    # wm_frame() は "0x12345" のような16進数文字列を返すため、これをパースする
                    frame_str = self._overlay._top.wm_frame()
                    overlay_hwnd = int(frame_str, 16)
                except Exception:
                    try:
                        h = self._overlay._top.winfo_id()
                        while True:
                            parent = win32gui.GetParent(h)
                            if parent == 0:
                                break
                            h = parent
                        overlay_hwnd = h
                    except Exception:
                        pass
            
            if curr_hwnd != 0 and curr_hwnd != self._focus_hwnd and curr_hwnd != overlay_hwnd:
                print(f"[KN] Foreground window changed from {self._focus_hwnd} to {curr_hwnd}. Cancelling hint mode.")
                self._cancel()

        self._root.after(10, self._poll)

    def _dispatch(self, event: dict) -> None:
        t = event['type']
        if t == 'hotkey_active':
            self._start_scan(active_only=True)
        elif t == 'hotkey_all':
            self._start_scan(active_only=False)
        elif t == 'scan_partial_uia':
            self._on_scan_partial_uia(event['elements'])
        elif t == 'scan_partial_image':
            self._on_scan_partial_image(event['elements'])
        elif t == 'scan_done_uia':
            self._on_scan_done_uia()
        elif t == 'scan_done_image':
            self._on_scan_done_image()
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

        # 登録に完全に失敗したかチェック
        if mgr.registered_count == 0:
            print("[KN] ホットキーの登録にすべて失敗しました。")
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                "ホットキーの登録にすべて失敗しました。\n他のアプリケーションが同じショートカットキー（Ctrl+Q等）を使用していないか確認してください。\nアプリケーションを終了します。",
                "KeyNavigator - 起動エラー",
                0x00000010  # MB_ICONERROR
            )
            self._queue.put({'type': 'quit'})

    def _unregister_hotkeys(self) -> None:
        if hasattr(self, '_hotkey_manager'):
            self._hotkey_manager.stop()

    # ------------------------------------------------------------------
    # Keyboard hook (suppress, active only during hint mode)
    # ------------------------------------------------------------------

    def _install_kb_hook(self) -> None:
        from keyboard_hook import SelectiveKeyboardHook, MouseHook

        def on_key(name: str) -> None:
            self._queue.put({'type': 'key_down', 'name': name})

        def on_mouse_click() -> None:
            self._queue.put({'type': 'key_down', 'name': 'escape'})

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

        self._mouse_hook = MouseHook(callback=on_mouse_click)
        self._mouse_hook.install()

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
        if self._mouse_hook is not None:
            try:
                self._mouse_hook.uninstall()
            except Exception as e:
                print(f"[KN] Mouse hook uninstall error: {e}")
            self._mouse_hook = None
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

    def _is_invalid_active_window(self, hwnd: int) -> bool:
        if not hwnd:
            return True
        try:
            cls = win32gui.GetClassName(hwnd)
            if cls in ('Progman', 'WorkerW'):
                return True
        except Exception:
            return True
        return False

    def _estimate_elements_count(self, active_only: bool, method: str) -> int:
        hwnd = win32gui.GetForegroundWindow()
        if self._is_invalid_active_window(hwnd):
            hwnd = win32gui.FindWindow("Shell_TrayWnd", None)
            if not hwnd:
                return 150

        # 画像解析(image)を伴う場合は、要素数が大幅に増えるため余裕を持った見積もりをする
        if method == 'image':
            if active_only:
                return 400
            else:
                return 750

        # UIAスキャンの場合
        if active_only:
            if self.config.parallel_sub_scan:
                import comtypes
                import uiautomation as auto
                children_count = 0
                com_initialized = False
                try:
                    comtypes.CoInitialize()
                    com_initialized = True
                    ctrl = auto.ControlFromHandle(hwnd)
                    if ctrl:
                        children_count = len(ctrl.GetChildren())
                except Exception:
                    pass
                finally:
                    if com_initialized:
                        try:
                            comtypes.CoUninitialize()
                        except Exception:
                            pass
                if children_count > 0:
                    return min(500, max(150, children_count * 20))
                return 200
            else:
                return 150
        else:
            window_count = [0]
            def enum_cb(h, _) -> bool:
                if win32gui.IsWindowVisible(h) and not win32gui.IsIconic(h):
                    window_count[0] += 1
                return True
            win32gui.EnumWindows(enum_cb, None)
            w_count = min(self.config.max_scan_windows, window_count[0])
            return min(750, max(200, w_count * 40))

    def _filter_active_elements(self, elements: list, hwnd: int) -> list:
        if not elements:
            return []
        try:
            wl, wt, wr, wb = win32gui.GetWindowRect(hwnd)
        except Exception:
            return list(elements)
            
        filtered = []
        for r, ctrl in elements:
            cx = (r.left + r.right) // 2
            cy = (r.top + r.bottom) // 2
            if wl <= cx <= wr and wt <= cy <= wb:
                filtered.append((r, ctrl))
        return filtered

    def _start_scan(self, active_only: bool) -> None:
        # Allow initiating rescan even when in hint mode
        if self._mode != self._MODE_IDLE and self._mode != self._MODE_HINT:
            if self._mode == self._MODE_SCANNING:
                return
                
        was_in_hint = (self._mode == self._MODE_HINT)
        if was_in_hint:
            self._remove_kb_hook()
            self._overlay.hide()

        # タイマーのクリーンアップ
        if self._decision_timer_id is not None:
            try:
                self._root.after_cancel(self._decision_timer_id)
            except Exception:
                pass
            self._decision_timer_id = None

        self._mode = self._MODE_SCANNING
        self._last_active_only = active_only
        self._focus_hwnd = win32gui.GetForegroundWindow()
        if self._is_invalid_active_window(self._focus_hwnd):
            self._focus_hwnd = win32gui.FindWindow("Shell_TrayWnd", None)
        
        self._accumulated_uia = []
        self._accumulated_image = []
        self._done_uia = False
        self._done_image = False
        self._default_method = None
        self._current_shown_method = None

        # 予測要素数に基づき、事前にタグリストを一括生成
        self._preestimated_count_uia = self._estimate_elements_count(active_only, 'uia')
        self._preestimated_count_image = self._estimate_elements_count(active_only, 'image')
        self._pregenerated_tags_uia = generate_tags(self._preestimated_count_uia, self.config.hint_chars)
        self._pregenerated_tags_image = generate_tags(self._preestimated_count_image, self.config.hint_chars)

        print(f'[KN] Scan start hwnd={self._focus_hwnd}')

        # UIAスキャンスレッド
        def _run_uia() -> None:
            import time
            t0 = time.time()
            try:
                gen = (self._scanner.scan_active() if active_only
                       else self._scanner.scan_all())
                for partial in gen:
                    if partial:
                        self._queue.put({'type': 'scan_partial_uia', 'elements': partial})
            except Exception as e:
                print(f"[KN] UIA Scan thread error: {e}")
            finally:
                print(f'[KN] UIA Scan thread finished in {(time.time()-t0)*1000:.0f}ms')
                self._queue.put({'type': 'scan_done_uia'})

        # Imageスキャンスレッド
        def _run_image() -> None:
            import time
            t0 = time.time()
            try:
                gen = (self._scanner.scan_active_image() if active_only
                       else self._scanner.scan_all_image())
                for partial in gen:
                    if partial:
                        self._queue.put({'type': 'scan_partial_image', 'elements': partial})
            except Exception as e:
                print(f"[KN] Image Scan thread error: {e}")
            finally:
                print(f'[KN] Image Scan thread finished in {(time.time()-t0)*1000:.0f}ms')
                self._queue.put({'type': 'scan_done_image'})

        threading.Thread(target=_run_uia, daemon=True).start()
        threading.Thread(target=_run_image, daemon=True).start()

        # UIAの応答を待つためのタイマー (300ms)
        self._decision_timer_id = self._root.after(300, self._decide_default_method)

    def _on_scan_partial_uia(self, elements: list) -> None:
        if self._mode not in (self._MODE_SCANNING, self._MODE_HINT):
            return
        if self._state is not None and self._state.typed != '':
            return

        # 重複排除
        new_unique = []
        for r, ctrl in elements:
            cx = (r.left + r.right) // 2
            cy = (r.top + r.bottom) // 2
            w = r.width()
            h = r.height()
            
            is_dup = False
            for ur, _ in self._accumulated_uia:
                ucx = (ur.left + ur.right) // 2
                ucy = (ur.top + ur.bottom) // 2
                uw = ur.width()
                uh = ur.height()
                
                if abs(cx - ucx) <= 3 and abs(cy - ucy) <= 3 and abs(w - uw) <= 5 and abs(h - uh) <= 5:
                    is_dup = True
                    break
            if not is_dup:
                new_unique.append((r, ctrl))

        if new_unique:
            self._accumulated_uia.extend(new_unique)

        # 現在表示中が UIA であれば描画更新
        if self._current_shown_method == 'uia':
            self._update_overlay_display('uia')

    def _on_scan_partial_image(self, elements: list) -> None:
        if self._mode not in (self._MODE_SCANNING, self._MODE_HINT):
            return
        if self._state is not None and self._state.typed != '':
            return

        # 重複排除
        new_unique = []
        for r, ctrl in elements:
            cx = (r.left + r.right) // 2
            cy = (r.top + r.bottom) // 2
            w = r.width()
            h = r.height()
            
            is_dup = False
            for ur, _ in self._accumulated_image:
                ucx = (ur.left + ur.right) // 2
                ucy = (ur.top + ur.bottom) // 2
                uw = ur.width()
                uh = ur.height()
                
                if abs(cx - ucx) <= 3 and abs(cy - ucy) <= 3 and abs(w - uw) <= 5 and abs(h - uh) <= 5:
                    is_dup = True
                    break
            if not is_dup:
                new_unique.append((r, ctrl))

        if new_unique:
            self._accumulated_image.extend(new_unique)

        # 現在表示中が Image であれば描画更新
        if self._current_shown_method == 'image':
            self._update_overlay_display('image')

    def _get_tags_for_method(self, method: str, count: int) -> list:
        pregen_tags = self._pregenerated_tags_uia if method == 'uia' else self._pregenerated_tags_image
        if count > len(pregen_tags):
            print(f"[KN] Estimation warning: elements ({count}) exceeded pregenerated ({len(pregen_tags)})")
            new_tags = generate_tags(count + 100, self.config.hint_chars)
            if method == 'uia':
                self._pregenerated_tags_uia = new_tags
            else:
                self._pregenerated_tags_image = new_tags
            pregen_tags = new_tags
        return pregen_tags[:count]

    def _update_overlay_display(self, method: str) -> None:
        if self._mode != self._MODE_HINT:
            return
        
        elements = self._accumulated_uia if method == 'uia' else self._accumulated_image
        done_flag = self._done_uia if method == 'uia' else self._done_image
        
        current_len = len(elements)
        if current_len == 0:
            return
            
        tags = self._get_tags_for_method(method, current_len)

        # すでに状態がある場合は、キーモードを引き継いで再構築する
        if self._state is not None:
            click_mode = self._state.click_mode
            self._state = HintState(list(elements), tags)
            self._state.set_click_mode(click_mode)
        else:
            self._state = HintState(list(elements), tags)
            
        # オーバーレイに描画
        self._overlay.show(elements, tags, scan_finished=done_flag)
        self._overlay.show_search_method_indicator(method)
        if self._state.click_mode != HintState.CLICK_LEFT:
            self._overlay.show_mode_indicator(self._state.click_mode)

    def _on_scan_done_uia(self) -> None:
        if self._mode not in (self._MODE_SCANNING, self._MODE_HINT):
            return
        self._done_uia = True
        
        # デフォルト未決定の場合
        if self._default_method is None:
            if self._accumulated_uia:
                # UIAが高速に完了し、かつ要素が存在するため UIA をデフォルトに決定
                self._apply_default_method('uia')
            else:
                # UIAが高速に完了したが要素数が0。Image をデフォルトに決定
                self._apply_default_method('image')
            return

        # すでに決定済みで、現在表示中が UIA であれば、表示完了を更新
        if self._current_shown_method == 'uia':
            if not self._accumulated_uia:
                print('[KN] UIA done with 0 elements. Toggling to image.')
                self._apply_default_method('image')
            else:
                self._update_overlay_display('uia')

    def _on_scan_done_image(self) -> None:
        if self._mode not in (self._MODE_SCANNING, self._MODE_HINT):
            return
        self._done_image = True

        # すでに決定済みで、現在表示中が Image であれば、表示完了を更新
        if self._current_shown_method == 'image':
            if not self._accumulated_image:
                print('[KN] Image done with 0 elements, aborting')
                self._cancel()
            else:
                self._update_overlay_display('image')

    def _decide_default_method(self) -> None:
        if self._default_method is not None:
            return

        # 150ms 経過時点で UIA の要素がある（またはすでに完了している）場合は UIA
        if self._accumulated_uia:
            print('[KN] UIA selected by timer (elements found)')
            self._apply_default_method('uia')
        else:
            print('[KN] Image selected by timer (UIA slow or empty)')
            self._apply_default_method('image')

    def _apply_default_method(self, method: str) -> None:
        self._default_method = method
        self._current_shown_method = method
        
        # タイマーのキャンセル
        if self._decision_timer_id is not None:
            try:
                self._root.after_cancel(self._decision_timer_id)
            except Exception:
                pass
            self._decision_timer_id = None

        self._mode = self._MODE_HINT
        
        # 初回の描画更新とキーフック有効化
        elements = self._accumulated_uia if method == 'uia' else self._accumulated_image
        done_flag = self._done_uia if method == 'uia' else self._done_image
        
        tags = self._get_tags_for_method(method, len(elements))
        self._state = HintState(list(elements), tags)
        self._install_kb_hook()

        # オーバーレイに描画
        self._overlay.show(elements, tags, scan_finished=done_flag)
        self._overlay.show_search_method_indicator(method)

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
        if self._default_method is None:
            return  # デフォルト決定前はトグルさせない
            
        next_method = 'image' if self._current_shown_method == 'uia' else 'uia'
        print(f'[KN] Switching displayed method to {next_method}')
        self._current_shown_method = next_method

        # 表示中データを切り替えて再描画
        elements = self._accumulated_uia if next_method == 'uia' else self._accumulated_image
        done_flag = self._done_uia if next_method == 'uia' else self._done_image

        tags = self._get_tags_for_method(next_method, len(elements))
        
        # キー入力状態はリセットするが、クリックモードは引き継ぐ
        click_mode = self._state.click_mode if self._state else HintState.CLICK_LEFT
        self._state = HintState(list(elements), tags)
        self._state.set_click_mode(click_mode)

        self._overlay.show(elements, tags, scan_finished=done_flag)
        self._overlay.show_search_method_indicator(next_method)
        if click_mode != HintState.CLICK_LEFT:
            self._overlay.show_mode_indicator(click_mode)

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
        import ctypes
        import ctypes.wintypes
        pt = ctypes.wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        orig_pos = (pt.x, pt.y)

        self._remove_kb_hook()
        self._overlay.hide()
        self._state = None
        self._mode = self._MODE_IDLE
        self._restore_focus()
        
        # タイマーのクリーンアップ
        if self._decision_timer_id is not None:
            try:
                self._root.after_cancel(self._decision_timer_id)
            except Exception:
                pass
            self._decision_timer_id = None
        
        # アクティビティ時刻更新
        import time
        self._last_activity_time = time.time()
        
        self._root.after(60, lambda: self._clicker.click(element, rect, click_mode, orig_pos))

    def _cancel(self) -> None:
        self._remove_kb_hook()
        self._overlay.hide()
        self._state = None
        self._mode = self._MODE_IDLE
        self._restore_focus()
        
        # タイマーのクリーンアップ
        if self._decision_timer_id is not None:
            try:
                self._root.after_cancel(self._decision_timer_id)
            except Exception:
                pass
            self._decision_timer_id = None

        # アクティビティ時刻更新
        import time
        self._last_activity_time = time.time()

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
        try:
            self._scanner.shutdown()
        except Exception:
            pass
        try:
            self._root.quit()
        except Exception:
            pass
        try:
            self._root.destroy()
        except Exception:
            pass
