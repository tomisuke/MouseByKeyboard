"""Regression checks for image search; no keyboard hooks or clicks."""
import random
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw
from config import Config
from scanner import Scanner, _suppress_overlapping_rects


def reference_suppression(rects):
    result = []
    for r in sorted(rects, key=lambda r: (r[2]-r[0])*(r[3]-r[1]), reverse=True):
        area = (r[2]-r[0])*(r[3]-r[1])
        for f in result:
            intersection = (max(0, min(r[2], f[2])-max(r[0], f[0])) *
                            max(0, min(r[3], f[3])-max(r[1], f[1])))
            union = area + (f[2]-f[0])*(f[3]-f[1]) - intersection
            if intersection / union > 0.4:
                break
        else:
            result.append(r)
    return result


class ImageSearchTests(unittest.TestCase):
    def test_spatial_index_preserves_results_and_order(self):
        rng = random.Random(12)
        rects = []
        for _ in range(1500):
            x, y = rng.randrange(-600, 600), rng.randrange(-400, 400)
            rects.append((x, y, x+rng.randrange(6, 301), y+rng.randrange(6, 101)))
        rects += rects[:50]  # identical candidates
        rects += [(-96, -96, 0, 0), (0, 0, 96, 96), (12, 12, 24, 24)]
        self.assertEqual(_suppress_overlapping_rects(rects), reference_suppression(rects))

    def test_active_capture_clips_to_desktop_and_keeps_negative_origin(self):
        scanner = Scanner(Config())
        image = Image.new('RGB', (300, 240), 'black')
        ImageDraw.Draw(image).rectangle((60, 60, 180, 120), outline='white', width=3)
        with patch.object(scanner, '_get_screen_rect', return_value=(-300, -240, 900, 600)), \
             patch('win32gui.GetForegroundWindow', return_value=123), \
             patch('win32gui.GetWindowRect', return_value=(-400, -300, 0, 0)), \
             patch('PIL.ImageGrab.grab', return_value=image) as grab:
            results = scanner.scan_active_image()
        grab.assert_called_once_with(bbox=(-300, -240, 0, 0), all_screens=True)
        self.assertTrue(results)
        for rect, _ in results:
            self.assertTrue(-300 <= rect.left < rect.right <= 0)
            self.assertTrue(-240 <= rect.top < rect.bottom <= 0)

    def test_offscreen_capture_is_empty(self):
        scanner = Scanner(Config())
        with patch.object(scanner, '_get_screen_rect', return_value=(0, 0, 900, 600)), \
             patch('PIL.ImageGrab.grab') as grab:
            self.assertEqual(scanner.scan_all_image(bounds=(-300, 0, -100, 100)), [])
        grab.assert_not_called()


if __name__ == '__main__':
    unittest.main()
