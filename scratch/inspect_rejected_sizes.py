import sys
import os
import win32gui
import comtypes
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

comtypes.CoInitialize()
try:
    screen_rect = scanner._get_screen_rect()
    try:
        screen = ImageGrab.grab(bbox=screen_rect)
    except Exception:
        screen = ImageGrab.grab()
        
    width, height = screen.size
    scale = 3
    small = screen.resize((width // scale, height // scale), ImageOps.Image.Resampling.BILINEAR if hasattr(ImageOps, 'Image') else 2)

    gray = ImageOps.grayscale(small)
    edges = gray.filter(ImageFilter.FIND_EDGES)
    binary = edges.point(lambda p: 255 if p > 30 else 0)

    pixels = binary.load()
    w, h = binary.size

    visited = set()
    rects = []

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
                
                rects.append(((rx1, ry1, rx2, ry2), rw, rh))
                
                # Boundary visited marking
                for vy in range(min_y, max_y + 1):
                    visited.add((min_x, vy))
                    visited.add((max_x, vy))
                for vx in range(min_x, max_x + 1):
                    visited.add((vx, min_y))
                    visited.add((vx, max_y))

    # Perform IoU-based NMS
    filtered_rects = []
    rects.sort(key=lambda r: r[1]*r[2], reverse=True)
    for r, rw, rh in rects:
        r_area = rw * rh
        contained = False
        for fr, frw, frh in filtered_rects:
            overlap_x = max(0, min(r[2], fr[2]) - max(r[0], fr[0]))
            overlap_y = max(0, min(r[3], fr[3]) - max(r[1], fr[1]))
            overlap_area = overlap_x * overlap_y
            
            union_area = r_area + frw*frh - overlap_area
            iou = overlap_area / union_area if union_area > 0 else 0
            
            if iou > 0.4:
                contained = True
                break
                
        if not contained:
            filtered_rects.append((r, rw, rh))

    # Group elements inside the active window on the far left side
    wl, wt, wr, wb = win_rect
    left_elements = []

    for r, rw, rh in filtered_rects:
        cx = (r[0] + r[2]) // 2
        cy = (r[1] + r[3]) // 2
        if wl <= cx <= wr and wt <= cy <= wb:
            if r[0] < wl + 60:
                left_elements.append((r, rw, rh))

    print(f"\nAll left side elements inside active window (NO size filter): {len(left_elements)}")
    left_elements.sort(key=lambda item: item[0][1])
    for idx, item in enumerate(left_elements):
        r, rw, rh = item
        accepted = (12 <= rw <= 300 and 10 <= rh <= 100)
        status = "ACCEPTED" if accepted else "REJECTED"
        print(f"  [{idx}] Rect={r}, WxH={rw}x{rh} -> Status: {status}")
        
finally:
    comtypes.CoUninitialize()
