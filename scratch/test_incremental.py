import sys
sys.path.append('.')

import tkinter as tk
from overlay import HintOverlay
from config import Config

class DummyRect:
    def __init__(self, l, t, r, b):
        self.left = l
        self.top = t
        self.right = r
        self.bottom = b
    def width(self):
        return self.right - self.left
    def height(self):
        return self.bottom - self.top

def test():
    cfg = Config()
    root = tk.Tk()
    root.withdraw()
    
    overlay = HintOverlay(root, cfg, on_key=lambda x: print(x), on_special=lambda x: print(x))
    
    rects = [DummyRect(100, 100, 150, 120), DummyRect(200, 200, 250, 220)]
    elements = [(r, None) for r in rects]
    tags = ["aa", "ab"]
    
    print("Testing show (1st partial)...")
    overlay.show(elements, tags, scan_finished=False)
    
    print("Testing show (2nd partial, incremental)...")
    rects.append(DummyRect(300, 300, 350, 320))
    elements = [(r, None) for r in rects]
    tags.append("ac")
    overlay.show(elements, tags, scan_finished=False)
    
    print("Testing show (done, finalize)...")
    overlay.show(elements, tags, scan_finished=True)
    
    print("Testing hide...")
    overlay.hide()
    
    print("Success!")
    root.destroy()

if __name__ == '__main__':
    test()
