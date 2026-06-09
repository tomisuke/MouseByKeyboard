from __future__ import annotations
import tkinter as tk
from tkinter import font as tkfont
from typing import List, Set, Optional, Callable

import win32api

# Badge colors — background must NOT be 'black' (black = transparent on this window)
_BADGE_BG      = '#FFFFFF'   # white background
_BADGE_BORDER  = '#1A1A1A'   # near-black border
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
        t.geometry(f'{self._vw}x{self._vh}+{self._vx}+{self._vy}')

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

    def _draw_badge(self, cx: int, cy: int, tag: str, font) -> tuple:
        """バッジ1個を描画して (bg_id, outline_ids, tx_id) を返す。"""
        pad = _BADGE_PAD
        tw = font.measure(tag)
        th = font.metrics('linespace')
        x1, y1 = cx - tw // 2 - pad, cy - th // 2 - pad
        x2, y2 = cx + tw // 2 + pad, cy + th // 2 + pad

        bg_id = self._canvas.create_rectangle(
            x1, y1, x2, y2,
            fill=_BADGE_BG, outline=_BADGE_BORDER, width=1,
        )
        # 背景が白になり、フォントも小さいため、テキスト縁取りは不要
        outline_ids = []
        tx_id = self._canvas.create_text(
            cx, cy, text=tag, font=font, fill=_BADGE_FG, anchor='center',
        )
        return bg_id, outline_ids, tx_id, x1, y1, x2, y2

    def show(self, elements: list, tags: List[str]) -> None:
        self._canvas.delete('all')
        self._badge_items.clear()
        self._mode_id = None
        self._method_id = None

        font = self._get_font()

        for (rect, _elem), tag in zip(elements, tags):
            cx = (rect.left + rect.right) // 2 - self._vx
            cy = (rect.top + rect.bottom) // 2 - self._vy

            bg_id, outline_ids, tx_id, x1, y1, x2, y2 = self._draw_badge(cx, cy, tag, font)
            self._badge_items[tag] = (bg_id, outline_ids, tx_id, x1, y1, x2, y2)

        self._top.deiconify()
        self._top.lift()
        self._top.focus_force()   # grab keyboard focus; no suppress hook needed

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
        if self._mode_id is not None:
            self._canvas.delete(self._mode_id)
        self._mode_id = self._canvas.create_text(
            self._vw // 2, 28,
            text=_MODE_LABELS.get(mode, mode.upper()),
            fill=_MODE_COLORS.get(mode, '#FFFFFF'),
            font=tkfont.Font(family='Arial', size=16, weight='bold'),
        )

    def show_search_method_indicator(self, method: str) -> None:
        if hasattr(self, '_method_id') and self._method_id is not None:
            self._canvas.delete(self._method_id)
        
        label = "[ UI ELEMENT SEARCH ]" if method == 'uia' else "[ IMAGE SEARCH (OCR/CV) ]"
        color = "#4D96FF" if method == 'uia' else "#FFB72B"
        
        self._method_id = self._canvas.create_text(
            self._vw // 2, 60,
            text=label,
            fill=color,
            font=tkfont.Font(family='Arial', size=14, weight='bold'),
        )

    def hide(self) -> None:
        self._canvas.delete('all')
        self._badge_items.clear()
        self._mode_id = None
        self._method_id = None
        self._top.withdraw()
