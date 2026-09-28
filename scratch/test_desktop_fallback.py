import sys
import os

# Ensure the parent directory is in the import path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("Verifying import syntax...")
try:
    import scanner
    import app
    from config import Config
    print("Imports OK.")
except Exception as e:
    print(f"Import failed: {e}")
    sys.exit(1)

print("Verifying _is_invalid_active_window in scanner.py...")
try:
    # 0 or None should be invalid
    assert scanner._is_invalid_active_window(0) == True
    assert scanner._is_invalid_active_window(None) == True
    
    # We can mock GetClassName by patching or by testing a dummy case if we can't patch easily.
    # Let's test with patch or mock class class-methods or by directly testing it with a win32gui handle if available.
    # To be safe and independent of GUI, we can temporarily monkeypatch win32gui.GetClassName
    import win32gui
    orig_get_classname = win32gui.GetClassName
    
    # Test Progman
    win32gui.GetClassName = lambda h: "Progman"
    assert scanner._is_invalid_active_window(999) == True
    
    # Test WorkerW
    win32gui.GetClassName = lambda h: "WorkerW"
    assert scanner._is_invalid_active_window(999) == True
    
    # Test Normal Window (e.g. CabinetWClass)
    win32gui.GetClassName = lambda h: "CabinetWClass"
    assert scanner._is_invalid_active_window(999) == False
    
    # Restore
    win32gui.GetClassName = orig_get_classname
    print("scanner._is_invalid_active_window verification passed.")
except Exception as e:
    print(f"scanner._is_invalid_active_window verification failed: {e}")
    sys.exit(1)

print("Verifying _is_invalid_active_window in app.py...")
try:
    config = Config()
    import tkinter as tk
    root = tk.Tk()
    # Mock some App initialization requirements
    class MockApp(app.App):
        def __init__(self, root, config):
            self._root = root
            self.config = config
            # Stub out initialization that depends on GUI or registers hotkeys
            pass
            
    inst = MockApp.__new__(MockApp)
    
    import win32gui
    orig_get_classname = win32gui.GetClassName
    
    # Test Progman
    win32gui.GetClassName = lambda h: "Progman"
    assert inst._is_invalid_active_window(999) == True
    
    # Test WorkerW
    win32gui.GetClassName = lambda h: "WorkerW"
    assert inst._is_invalid_active_window(999) == True
    
    # Test Normal
    win32gui.GetClassName = lambda h: "CabinetWClass"
    assert inst._is_invalid_active_window(999) == False
    
    # Restore
    win32gui.GetClassName = orig_get_classname
    print("app.App._is_invalid_active_window verification passed.")
except Exception as e:
    print(f"app.App._is_invalid_active_window verification failed: {e}")
    sys.exit(1)

print("All fallback logic verification tests passed successfully!")
