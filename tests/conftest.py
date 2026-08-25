import sys
from pathlib import Path

# Add src and root directories to sys.path for all pytest sessions
root_dir = Path(__file__).resolve().parent.parent
src_dir = root_dir / "src"

for p in [str(src_dir), str(root_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)
