import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
src = root / "src"

for p in (str(src), str(root)):
    if p not in sys.path:
        sys.path.insert(0, p)
