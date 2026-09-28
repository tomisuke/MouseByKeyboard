import os
import sys
import shutil
import subprocess
import time

def kill_process():
    print("[1/5] 既存の KeyNavigator.exe プロセスを終了しています...")
    try:
        # taskkill のフルパスを試す
        system_root = os.environ.get('SystemRoot', 'C:\\Windows')
        taskkill_path = os.path.join(system_root, 'System32', 'taskkill.exe')
        if os.path.exists(taskkill_path):
            subprocess.run([taskkill_path, "/f", "/im", "KeyNavigator.exe"], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            # powershellのStop-Processを試す
            subprocess.run(["powershell", "-Command", "Stop-Process -Name KeyNavigator -Force"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # プロセスが終了するまで少し待つ
        time.sleep(1)
    except Exception as e:
        print(f"警告: プロセス終了中にエラーが発生しました: {e}")

def run_build():
    print("[2/5] PyInstaller を使用してビルドを実行中...")
    
    # winrt の関連パッケージがインポートから漏れないように hidden-import を指定
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        "--name", "KeyNavigator",
        "--hidden-import", "winrt.windows.media.ocr",
        "--hidden-import", "winrt.windows.graphics.imaging",
        "--hidden-import", "winrt.windows.storage.streams",
        "--hidden-import", "winrt.windows.foundation",
        "--hidden-import", "winrt.windows.foundation.collections",
        "--hidden-import", "winrt.windows.globalization",
        "main.py"
    ]
    
    print(f"実行コマンド: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("エラー: ビルドに失敗しました。")
        sys.exit(1)
    print("ビルドが成功しました。")

def deploy_exe():
    print("[3/5] 実行ファイルを配置しています...")
    dist_path = os.path.join("dist", "KeyNavigator.exe")
    dest_path = "KeyNavigator.exe"
    
    if not os.path.exists(dist_path):
        print(f"エラー: ビルド成果物が見つかりません ({dist_path})")
        sys.exit(1)
        
    try:
        shutil.copy2(dist_path, dest_path)
        print(f"KeyNavigator.exe をプロジェクトルートに配置しました。")
    except Exception as e:
        print(f"エラー: 実行ファイルのコピーに失敗しました: {e}")
        sys.exit(1)

def register_startup():
    print("[4/5] スタートアップに登録しています...")
    try:
        import win32com.client
        
        startup_dir = os.path.join(
            os.environ["APPDATA"], 
            "Microsoft", "Windows", "Start Menu", "Programs", "Startup"
        )
        shortcut_path = os.path.join(startup_dir, "KeyNavigator.lnk")
        exe_path = os.path.abspath("KeyNavigator.exe")
        
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.TargetPath = exe_path
        shortcut.WorkingDirectory = os.path.dirname(exe_path)
        shortcut.Description = "KeyNavigator - Keyboard navigation utility"
        shortcut.save()
        print(f"スタートアップショートカットを作成しました: {shortcut_path}")
    except Exception as e:
        print(f"エラー: スタートアップ登録に失敗しました: {e}")
        # スタートアップ登録の失敗はビルド自体の致命的エラーとはしない
        
def start_app():
    print("[5/5] 最新の KeyNavigator.exe を起動しています...")
    try:
        exe_path = os.path.abspath("KeyNavigator.exe")
        os.startfile(exe_path)
        print("KeyNavigator.exe を起動しました（バックグラウンド常駐）。")
    except Exception as e:
        print(f"エラー: 起動に失敗しました: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("=== KeyNavigator 自動ビルド & 常駐化スクリプト ===")
    kill_process()
    run_build()
    deploy_exe()
    register_startup()
    start_app()
    print("=== すべての処理が完了しました ===")
