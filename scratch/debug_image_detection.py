import time
from PIL import Image, ImageFilter, ImageOps, ImageGrab

def detect_visual_elements():
    t0 = time.time()
    # Grab primary monitor screen
    screen = ImageGrab.grab()
    grab_time = (time.time() - t0) * 1000
    
    t0 = time.time()
    width, height = screen.size
    
    # Resize to speed up processing (factor of 3)
    scale = 3
    small = screen.resize((width // scale, height // scale), Image.Resampling.BILINEAR)
    resize_time = (time.time() - t0) * 1000
    
    t0 = time.time()
    # Convert to grayscale and find edges
    gray = ImageOps.grayscale(small)
    edges = gray.filter(ImageFilter.FIND_EDGES)
    
    # Binarize edges
    threshold = 30
    binary = edges.point(lambda p: 255 if p > threshold else 0)
    img_processing_time = (time.time() - t0) * 1000
    
    t0 = time.time()
    pixels = binary.load()
    w, h = binary.size
    
    visited = set()
    rects = []
    
    # Scan every 2 pixels to speed up
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            if pixels[x, y] == 255 and (x, y) not in visited:
                # BFS to find connected component bounds
                min_x, max_x = x, x
                min_y, max_y = y, y
                
                queue = [(x, y)]
                visited.add((x, y))
                count = 0
                
                while queue and count < 500:  # limit component size
                    cx, cy = queue.pop(0)
                    count += 1
                    
                    min_x = min(min_x, cx)
                    max_x = max(max_x, cx)
                    min_y = min(min_y, cy)
                    max_y = max(max_y, cy)
                    
                    # 4-connectivity
                    for nx, ny in [(cx+2, cy), (cx-2, cy), (cx, cy+2), (cx, cy-2)]:
                        if 0 <= nx < w and 0 <= ny < h:
                            if pixels[nx, ny] == 255 and (nx, ny) not in visited:
                                visited.add((nx, ny))
                                queue.append((nx, ny))
                
                # Check component dimensions
                rw = (max_x - min_x) * scale
                rh = (max_y - min_y) * scale
                
                # Reject too small, too large or weird aspect ratio components
                if 12 <= rw <= 300 and 10 <= rh <= 100:
                    rx1 = min_x * scale
                    ry1 = min_y * scale
                    rx2 = max_x * scale
                    ry2 = max_y * scale
                    rects.append((rx1, ry1, rx2, ry2))
                    
                    # Fill visited for the bounding box in small image to avoid redundant checks
                    for vy in range(min_y, max_y + 1):
                        for vx in range(min_x, max_x + 1):
                            visited.add((vx, vy))

    # Remove overlapping / nested rectangles (Non-Maximum Suppression-like)
    filtered_rects = []
    rects.sort(key=lambda r: (r[2]-r[0])*(r[3]-r[1]), reverse=True) # Sort by area descending
    
    for r in rects:
        # Check if this rect is already inside a larger rect
        r_area = (r[2]-r[0]) * (r[3]-r[1])
        contained = False
        for fr in filtered_rects:
            # Check overlap percentage
            overlap_x = max(0, min(r[2], fr[2]) - max(r[0], fr[0]))
            overlap_y = max(0, min(r[3], fr[3]) - max(r[1], fr[1]))
            overlap_area = overlap_x * overlap_y
            if overlap_area > 0.5 * r_area:
                contained = True
                break
        if not contained:
            filtered_rects.append(r)
            
    search_time = (time.time() - t0) * 1000
    
    print(f"Grab: {grab_time:.1f}ms | Resize: {resize_time:.1f}ms | Process: {img_processing_time:.1f}ms | Scan/Filter: {search_time:.1f}ms")
    print(f"Found {len(rects)} raw rects, {len(filtered_rects)} filtered rects")
    
    # Print some coordinates
    for i, r in enumerate(filtered_rects[:10]):
        print(f"  Rect {i}: {r} (size: {r[2]-r[0]}x{r[3]-r[1]})")

if __name__ == '__main__':
    detect_visual_elements()
