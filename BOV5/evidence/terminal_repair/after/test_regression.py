import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
result = subprocess.run([sys.executable, str(root / "game/main.py")], input="1\n1\n", text=True, capture_output=True, timeout=8)
assert result.returncode == 0, result.stderr
assert result.stdout.strip().splitlines()[-1] == "SCORE:2 STATUS:ONGOING", result.stdout
