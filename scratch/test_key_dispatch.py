import sys
import os
import tkinter as tk

# Add workspace root to path
workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(workspace_root)

from app import App
from hint_manager import HintState
from config import Config

# Dummy tkinter root
root = tk.Tk()
root.withdraw() # Hide window

class DummyConfig:
    def __init__(self):
        self.hotkey_active = 'ctrl+shift+q'
        self.hotkey_all = 'ctrl+q'
        self.hint_chars = 'fjdkslaghrueiwoqpvnmcxbt'
        self.font_size = 14
        self.prefix_double = ';'
        self.prefix_right = "'"
        self.prefix_middle = ','
        self.scan_timeout_ms = 2000

config = DummyConfig()

# We need to bypass some initializations like HintOverlay since it creates TK widgets
# and might require active screen context. Let's subclass App and mock what is needed.
class MockApp(App):
    def __init__(self, root, config):
        self._root = root
        self.config = config
        self._mode = 'idle'
        self._state = None
        self._search_method = 'uia'
        self._last_active_only = False
        
        # Mock overlay
        class MockOverlay:
            def show_mode_indicator(self, mode):
                print(f"[MockOverlay] Mode indicator: {mode}")
            def update_filter(self, typed, visible, tags):
                print(f"[MockOverlay] Filter updated: typed='{typed}'")
        self._overlay = MockOverlay()

app = MockApp(root, config)
app._mode = app._MODE_HINT

# Set dummy elements and tags
elements = [(None, None)] * 5
tags = ['fj', 'jd', 'ks', 'la', 'gh']
app._state = HintState(elements, tags)

print("Testing prefix key ';'")
app._on_key_name(';')
print(f"Click mode after prefix ';': {app._state.click_mode}")

print("\nTesting backspace")
app._state.input_char('f')
print(f"Typed before backspace: {app._state.typed}")
app._on_key_name('backspace')
print(f"Typed after backspace: {app._state.typed}")

print("\nTesting tab (toggle search method)")
# Since _toggle_search_method calls _start_scan which calls threading.Thread, we should mock it or see if it executes.
# Let's mock _start_scan.
def mock_start_scan(active_only, force_method=None):
    print(f"[MockApp] _start_scan called with active_only={active_only}, force_method={force_method}")
    app._search_method = force_method

app._start_scan = mock_start_scan
app._on_key_name('tab')

print("\nAll tests completed without throwing NameError!")
