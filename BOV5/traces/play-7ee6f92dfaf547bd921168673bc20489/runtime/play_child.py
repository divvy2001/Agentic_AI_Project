"""Real play entry for Python games; no frame limit or injected input."""
from pathlib import Path
import runpy
import sys

root = Path.cwd().resolve()
entry = (root / sys.argv[1]).resolve()
if not entry.is_relative_to(root / 'game') or not entry.is_file():
    raise ValueError('invalid_play_entry')
sys.path[:0] = [str(entry.parent), str(root)]
runpy.run_path(str(entry), run_name='__main__')
