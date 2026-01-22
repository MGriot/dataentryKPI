import sys
from pathlib import Path

# Ensure the 'src' directory is in the Python path
project_root = Path(__file__).resolve().parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from src.main import main

if __name__ == "__main__":
    main()
