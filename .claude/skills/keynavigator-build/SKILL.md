---
name: keynavigator-build
description: KeyNavigatorをPyInstallerでexe化し、Windowsスタートアップに常駐登録するビルドフロー（build.py, build.bat, KeyNavigator.spec）。exeが起動しない・winrt関連のImportErrorが出る等のビルド関連トラブル対応時に使用する。
---

# KeyNavigator ビルド・常駐化フロー

## 実行方法

```powershell
build.bat
```

内部で `python build.py` を呼ぶだけ。個別に検証したい場合は
`python build.py` を直接実行してもよい。

## build.py の処理順序（5ステップ）

1. **既存プロセス終了** — `taskkill /f /im KeyNavigator.exe`
   （フルパスが無ければ `powershell Stop-Process -Name KeyNavigator -Force`
   にフォールバック）。1秒待機してから次へ。
2. **PyInstaller ビルド** — `python -m PyInstaller --onefile --noconsole
   --name KeyNavigator main.py` に加え、下記の `--hidden-import` を必須で
   付与（PyInstaller は WinRT モジュールを自動検出できないため）。
   - `winrt.windows.media.ocr`
   - `winrt.windows.graphics.imaging`
   - `winrt.windows.storage.streams`
   - `winrt.windows.foundation`
   - `winrt.windows.foundation.collections`
   - `winrt.windows.globalization`
3. **exe 配置** — `dist/KeyNavigator.exe` をプロジェクトルートへコピー。
4. **スタートアップ登録** — `win32com.client` で
   `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\KeyNavigator.lnk`
   を作成（失敗してもビルド自体は失敗扱いにしない）。
5. **起動** — `os.startfile()` でルート直下の `KeyNavigator.exe` を起動。

`KeyNavigator.spec` にも同じ `hiddenimports` が定義済みなので、
`pyinstaller KeyNavigator.spec` で直接ビルドしても同等の結果になる。

## 注意点

- `--hidden-import` を1つでも落とすと、exe起動時（OCRスキャン実行時）に
  `ImportError` で落ちる。OCR/CV関連の依存を追加・変更したときは
  `KeyNavigator.spec` の `hiddenimports` と `build.py` の
  `--hidden-import` 一覧を両方更新すること（詳細は
  `/keynavigator-gotchas`）。
- ビルド前に常駐プロセスを終了させないと `dist/KeyNavigator.exe` の
  コピーがファイルロックで失敗するため、`kill_process()` を必ず先に通す。
- `console=False`（`--noconsole`）なので、ビルド後の exe は例外が起きても
  コンソールに出力されない。デバッグ時は `python main.py` で直接起動する
  （`/keynavigator-debug` 参照）か、`hook_debug.log` / `click_debug.log`
  等のログファイルを確認する。
