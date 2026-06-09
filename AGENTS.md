# AGENTS.md — KeyNavigator

キーボードだけでマウス操作を完結させる Windows 常駐ユーティリティ。
画面上のクリック可能な UI 要素をスキャンし、金色のヒントタグを重ねて表示、
タグ文字を入力するだけで任意の要素をクリックできる（Vimium / Vimperator 風の操作）。

## 目的・コンセプト

- マウスに手を伸ばさず、ホームポジションのまま GUI を操作する。
- 全画面 or アクティブウィンドウの「押せる要素」を自動検出してタグ付け。
- 左・右・ダブル・中央クリックをプレフィックスキーで切り替え可能。
- 常駐型。タスクトレイから設定・終了。

## 起動方法

```
python main.py
```

依存パッケージのインストール:

```
python -m pip install -r requirements.txt
```

## 依存ライブラリ (`requirements.txt`)

| パッケージ | 用途 |
|-----------|------|
| `uiautomation` | Windows UI Automation による要素スキャン |
| `pystray` | システムトレイアイコン |
| `Pillow` | トレイアイコン画像生成 |
| `pywin32` | Win32 API（ウィンドウ列挙・座標・クリック） |

> 注: ホットキーは Win32 `RegisterHotKey` を直接使用するため `keyboard`
> ライブラリには依存しない（CapsLock 等のキー状態汚染を防ぐため）。

## 操作仕様

### グローバルホットキー

| キー | 動作 |
|------|------|
| `Ctrl+Q` | 全画面（全ウィンドウ）スキャン |
| `Ctrl+Shift+Q` | アクティブウィンドウのみスキャン |

### ヒントモード中の入力

| キー | 動作 |
|------|------|
| タグ文字（例 `fj`） | 該当タグの要素をクリック。部分一致は絞り込み表示 |
| `Esc` | キャンセル |
| `Backspace` | 入力を1文字戻す |
| `;`（プレフィックス） | 次のクリックをダブルクリックに |
| `'`（プレフィックス） | 次のクリックを右クリックに |
| `,`（プレフィックス） | 次のクリックを中央クリックに |

プレフィックスはタグ文字入力前のみ有効。

### タグ生成規則

ホームrow優先の文字セット `fjdkslaghrueiwoqpvnmcxbt` から、
短いタグを優先して一意に割り当てる（1文字 → 2文字 …）。

## 設定 (`config.py`)

`~/.keynamigator/config.json` に JSON 保存。存在しなければデフォルト値。

| 項目 | デフォルト | 説明 |
|------|-----------|------|
| `hotkey_all` | `ctrl+q` | 全画面スキャンのホットキー |
| `hotkey_active` | `ctrl+shift+q` | アクティブ画面スキャンのホットキー |
| `hint_chars` | `fjdkslaghrueiwoqpvnmcxbt` | タグに使う文字（優先順） |
| `font_size` | `14` | タグフォントサイズ（最低14ptを保証） |
| `prefix_double` | `;` | ダブルクリック切替キー |
| `prefix_right` | `'` | 右クリック切替キー |
| `prefix_middle` | `,` | 中央クリック切替キー |
| `scan_timeout_ms` | `2000` | 1ウィンドウあたりのスキャン上限時間 |

## アーキテクチャ

```
main.py            エントリポイント。DPI設定 → App起動 → トレイ起動 → mainloop
 └ app.py          メインコントローラ（キューイベントループ、状態管理）
     ├ hotkey_manager.py  Win32 RegisterHotKey をバックグラウンドスレッドで監視
     ├ scanner.py         UI Automation で要素スキャン（並列対応）
     ├ hint_manager.py    タグ生成 + ヒント入力状態（HintState）
     ├ overlay.py         透過 tkinter オーバーレイにタグ描画
     ├ clicker.py         クリック実行（UIA Invoke → 物理クリックfallback）
     ├ tray.py            pystray トレイアイコン
     └ settings_window.py 設定GUI
```

### 主要モジュールの責務

- **app.py** — メインスレッドで `queue` をポーリングするイベントループ
  (`_poll` → `root.after(10)`)。スレッド安全に各イベントを `_dispatch`。
  状態は `idle` / `scanning` / `hint` の3モード。

- **hotkey_manager.py** — `HotkeyManager(threading.Thread)`。
  Win32 メッセージポンプ（`PeekMessageW`）を回し、`WM_HOTKEY` 受信時に
  イベントをキューへ送る。`keyboard` ライブラリ非依存でキー状態を汚さない。

- **scanner.py** — `CLICKABLE_TYPE_IDS`（Button, Edit, ListItem 等）に該当する
  要素を UIA でツリー探索。`scan_active()` は前面ウィンドウ、`scan_all()` は
  `EnumWindows` + `ThreadPoolExecutor`（8ワーカー）で並列スキャン。
  各スキャンスレッドで COM 初期化（`CoInitialize/CoUninitialize`）。

- **overlay.py** — `Toplevel` + `transparentcolor='black'` でクリックスルー風の
  透過ウィンドウ。バッジは明るい黄色背景・濃い枠線・白縁取りテキストで高視認性。
  入力に応じて `update_filter` で非該当タグを透明化。

- **hint_manager.py** — `generate_tags()` と `HintState`。
  `input_char()` は `'invalid'` / `'filter'` / `'match'` を返す。

- **clicker.py** — ①UIA `InvokePattern.Invoke()` → ②`element.Click()` →
  ③物理クリック（`win32api`）の順にフォールバック。

## 重要な技術的注意点

- **DPI**: `SetProcessDpiAwareness(2)`（Per-Monitor v2）を tkinter 初期化より
  前に実行。座標ズレ防止のため必須。
- **スキャンタイムアウト**: 一般的なウィンドウ（エクスプローラー等）のツリー
  探索は ~500-700ms かかるため、`scan_timeout_ms` は 2000ms 以上が必要。
- **キーボード入力捕捉**: ヒントモード中は `keyboard.hook(suppress=True)` で
  全キーを捕捉（フォーカスに依存せず確実）。フリーズ防止のため 30 秒の安全
  タイマーで自動キャンセル（`_HINT_SAFETY_TIMEOUT`）。
- **オーバーレイの透過色**: 背景 `black` が透明になるため、バッジ背景に黒は
  使用不可。

## 既知の修正履歴（再発防止メモ）

- `keyboard.add_hotkey` はホットキー登録時に Shift/CapsLock 状態を汚染する
  ことがあるため、Win32 `RegisterHotKey` へ置き換え済み。
- `setup.bat` は cmd の Shift-JIS 期待に合わせ ASCII のみで記述。`pip` は
  PATH 非依存の `python -m pip` を使用。
- オーバーレイによるマウス固まりは、クリックスルーではなくキーボード
  フォーカス + suppress フック方式で解決。

## デバッグ用ファイル

`debug_*.py`, `test_hotkey.py` は単体検証用スクリプト（本体動作には不要）。
