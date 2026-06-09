import sys
import os
import win32gui
from PIL import ImageGrab, ImageOps, ImageFilter

# Add workspace root to path
workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(workspace_root)

from scanner import Scanner

class DummyConfig:
    scan_timeout_ms = 3000

config = DummyConfig()
scanner = Scanner(config)

hwnd = 0
def cb(h, _):
    global hwnd
    title = win32gui.GetWindowText(h)
    if 'TickTick' in title or 'TickTick' in win32gui.GetClassName(h):
        hwnd = h
        return False
    return True

win32gui.EnumWindows(cb, None)
if not hwnd:
    hwnd = win32gui.GetForegroundWindow()

win_rect = win32gui.GetWindowRect(hwnd)
print(f"Target Window: Rect={win_rect}")

# Copy the core logic of scan_all_image, but print out rejected rectangles as well
screen_rect = scanner._get_screen_rect()
try:
    screen = ImageGrab.grab(bbox=screen_rect)
except Exception:
    screen = ImageGrab.grab()
    
width, height = screen.size
scale = 3
small = screen.resize((width // scale, height // scale), ImageOps.Image.Resampling.BILINEAR if hasattr(ImageOps, 'Image') else 2) # BILINEAR = 2

gray = ImageOps.grayscale(small)
edges = gray.filter(ImageFilter.FIND_EDGES)
binary = edges.point(lambda p: 255 if p > 30 else 0)

pixels = binary.load()
w, h = binary.size

visited = set()
rejected = []
accepted = []

for y in range(0, h, 2):
    for x in range(0, w, 2):
        if pixels[x, y] == 255 and (x, y) not in visited:
            min_x, max_x = x, x
            min_y, max_y = y, y
            
            queue = [(x, y)]
            visited.add((x, y))
            count = 0
            
            while queue and count < 500:
                cx, cy = queue.pop(0)
                count += 1
                
                min_x = min(min_x, cx)
                max_x = max(max_x, cx)
                min_y = min(min_y, cy)
                max_y = max(max_y, cy)
                
                for nx, ny in [(cx+2, cy), (cx-2, cy), (cx, cy+2), (cx, cy-2)]:
                    if 0 <= nx < w and 0 <= ny < h:
                        if pixels[nx, ny] == 255 and (nx, ny) not in visited:
                            visited.add((nx, ny))
                            queue.append((nx, ny))
            
            rw = (max_x - min_x) * scale
            rh = (max_y - min_y) * scale
            
            rx1 = screen_rect[0] + min_x * scale
            ry1 = screen_rect[1] + min_y * scale
            rx2 = screen_rect[0] + max_x * scale
            ry2 = screen_rect[1] + max_y * scale
            
            # Check left side
            if rx1 < win_rect[0] + 60:
                if 12 <= rw <= 300 and 10 <= rh <= 100:
                    accepted.append(((rx1, ry1, rx2, ry2), rw, rh))
                else:
                    rejected.append(((rx1, ry1, rx2, ry2), rw, rh))
                
                # Mark as visited
                for vy in range(min_y, max_y + 1):
                    for vx in range(min_x, max_x + 1):
                        visited.add((vx, vy))

print(f"\nAccepted Left Side Elements: {len(accepted)}")
for idx, item in enumerate(accepted):
    print(f"  [{idx}] Rect={item[0]}, WxH={item[1]}x{item[2]}")
    
print(f"\nRejected Left Side Elements: {len(rejected)}")
for idx, item in enumerate(rejected):
    print(f"  [{idx}] Rect={item[0]}, WxH={item[1]}x{item[2]} (Reason: size out of limits)")
