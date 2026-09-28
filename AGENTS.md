# AGENTS.md — KeyNavigator

キーボードだけでマウス操作を完結させる Windows 常駐ユーティリティ。
画面上のクリック可能な UI 要素をスキャンし、金色のヒントタグを重ねて表示、
タグ文字を入力するだけで任意の要素をクリックできる（Vimium / Vimperator 風）。

起動: `python main.py`（依存導入: `python -m pip install -r requirements.txt`）

詳細は用途に応じて以下の Skill を参照:
- `/keynavigator-spec` — コンセプト、操作仕様、ホットキー、config.py設定項目
- `/keynavigator-architecture` — 全体構成図、各モジュールの責務
- `/keynavigator-gotchas` — 重要な技術的注意点、既知の修正履歴
- `/keynavigator-debug` — debug_*.py 等の動作確認スクリプト一覧
- `/keynavigator-build` — PyInstallerでのexe化・スタートアップ常駐化フロー
