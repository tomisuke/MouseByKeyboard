import sys
import os

# Ensure the parent directory is in the import path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    print("Importing scanner...")
    import scanner
    print("scanner imported successfully.")
except Exception as e:
    print(f"Error importing scanner: {e}")
    sys.exit(1)

try:
    print("Importing app...")
    import app
    print("app imported successfully.")
except Exception as e:
    print(f"Error importing app: {e}")
    sys.exit(1)

print("Syntax and imports are verified successfully.")
