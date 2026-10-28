import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))  # project root
from config import (
    PLANNER_OPENROUTER_API_KEY as OPENROUTER_API_KEY,
    ASSET_OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL, GODOT_BINARY, ROOT,
)

LOCAL = Path(__file__).parent.parent
PROMPT_PATH     = LOCAL / "resources" / "planner_prompt.txt"
SCHEMA_PATH     = LOCAL / "resources" / "plan_schema.json"
TRACE_FILE      = ROOT / "traces" / "planner_attempts.jsonl"
CODER_PLAN_FILE = ROOT / "plans" / "coder_plan.json"
PLAN_FILE       = ROOT / "plans" / "plan.json"
GAME_ASSETS_DIR = ROOT / "game" / "assets"

MAX_ATTEMPTS = 2
MODEL = "google/gemini-2.5-flash"
PRICE_PER_1M_INPUT = 0.30
PRICE_PER_1M_OUTPUT = 2.50
TEMPERATURE = 0
MAX_TOKENS = 8000
LIBRARIES = ["pygame", "numpy"]