---
name: keynavigator-architecture
description: KeyNavigatorのアーキテクチャ図と各モジュール（app.py, hotkey_manager.py, keyboard_hook.py, scanner.py, hint_manager.py, overlay.py, clicker.py, tray.py, settings_window.py）の責務。ハイブリッドスキャン・インクリメンタル表示・マルチモニタ対応を含む。コード変更やバグ調査でどのファイルを見るべきか判断する際に使用する。
---

# KeyNavigator アーキテクチャ

```
main.py            エントリポイント。DPI設定 → App起動 → トレイ起動 → mainloop
 └ app.py          メインコントローラ（キューイベントループ、状態管理、インクリメンタル描画制御）
     ├ hotkey_manager.py  Win32 RegisterHotKey をバックグラウンドスレッドで監視（グローバルホットキー）
     ├ keyboard_hook.py   WH_KEYBOARD_LL/WH_MOUSE_LL 低レベルフック（ヒントモード中の入力捕捉）
     ├ scanner.py         UIA + OCR + CV のハイブリッド要素スキャン（並列・インクリメンタル対応）
     ├ hint_manager.py    タグ生成 + ヒント入力状態（HintState）
     ├ overlay.py         透過 tkinter オーバーレイにタグ・インジケータを描画
     ├ clicker.py         クリック実行（UIA Invoke → 物理クリックfallback、プロセス別強制切替）
     ├ tray.py            pystray トレイアイコン
     └ settings_window.py 設定GUI
```

## 主要モジュールの責務

- **app.py** — メインスレッドで `queue` をポーリングするイベントループ
  (`_poll` → `root.after(10)`)。スレッド安全に各イベントを `_dispatch`。
  状態は `idle` / `scanning` / `hint` の3モード。
  `_start_scan()` で UIA スレッドと Image（OCR/CV）スレッドを並行実行し、
  `_accumulated_uia` / `_accumulated_image` に部分結果を蓄積しながら
  `_on_scan_partial_uia` / `_on_scan_partial_image` で逐次オーバーレイ更新
  （インクリメンタル表示）。`_decide_default_method()` が起動 300ms 以内に
  UIA が要素を検出したかどうかで既定の検索方式（`'uia'` / `'image'`）を決定。
  `Tab` キー（`_toggle_search_method()`）でヒントモード中に UIA/Image を
  手動切替可能。ヒント中に前面ウィンドウが変わったら `_poll()` が検知して
  `_cancel()` する。

- **hotkey_manager.py** — `HotkeyManager(threading.Thread)`。
  Win32 メッセージポンプ（`PeekMessageW`）を回し、`WM_HOTKEY` 受信時に
  イベントをキューへ送る。`keyboard` ライブラリ非依存でキー状態を汚さない。
  グローバル起動ホットキー（スキャン開始）専用。

- **keyboard_hook.py** — ヒントモード中の入力捕捉を担当。旧来の
  `keyboard.hook(suppress=True)` 方式を置き換え済み。
  - `SelectiveKeyboardHook`（`WH_KEYBOARD_LL`）: ヒント文字・Esc・Backspace・
    プレフィックスキーのみ選択的に suppress。Ctrl/Alt/Win 併用時は無条件で
    パススルーするため AutoHotkey 等の外部スクリプトを阻害しない。
    `ToUnicode()` でキーボードレイアウト依存の文字変換を行う。
  - `MouseHook`（`WH_MOUSE_LL`）: 左/右/中クリックを検知してコールバックする
    のみで、イベント自体はブロックしない（ヒントモード中のクリックでの
    自動キャンセルに使用）。

- **scanner.py** — ハイブリッドスキャンの中核。`Scanner.__init__` で
  `ProcessPoolExecutor`（`max_workers=config.max_scan_windows`）を常駐初期化
  しウォームアップで起動ラグを削減。
  - `scan_hybrid(active_only)` — UIA と画像認識（OCR+CV）を別スレッドで並列
    実行し、結果をキュー経由で逐次受け取る。中心点距離 3px 以下、または
    OCR 領域の重複率 50% 超で UIA 要素と重複する画像要素を除外。
  - UIA 探索は `CLICKABLE_TYPE_IDS` に該当する要素をツリー探索。
    `_scan_hwnd_process_path()` で `ProcessPoolExecutor` によりサブツリーを
    パス指定で分割スキャン（最大8分割、`parallel_sub_scan` 設定で単一
    ウィンドウ内も分割可）。
  - `_scan_ocr()` — `winrt.windows.media.ocr.OcrEngine` で非同期 OCR。
    行間ギャップが行高×1.3以下かつ垂直重複がある単語を同一グループに結合。
  - `_scan_cv()` — Pillow ベースのエッジ検出→二値化（閾値15）→BFS 輪郭抽出。
    IoU 0.4 超で重複除外、サイズ制限（幅6〜600px・高さ6〜120px）。
  - `_grab_screen_gdi()` — GDI API でモニタ別に `CreateDCW`+`BitBlt` して
    仮想画面全体を1枚に合成（マルチモニタキャプチャ）。
  - `_worker_init_dpi_aware()` — `ProcessPoolExecutor` の各ワーカープロセス
    起動時に `SetProcessDpiAwareness(2)` を設定し座標ズレを防止。

- **overlay.py** — `Toplevel` + `transparentcolor='black'` でクリックスルー風の
  透過ウィンドウ。バッジは明るい黄色背景・濃い枠線・白縁取りテキストで高視認性。
  入力に応じて `update_filter` で非該当タグを透明化。
  - インジケータ表示: `show_search_method_indicator(method)`
    （UIA/Image/Hybrid を色分け表示）と `show_mode_indicator(mode)`
    （Double/Right/Middle クリックモードを色分け表示）。表示対象・位置は
    `config.indicator_display` / `indicator_position` に従う。
  - 部分描画対応: `needs_full_redraw` が false のときは既存バッジを維持し
    新規要素のみ追加描画（インクリメンタル表示のちらつき防止）。
  - `scan_finished` フラグでバッジ枠線の濃さを変更（スキャン中は薄く、
    完了後は濃く）。

- **hint_manager.py** — `generate_tags()` と `HintState`。
  `input_char()` は `'invalid'` / `'filter'` / `'match'` を返す。
  タグは事前に一括生成され、インクリメンタル表示・方式切替でも変わらない。

- **clicker.py** — ①UIA `InvokePattern.Invoke()` → ②`element.Click()` →
  ③物理クリック（`win32api`）の順にフォールバック。
  `config.force_physical_click` が true、または対象要素の所属プロセス名が
  `_FORCE_PHYSICAL_PROCESSES`（例: `code.exe`）に該当する場合は上記を
  スキップして最初から物理クリックを強制する（`_get_process_name_from_hwnd()`
  で `QueryFullProcessImageNameW` によりプロセス名を取得）。
