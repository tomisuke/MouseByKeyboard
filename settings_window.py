from __future__ import annotations
import tkinter as tk
from tkinter import messagebox

from config import Config


_FIELDS = [
    ('全画面スキャン ホットキー',        'hotkey_all',        str),
    ('アクティブ画面スキャン ホットキー', 'hotkey_active',     str),
    ('ヒント文字セット',                 'hint_chars',        str),
    ('ダブルクリック プレフィックスキー', 'prefix_double',     str),
    ('右クリック プレフィックスキー',     'prefix_right',      str),
    ('中央クリック プレフィックスキー',   'prefix_middle',     str),
    ('フォントサイズ (pt)',              'font_size',         int),
    ('スキャンタイムアウト (ms)',         'scan_timeout_ms',   int),
]


class SettingsWindow:
    def __init__(self, parent: tk.Tk, config: Config, on_save) -> None:
        self._config = config
        self._on_save = on_save

        win = tk.Toplevel(parent)
        win.title('KeyNavigator - 設定')
        win.resizable(False, False)
        win.grab_set()
        self._win = win
        self._vars: dict[str, tk.StringVar] = {}
        self._build()

    def _build(self) -> None:
        win = self._win
        pad = {'padx': 10, 'pady': 4}

        for row, (label, attr, _type) in enumerate(_FIELDS):
            tk.Label(win, text=label, anchor='e').grid(
                row=row, column=0, sticky='e', **pad)
            var = tk.StringVar(value=str(getattr(self._config, attr)))
            self._vars[attr] = var
            tk.Entry(win, textvariable=var, width=32).grid(
                row=row, column=1, sticky='w', **pad)

        # Helper text
        note = ('ホットキー例: ctrl+q, ctrl+shift+q\n'
                'プレフィックスキー例: ;  \'  ,')
        tk.Label(win, text=note, fg='#666666', justify='left').grid(
            row=len(_FIELDS), column=0, columnspan=2, padx=10, pady=(0, 4), sticky='w')

        btn_frame = tk.Frame(win)
        btn_frame.grid(row=len(_FIELDS) + 1, column=0, columnspan=2, pady=8)
        tk.Button(btn_frame, text='保存', command=self._save, width=10).pack(
            side='left', padx=6)
        tk.Button(btn_frame, text='キャンセル', command=self._win.destroy,
                  width=10).pack(side='left', padx=6)

    def _save(self) -> None:
        try:
            kwargs = {}
            for _label, attr, cast in _FIELDS:
                raw = self._vars[attr].get().strip()
                kwargs[attr] = cast(raw)
            new_cfg = Config(**kwargs)
            new_cfg.save()
            self._on_save(new_cfg)
            self._win.destroy()
        except Exception as exc:
            messagebox.showerror('設定エラー', str(exc), parent=self._win)
