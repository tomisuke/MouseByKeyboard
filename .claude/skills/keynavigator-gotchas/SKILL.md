---
name: keynavigator-gotchas
description: KeyNavigator開発における重要な技術的注意点（DPI設定、スキャンタイムアウト、キーボード入力捕捉、オーバーレイ透過色、マルチモニタ、PyInstallerビルド）と既知の修正履歴・再発防止メモ。バグ修正や関連コード変更の前に確認する。
---

# KeyNavigator 重要な技術的注意点・既知の修正履歴

## 重要な技術的注意点

- **DPI**: `SetProcessDpiAwareness(2)`（Per-Monitor v2）を tkinter 初期化より
  前に実行。座標ズレ防止のため必須。`ProcessPoolExecutor` の各ワーカー
  プロセスでも `_worker_init_dpi_aware()` で同様に設定しないと、マルチ
  モニタ環境でサブプロセス側のスキャン座標がズレる。
- **スキャンタイムアウト**: `scan_timeout_ms` のデフォルトは `500`
  （旧: 2000）。インクリメンタル表示により部分結果を逐次描画するため、
  1ウィンドウあたりの探索を打ち切っても体感の取りこぼしが起きにくい設計に
  変更されている。並列サブスキャン（`parallel_sub_scan`）を有効にすると
  さらに短縮できる。全体を待たせたくない場合以外はデフォルトのまま変更
  しないこと。
- **キーボード入力捕捉**: ヒントモード中は `keyboard_hook.py` の
  `SelectiveKeyboardHook`（`WH_KEYBOARD_LL`）で対象キーのみ選択的に
  suppress する方式に変更済み（旧: `keyboard.hook(suppress=True)` で
  全キー捕捉）。Ctrl/Alt/Win 併用時は無条件パススルーするため他アプリの
  ショートカットを壊さない。フリーズ防止のため 30 秒の安全タイマーで
  自動キャンセル（`_HINT_SAFETY_TIMEOUT`）は継続。
- **オーバーレイの透過色**: 背景 `black` が透明になるため、バッジ背景に黒は
  使用不可。
- **マルチモニタキャプチャ**: `_grab_screen_gdi()` はモニタ単位で
  `CreateDCW`+`BitBlt` して仮想画面座標に合成する。単一の `GetDC(None)` で
  丸ごとキャプチャすると環境によって一部モニタが欠落するため避けること。
- **font_size のデフォルトは `8`** だが、overlay 描画時に最低14ptが保証
  される。config.py のデフォルト値だけを見て「小さすぎる」と判断しない。

## 既知の修正履歴（再発防止メモ）

- `keyboard.add_hotkey` はホットキー登録時に Shift/CapsLock 状態を汚染する
  ことがあるため、Win32 `RegisterHotKey` へ置き換え済み（グローバル起動
  ホットキー）。ヒントモード中の入力捕捉も同様の理由で `keyboard_hook.py`
  の低レベルフック方式へ置き換え済み。
- `setup.bat` は cmd の Shift-JIS 期待に合わせ ASCII のみで記述。`pip` は
  PATH 非依存の `python -m pip` を使用。
- オーバーレイによるマウス固まりは、クリックスルーではなくキーボード
  フォーカス + suppress フック方式で解決。
- VSCode（`code.exe`）ではUIAのシミュレートクリック（`InvokePattern.Invoke()`）が例外を投げずに無視されるため、プロセス名で判定し自動的に物理クリックに切り替えるロジックを `clicker.py` に追加（`_FORCE_PHYSICAL_PROCESSES`）。同じChromiumベースでもAntigravityIDEやVivaldiでは問題ないため、ウィンドウクラス名ではなくプロセス名で判定する。
- PyInstaller で `--onefile` ビルドすると `winrt.windows.media.ocr` 等の
  WinRT モジュールが自動検出されず起動時に ImportError となるため、
  `--hidden-import` で明示指定する必要がある（詳細は
  `/keynavigator-build`）。
