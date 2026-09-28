import sys
import os
import tkinter as tk

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from settings_window import SettingsWindow
from config import Config

def main():
    root = tk.Tk()
    root.withdraw()
    
    config = Config.load()
    
    def on_save(new_config):
        print("Config saved:")
        print(f"  hotkey_all: {new_config.hotkey_all}")
        print(f"  hotkey_active: {new_config.hotkey_active}")
        print(f"  font_size: {new_config.font_size}")
        root.quit()
        
    app = SettingsWindow(root, config, on_save)
    app._win.protocol("WM_DELETE_WINDOW", lambda: root.quit())
    
    root.mainloop()

if __name__ == '__main__':
    main()
