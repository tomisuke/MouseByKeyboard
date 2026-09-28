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
    ('最大スキャンウィンドウ数',         'max_scan_windows',   int),
    ('単一ウィンドウ内も並列スキャン',     'parallel_sub_scan',   bool),
    ('常に物理クリックを使用',          'force_physical_click', bool),
    ('情報表示を有効にする',             'show_indicators',     bool),
    ('情報表示画面',                    'indicator_display',   str),
    ('情報表示位置',                    'indicator_position',  str),
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
        self._vars: dict[str, tk.Variable] = {}
        self._build()

    def _build(self) -> None:
        win = self._win
        pad = {'padx': 10, 'pady': 4}
        from tkinter import ttk

        for row, (label, attr, _type) in enumerate(_FIELDS):
            tk.Label(win, text=label, anchor='e').grid(
                row=row, column=0, sticky='e', **pad)
            if _type is bool:
                var = tk.BooleanVar(value=bool(getattr(self._config, attr)))
                self._vars[attr] = var
                tk.Checkbutton(win, variable=var).grid(
                    row=row, column=1, sticky='w', **pad)
            elif attr == 'indicator_display':
                choices_map = {
                    'active_window': 'アクティブ窓のある画面',
                    'mouse': 'マウスカーソルのある画面',
                    'primary': 'プライマリ（メイン）画面',
                    'all': 'すべての画面'
                }
                current_val = getattr(self._config, attr)
                current_label = choices_map.get(current_val, 'アクティブ窓のある画面')
                
                var = tk.StringVar(value=current_label)
                self._vars[attr] = var
                
                cb = ttk.Combobox(win, textvariable=var, values=list(choices_map.values()), state='readonly', width=30)
                cb.grid(row=row, column=1, sticky='w', **pad)
            elif attr == 'indicator_position':
                choices_map = {
                    'top_left': '左上',
                    'top_center': '上中央',
                    'top_right': '右上',
                    'center': '画面中央',
                    'bottom_left': '左下',
                    'bottom_center': '下中央',
                    'bottom_right': '右下'
                }
                current_val = getattr(self._config, attr)
                current_label = choices_map.get(current_val, '上中央')
                
                var = tk.StringVar(value=current_label)
                self._vars[attr] = var
                
                cb = ttk.Combobox(win, textvariable=var, values=list(choices_map.values()), state='readonly', width=30)
                cb.grid(row=row, column=1, sticky='w', **pad)
            else:
                var = tk.StringVar(value=str(getattr(self._config, attr)))
                self._vars[attr] = var
                entry = tk.Entry(win, textvariable=var, width=32)
                entry.grid(row=row, column=1, sticky='w', **pad)
                if attr in ('hotkey_all', 'hotkey_active'):
                    self._setup_hotkey_entry(entry, var)

        # Helper text
        note = ('ホットキーは入力欄を選択し、設定したいキーの組み合わせを押してください。\n'
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
            display_map = {
                'アクティブ窓のある画面': 'active_window',
                'マウスカーソルのある画面': 'mouse',
                'プライマリ（メイン）画面': 'primary',
                'すべての画面': 'all'
            }
            position_map = {
                '左上': 'top_left',
                '上中央': 'top_center',
                '右上': 'top_right',
                '画面中央': 'center',
                '左下': 'bottom_left',
                '下中央': 'bottom_center',
                '右下': 'bottom_right'
            }

            kwargs = {}
            for _label, attr, cast in _FIELDS:
                if cast is bool:
                    kwargs[attr] = bool(self._vars[attr].get())
                elif attr == 'indicator_display':
                    label_val = self._vars[attr].get()
                    kwargs[attr] = display_map.get(label_val, 'active_window')
                elif attr == 'indicator_position':
                    label_val = self._vars[attr].get()
                    kwargs[attr] = position_map.get(label_val, 'top_center')
                else:
                    raw = self._vars[attr].get().strip()
                    kwargs[attr] = cast(raw)

            # --- バリデーションとフォーマット（小文字化・空白除去） ---
            # 1. ヒント文字セットの処理
            hint_chars = kwargs.get('hint_chars', '').lower().replace(' ', '')
            if not hint_chars:
                raise ValueError("ヒント文字セットを入力してください。")
            if len(hint_chars) < 2:
                raise ValueError("ヒント文字セットは2文字以上指定してください。")
            
            # ヒント文字の重複チェック
            seen_chars = set()
            for char in hint_chars:
                if char in seen_chars:
                    raise ValueError(f"ヒント文字セットに重複する文字 '{char}' が含まれています。")
                seen_chars.add(char)
            kwargs['hint_chars'] = hint_chars

            # 2. プレフィックスキーの処理と検証
            prefixes = {}
            prefix_fields = [
                ('prefix_double', 'ダブルクリック プレフィックスキー'),
                ('prefix_right', '右クリック プレフィックスキー'),
                ('prefix_middle', '中央クリック プレフィックスキー'),
            ]
            
            for attr, label in prefix_fields:
                val = kwargs.get(attr, '').lower().strip()
                if val:
                    if len(val) != 1:
                        raise ValueError(f"{label}は1文字で指定してください。")
                    prefixes[label] = val
                    kwargs[attr] = val
                else:
                    kwargs[attr] = ''

            # プレフィックスキー同士の重複チェック
            seen_prefixes = {}
            for label, val in prefixes.items():
                if val in seen_prefixes:
                    other_label = seen_prefixes[val]
                    raise ValueError(f"プレフィックスキーが重複しています:\n'{val}' が '{other_label}' と '{label}' の両方に使用されています。")
                seen_prefixes[val] = label

            # プレフィックスキーとヒント文字セットの重複チェック
            for label, val in prefixes.items():
                if val in seen_chars:
                    raise ValueError(f"重複エラー:\nプレフィックスキー '{val}' ({label}) が、ヒント文字セットにも含まれています。")
            # ----------------------------------------------------

            new_cfg = Config(**kwargs)
            new_cfg.save()
            self._on_save(new_cfg)
            self._win.destroy()
        except Exception as exc:
            messagebox.showerror('設定エラー', str(exc), parent=self._win)

    def _setup_hotkey_entry(self, entry: tk.Entry, var: tk.StringVar) -> None:
        original_val = [var.get()]

        def on_focus_in(event: tk.Event) -> None:
            original_val[0] = var.get()

        def on_focus_out(event: tk.Event) -> None:
            val = var.get()
            if val.endswith('+') or not val:
                var.set(original_val[0])

        def on_key_press(event: tk.Event) -> str:
            keysym = event.keysym.lower()
            
            # 修飾キーの判定 (Windows Tkinter の state ビットマスクと keysym の両方で判定)
            is_ctrl = bool(event.state & 0x0004)
            is_shift = bool(event.state & 0x0001)
            is_alt = bool(event.state & 0x20000) or bool(event.state & 0x0020)
            is_win = bool(event.state & 0x0040) or bool(event.state & 0x0008)
            
            if keysym in ('control_l', 'control_r'):
                is_ctrl = True
            elif keysym in ('shift_l', 'shift_r'):
                is_shift = True
            elif keysym in ('alt_l', 'alt_r'):
                is_alt = True
            elif keysym in ('win_l', 'win_r', 'meta_l', 'meta_r'):
                is_win = True
                
            is_modifier_key = keysym in (
                'control_l', 'control_r', 'shift_l', 'shift_r', 'alt_l', 'alt_r', 'win_l', 'win_r', 'meta_l', 'meta_r'
            )
            
            mods = []
            if is_ctrl: mods.append('ctrl')
            if is_shift: mods.append('shift')
            if is_alt: mods.append('alt')
            if is_win: mods.append('win')
            
            if is_modifier_key:
                val = '+'.join(mods)
                if val:
                    val += '+'
                var.set(val)
            else:
                key_map = {
                    'prior': 'pageup',
                    'next': 'pagedown',
                    'space': 'space',
                    'return': 'enter',
                    'kp_enter': 'enter',
                    'escape': 'escape',
                    'backspace': 'backspace',
                    'delete': 'delete',
                    'insert': 'insert',
                    'home': 'home',
                    'end': 'end',
                    'left': 'left',
                    'up': 'up',
                    'right': 'right',
                    'down': 'down',
                    'tab': 'tab'
                }
                key_name = key_map.get(keysym, keysym)
                
                parts = mods + [key_name]
                var.set('+'.join(parts))
                original_val[0] = var.get()
                
            return 'break'

        entry.bind('<FocusIn>', on_focus_in)
        entry.bind('<FocusOut>', on_focus_out)
        entry.bind('<KeyPress>', on_key_press)
