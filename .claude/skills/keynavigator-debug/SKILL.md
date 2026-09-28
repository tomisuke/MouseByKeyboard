---
name: keynavigator-debug
description: KeyNavigatorの動作確認・デバッグ用スクリプト（debug_*.py, test_hotkey.py）の使い方一覧。個別機能（スキャン、オーバーレイ、ホットキー等）の動作テストや不具合調査時に使用する。
---

# KeyNavigator 動作確認・デバッグ

`debug_*.py` および `test_hotkey.py` は本体（`main.py`）とは独立した単体検証用
スクリプト。機能ごとの切り出し確認に使う。

## 主な検証スクリプト

- `debug_scan.py` — 画面スキャンの基本動作テスト
- `debug_hybrid_scan.py` — UIA + 画像認識のハイブリッドスキャンのテスト
- `debug_incremental.py` — インクリメンタルスキャン（差分検出）のテスト
- `debug_multimonitor.py` — マルチモニタ環境でのスキャン・座標のテスト
- `debug_overlay.py` / `debug_overlay2.py` — オーバーレイ描画の単体テスト
- `debug_ocr.py` — OCR による要素検出のテスト
- `debug_claude.py` — Claude 連携機能のテスト
- `test_hotkey.py` — グローバルホットキー登録・検知のテスト

## 実行方法

```powershell
python debug_scan.py
```

各スクリプトは本体の状態管理・キューイベントループを経由しないため、
`app.py` の起動なしに対象モジュール（`scanner.py` / `overlay.py` 等）を
単体で確認できる。新しい検証用スクリプトを追加する際も `debug_*.py` の
命名規則に従う。
