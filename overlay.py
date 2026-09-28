from __future__ import annotations
import tkinter as tk
from tkinter import font as tkfont
from typing import List, Set, Optional, Callable

import win32api

# Badge colors — background must NOT be 'black' (black = transparent on this window)
_BADGE_BG      = '#FFFFFF'   # white background
_BADGE_BORDER  = '#FF8C00'   # orange border (high visibility dark orange)
_BADGE_FG      = '#010101'   # near-black text (avoiding perfect black #000000 to prevent text transparency)
_BADGE_HIT_FG  = '#CC0000'   # typed-prefix accent (red when partially matched)
_TEXT_OUTLINE  = '#FFFFFF'   # white outline behind text for contrast
_TRANSPARENT   = 'black'
_BADGE_PAD     = 2           # badge padding px (reduced for size 8 font)

_MODE_COLORS = {
    'double': '#FF6B6B',
    'right':  '#6BCB77',
    'middle': '#4D96FF',
}
_MODE_LABELS = {
    'double': '[ DOUBLE CLICK ]',
    'right':  '[ RIGHT CLICK ]',
    'middle': '[ MIDDLE CLICK ]',
}


class HintOverlay:
    def __init__(self, root: tk.Tk, config,
                 on_key: Callable[[str], None],
                 on_special: Callable[[str], None]) -> None:
        """
        on_key(char)     -- called with a printable character key
        on_special(name) -- called with 'escape' or 'backspace'
        """
        self.config = config
        self._root = root
        self._on_key = on_key
        self._on_special = on_special

        self._top = tk.Toplevel(root)
        self._canvas: tk.Canvas
        self._vx = self._vy = self._vw = self._vh = 0
        self._badge_items: dict = {}   # tag -> (bg_id, text_id)
        self._mode_id: Optional[int] = None
        self._method_id: Optional[int] = None
        self._font: Optional[tkfont.Font] = None
        self._current_mode: str = 'left'
        self._current_method: str = 'uia'
        self._indicator_ids: List[int] = []

        self._setup()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _setup(self) -> None:
        t = self._top
        t.overrideredirect(True)
        t.attributes('-topmost', True)
        # transparentcolor makes black pixels see-through
        t.attributes('-transparentcolor', _TRANSPARENT)
        t.configure(bg=_TRANSPARENT)
        t.withdraw()

        # Cover all monitors
        self._vx = win32api.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
        self._vy = win32api.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
        self._vw = win32api.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
        self._vh = win32api.GetSystemMetrics(79)   # SM_CYVIRTUALSCREEN
        t.geometry(f'{self._vw}x{self._vh}{self._vx:+d}{self._vy:+d}')

        self._canvas = tk.Canvas(t, bg=_TRANSPARENT, highlightthickness=0)
        self._canvas.pack(fill=tk.BOTH, expand=True)

        # Bind keyboard input to this window so we receive keys without
        # a global suppress hook.  The window grabs focus when shown.
        t.bind('<KeyPress>', self._handle_keypress)

    def _handle_keypress(self, event: tk.Event) -> None:
        keysym = event.keysym.lower()
        if keysym in ('escape', 'backspace'):
            self._on_special(keysym)
            return
        char = event.char.lower() if event.char else ''
        if char:
            self._on_key(char)

    # ------------------------------------------------------------------
    # Font helper
    # ------------------------------------------------------------------

    def _get_font(self) -> tkfont.Font:
        size = max(self.config.font_size, 6)   # 最低 6pt を保証
        if self._font is None or self._font.cget('size') != size:
            self._font = tkfont.Font(family='Consolas', size=size, weight='bold')
        return self._font

    # ------------------------------------------------------------------
    # Public API  (called from main thread only)
    # ------------------------------------------------------------------

    def _draw_badge(self, cx: int, cy: int, tag: str, font, scan_finished: bool = False) -> tuple:
        """バッジ1個を描画して (bg_id, outline_ids, tx_id, x1, y1, x2, y2) を返す。"""
        display_tag = tag.upper()
        pad = _BADGE_PAD
        tw = font.measure(display_tag)
        th = font.metrics('linespace')
        x1, y1 = cx - tw // 2 - pad, cy - th // 2 - pad
        x2, y2 = cx + tw // 2 + pad, cy + th // 2 + pad

        # スキャン完了時は濃いオレンジ、スキャン進行中は薄いオレンジの枠線にする
        border_color = _BADGE_BORDER if scan_finished else '#FFCC80'

        bg_id = self._canvas.create_rectangle(
            x1, y1, x2, y2,
            fill=_BADGE_BG, outline=border_color, width=2,
        )
        # 背景が白になり、フォントも小さいため、テキスト縁取りは不要
        outline_ids = []
        tx_id = self._canvas.create_text(
            cx, cy, text=display_tag, font=font, fill=_BADGE_FG, anchor='center',
        )
        return bg_id, outline_ids, tx_id, x1, y1, x2, y2

    def show(self, elements: list, tags: List[str], scan_finished: bool = False) -> None:
        font = self._get_font()

        # 既存のバッジと新しいリクエストの互換性をチェック
        # elements の数が現在の _badge_items より減っている、または
        # 前半のタグが一致していない場合は、全描き直しを行う
        needs_full_redraw = False
        if len(elements) < len(self._badge_items):
            needs_full_redraw = True
        else:
            for i, tag in enumerate(tags[:len(self._badge_items)]):
                if tag not in self._badge_items:
                    needs_full_redraw = True
                    break

        if needs_full_redraw:
            self._canvas.delete('all')
            self._badge_items.clear()
            self._mode_id = None
            self._method_id = None

        border_color = _BADGE_BORDER if scan_finished else '#888888'

        # 既存バッジの枠線色を更新 (スキャン完了ステータスの変化を反映)
        for tag, (bg_id, outline_ids, tx_id, *_) in self._badge_items.items():
            self._canvas.itemconfig(bg_id, outline=border_color)

        # 未描画の新規要素のみを描画して追加
        for (rect, _elem), tag in zip(elements, tags):
            if tag in self._badge_items:
                continue  # すでに描画済み

            cx = (rect.left + rect.right) // 2 - self._vx
            cy = (rect.top + rect.bottom) // 2 - self._vy

            bg_id, outline_ids, tx_id, x1, y1, x2, y2 = self._draw_badge(cx, cy, tag, font, scan_finished)
            self._badge_items[tag] = (bg_id, outline_ids, tx_id, x1, y1, x2, y2)

        self._top.deiconify()
        self._top.lift()
        self._top.focus_force()   # grab keyboard focus; no suppress hook needed
        self._top.update_idletasks()
        
        # Force position and size using Win32 API to bypass Tkinter multi-monitor coordinate bugs
        try:
            import win32gui
            import win32con
            # winfo_id() は Toplevel 内部の子ウィンドウを指すため、それに
            # SetWindowPos しても実際のトップレベル位置は動かない
            # (Tkinter の .geometry() が負の座標で計算した誤った位置のまま残る)。
            # GA_ROOT で真のトップレベル祖先ウィンドウを取得して移動させる。
            GA_ROOT = 2
            hwnd = win32gui.GetAncestor(self._top.winfo_id(), GA_ROOT)

            # SWP_NOACTIVATE = 0x0010
            # SWP_SHOWWINDOW = 0x0040
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                self._vx, self._vy,
                self._vw, self._vh,
                win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW
            )
        except Exception as e:
            print(f"[KN] Win32 SetWindowPos in show() failed: {e}")
            
        self.update_indicators()

    def update_filter(self, typed: str, visible: Set[int], tags: List[str]) -> None:
        visible_tags = {tags[i] for i in visible}
        hit = len(typed) > 0
        fg = _BADGE_HIT_FG if hit else _BADGE_FG

        for tag, (bg_id, outline_ids, tx_id, *_) in self._badge_items.items():
            if tag not in visible_tags:
                self._canvas.itemconfig(bg_id, fill=_TRANSPARENT, outline=_TRANSPARENT)
                for oid in outline_ids:
                    self._canvas.itemconfig(oid, fill=_TRANSPARENT)
                self._canvas.itemconfig(tx_id, fill=_TRANSPARENT)
            else:
                self._canvas.itemconfig(bg_id, fill=_BADGE_BG, outline=_BADGE_BORDER)
                for oid in outline_ids:
                    self._canvas.itemconfig(oid, fill=_TEXT_OUTLINE)
                self._canvas.itemconfig(tx_id, fill=fg)

    def show_mode_indicator(self, mode: str) -> None:
        self.update_indicators(mode=mode)

    def show_search_method_indicator(self, method: str) -> None:
        self.update_indicators(method=method)

    def update_indicators(self, mode: Optional[str] = None, method: Optional[str] = None) -> None:
        if mode is not None:
            self._current_mode = mode
        if method is not None:
            self._current_method = method

        if hasattr(self, '_indicator_ids'):
            for iid in self._indicator_ids:
                try:
                    self._canvas.delete(iid)
                except Exception:
                    pass
        self._indicator_ids = []

        if not getattr(self.config, 'show_indicators', True):
            return

        rects = self._get_target_monitor_rects()
        if not rects:
            return

        font = tkfont.Font(family='Segoe UI', size=10, weight='bold')

        for rect in rects:
            ids = self._draw_indicator_on_monitor(rect, self._current_mode, self._current_method, font)
            self._indicator_ids.extend(ids)

    def _get_target_monitor_rects(self) -> list:
        display_opt = getattr(self.config, 'indicator_display', 'active_window')
        
        all_monitors = win32api.EnumDisplayMonitors()
        if display_opt == 'all':
            return [m[2] for m in all_monitors]
            
        if display_opt == 'primary':
            hmon = win32api.MonitorFromWindow(0, 1)
            info = win32api.GetMonitorInfo(hmon)
            return [info['Monitor']]
            
        if display_opt == 'active_window':
            try:
                import win32gui
                hwnd = win32gui.GetForegroundWindow()
                if hwnd:
                    hmon = win32api.MonitorFromWindow(hwnd, 1)
                    info = win32api.GetMonitorInfo(hmon)
                    return [info['Monitor']]
            except Exception:
                pass
            hmon = win32api.MonitorFromWindow(0, 1)
            info = win32api.GetMonitorInfo(hmon)
            return [info['Monitor']]
            
        if display_opt == 'mouse':
            try:
                pos = win32api.GetCursorPos()
                hmon = win32api.MonitorFromPoint(pos, 1)
                info = win32api.GetMonitorInfo(hmon)
                return [info['Monitor']]
            except Exception:
                pass
            hmon = win32api.MonitorFromWindow(0, 1)
            info = win32api.GetMonitorInfo(hmon)
            return [info['Monitor']]
            
        return [[0, 0, win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)]]

    def _draw_indicator_on_monitor(self, rect: tuple, mode: Optional[str], method: Optional[str], font) -> list:
        m_left, m_top, m_right, m_bottom = rect
        
        mode_label = None
        mode_color = None
        if mode and mode != 'left':
            if mode == 'double':
                mode_label = "DOUBLE CLICK"
                mode_color = "#FF6B6B"
            elif mode == 'right':
                mode_label = "RIGHT CLICK"
                mode_color = "#6BCB77"
            elif mode == 'middle':
                mode_label = "MIDDLE CLICK"
                mode_color = "#4D96FF"
                
        method_label = "UI ELEMENT SEARCH"
        method_color = "#4D96FF"
        if method == 'hybrid':
            method_label = "HYBRID SEARCH"
            method_color = "#A855F7"
        elif method == 'image':
            method_label = "IMAGE SEARCH"
            method_color = "#FFB72B"
            
        pad_x = 12
        dot_size = 8
        dot_margin = 6
        pad_y = 6
        th = font.metrics('linespace')
        pill_h = pad_y * 2 + th
        
        spacing = 8
        margin = 25
        
        w_method = pad_x * 2 + dot_size + dot_margin + font.measure(method_label)
        w_mode = 0
        if mode_label:
            w_mode = pad_x * 2 + dot_size + dot_margin + font.measure(mode_label)
            
        total_w = w_method
        if w_mode > 0:
            total_w += spacing + w_mode
            
        total_h = pill_h
        
        left_c = m_left - self._vx
        top_c = m_top - self._vy
        right_c = m_right - self._vx
        bottom_c = m_bottom - self._vy
        
        pos_opt = getattr(self.config, 'indicator_position', 'top_center')
        
        if pos_opt == 'top_left':
            rx = left_c + margin
            ry = top_c + margin
        elif pos_opt == 'top_right':
            rx = right_c - margin - total_w
            ry = top_c + margin
        elif pos_opt == 'center':
            rx = (left_c + right_c) // 2 - total_w // 2
            ry = (top_c + bottom_c) // 2 - total_h // 2
        elif pos_opt == 'bottom_left':
            rx = left_c + margin
            ry = bottom_c - margin - total_h
        elif pos_opt == 'bottom_center':
            rx = (left_c + right_c) // 2 - total_w // 2
            ry = bottom_c - margin - total_h
        elif pos_opt == 'bottom_right':
            rx = right_c - margin - total_w
            ry = bottom_c - margin - total_h
        else: # top_center
            rx = (left_c + right_c) // 2 - total_w // 2
            ry = top_c + margin
            
        ids = []
        curr_x = rx
        
        if mode_label:
            p_ids, p_w, _ = self._draw_pill(curr_x, ry, mode_label, mode_color, font)
            ids.extend(p_ids)
            curr_x += p_w + spacing
            
        p_ids, _, _ = self._draw_pill(curr_x, ry, method_label, method_color, font)
        ids.extend(p_ids)
        
        return ids

    def _draw_pill(self, rx1: float, ry1: float, text: str, dot_color: str, font) -> tuple:
        tw = font.measure(text)
        th = font.metrics('linespace')
        
        pad_x = 12
        pad_y = 6
        dot_size = 8
        dot_margin = 6
        
        pill_w = pad_x * 2 + dot_size + dot_margin + tw
        pill_h = pad_y * 2 + th
        
        rx2 = rx1 + pill_w
        ry2 = ry1 + pill_h
        
        ids = []
        
        bg_color = '#1C1C1E'
        border_color = '#3A3A3C'
        
        bg_id = self._create_round_rectangle(rx1, ry1, rx2, ry2, radius=pill_h/2, fill=bg_color, outline=border_color, width=1.5)
        ids.append(bg_id)
        
        cy = ry1 + pill_h / 2
        dot_x1 = rx1 + pad_x
        dot_y1 = cy - dot_size / 2
        dot_x2 = dot_x1 + dot_size
        dot_y2 = cy + dot_size / 2
        
        dot_id = self._canvas.create_oval(dot_x1, dot_y1, dot_x2, dot_y2, fill=dot_color, outline=dot_color)
        ids.append(dot_id)
        
        text_x = dot_x2 + dot_margin
        text_y = cy
        text_id = self._canvas.create_text(text_x, text_y, text=text, font=font, fill='#FFFFFF', anchor='w')
        ids.append(text_id)
        
        return ids, pill_w, pill_h

    def _create_round_rectangle(self, x1, y1, x2, y2, radius=10, **kwargs):
        points = [
            x1+radius, y1,
            x1+radius, y1,
            x2-radius, y1,
            x2-radius, y1,
            x2, y1,
            x2, y1+radius,
            x2, y1+radius,
            x2, y2-radius,
            x2, y2-radius,
            x2, y2,
            x2-radius, y2,
            x2-radius, y2,
            x1+radius, y2,
            x1+radius, y2,
            x1, y2,
            x1, y2-radius,
            x1, y2-radius,
            x1, y1+radius,
            x1, y1+radius,
            x1, y1
        ]
        return self._canvas.create_polygon(points, **kwargs, smooth=True)

    def hide(self) -> None:
        self._canvas.delete('all')
        self._badge_items.clear()
        self._mode_id = None
        self._method_id = None
        self._indicator_ids = []
        self._current_mode = 'left'
        self._top.update_idletasks()
        self._top.withdraw()
