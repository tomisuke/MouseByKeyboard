---
name: keynavigator-spec
description: KeyNavigatorのコンセプト、依存ライブラリ、ホットキー/ヒントモードの操作仕様（UIA/Image/Hybrid検索方式の切替、インジケータ表示を含む）、タグ生成規則、config.pyの設定項目一覧。機能仕様の確認や設定値の変更、操作フローの実装時に使用する。
---

# KeyNavigator 操作仕様・設定

## 目的・コンセプト

- マウスに手を伸ばさず、ホームポジションのまま GUI を操作する。
- 全画面 or アクティブウィンドウの「押せる要素」を自動検出してタグ付け。
- UIA（UI Automation）・画像認識（OCR+CV）・ハイブリッドの3方式でスキャンし、
  結果をインクリメンタルに（見つかった順に）オーバーレイ表示。
- 左・右・ダブル・中央クリックをプレフィックスキーで切り替え可能。
- 常駐型。タスクトレイから設定・終了。

## 依存ライブラリ (`requirements.txt`)

| パッケージ | 用途 |
|-----------|------|
| `uiautomation` | Windows UI Automation による要素スキャン |
| `pystray` | システムトレイアイコン |
| `Pillow` | 画像スキャン（CV/エッジ検出）・トレイアイコン画像生成 |
| `pywin32` | Win32 API（ウィンドウ列挙・座標・クリック・GDIキャプチャ） |
| `winrt-Windows.Media.Ocr` 他 winrt-* 一式 | OCR による画面上テキスト要素の検出 |
| `pyinstaller` | 常駐用 exe のビルド（詳細は `/keynavigator-build`） |
| `keyboard` | requirements には残るが、ヒントモード中の入力捕捉は
  `keyboard_hook.py` の低レベルフックに置き換え済み（下記参照） |

> 注: グローバル起動ホットキーは Win32 `RegisterHotKey`、ヒントモード中の
> キー捕捉は `WH_KEYBOARD_LL`/`WH_MOUSE_LL` を直接使用するため、実質的に
> `keyboard` ライブラリの `hook`/`add_hotkey` には依存しない
> （CapsLock 等のキー状態汚染を防ぐため）。

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
| `Tab` | 検索方式を UIA ⇔ Image で手動切替（クリックモードは維持） |
| `;`（プレフィックス） | 次のクリックをダブルクリックに |
| `'`（プレフィックス） | 次のクリックを右クリックに |
| `,`（プレフィックス） | 次のクリックを中央クリックに |

プレフィックスはタグ文字入力前のみ有効。

### 検索方式とインジケータ

- 起動後 300ms 以内に UIA が要素を検出できれば `uia`、できなければ
  `image`（OCR+CV）を既定方式として自動採用する。
- 画面上部などに現在の検索方式（UI ELEMENT SEARCH / IMAGE SEARCH /
  HYBRID SEARCH）とクリックモード（DOUBLE/RIGHT/MIDDLE CLICK）を
  色分けインジケータで表示（`show_indicators` で on/off）。

### タグ生成規則

ホームrow優先の文字セット `fjdkslaghrueiwoqpvnmcxbt` から、
短いタグを優先して一意に割り当てる（1文字 → 2文字 …）。タグは事前に
一括生成され、インクリメンタル表示・検索方式の切替でも変化しない。

## 設定 (`config.py`)

`~/.keynamigator/config.json` に JSON 保存。存在しなければデフォルト値。

| 項目 | デフォルト | 説明 |
|------|-----------|------|
| `hotkey_all` | `ctrl+q` | 全画面スキャンのホットキー |
| `hotkey_active` | `ctrl+shift+q` | アクティブ画面スキャンのホットキー |
| `hint_chars` | `fjdkslaghrueiwoqpvnmcxbt` | タグに使う文字（優先順） |
| `font_size` | `8` | タグフォントサイズ（描画時に最低14ptを保証） |
| `prefix_double` | `;` | ダブルクリック切替キー |
| `prefix_right` | `'` | 右クリック切替キー |
| `prefix_middle` | `,` | 中央クリック切替キー |
| `scan_timeout_ms` | `500` | 1ウィンドウあたりのスキャン上限時間（インクリメンタル表示前提の短縮値） |
| `max_scan_windows` | `5` | `ProcessPoolExecutor` の並列ワーカー数上限 |
| `parallel_sub_scan` | `False` | 単一ウィンドウ内のサブツリーも並列分割スキャンするか |
| `force_physical_click` | `False` | 常に物理クリック（UIA Invoke を使わない）を強制するか |
| `show_indicators` | `True` | 検索方式・クリックモードのインジケータ表示 |
| `indicator_display` | `active_window` | インジケータを表示する画面（`active_window`/`primary`/`mouse`/`all`） |
| `indicator_position` | `top_center` | インジケータの表示位置（7パターン） |
