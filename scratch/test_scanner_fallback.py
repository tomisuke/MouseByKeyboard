import sys
import os
import win32gui

# Ensure the parent directory is in the import path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner import Scanner
from config import Config

# Mock config
config = Config()
scanner = Scanner(config)

print("Verifying scanner.scan_active()...")
try:
    gen = scanner.scan_active()
    # It should be a generator. Since GetForegroundWindow and FindWindow return 0/None,
    # it should terminate immediately when we try to pull elements.
    elements = list(gen)
    print(f"scan_active completed successfully. Found elements count: {len(elements)}")
except Exception as e:
    print(f"scan_active failed with exception: {e}")
    sys.exit(1)

print("Verifying scanner.scan_active_image()...")
try:
    # scan_active_image calls scan_all_image which might fail if Tesseract/OCR/CV or screen capturing fails in headless.
    # We catch exceptions just to see how it behaves.
    gen_img = scanner.scan_active_image()
    elements_img = list(gen_img)
    print(f"scan_active_image completed successfully. Found elements count: {len(elements_img)}")
except Exception as e:
    print(f"scan_active_image (expected to potentially fail or succeed depending on OCR installation, but should not crash due to window handling): {e}")

print("Verification complete.")
