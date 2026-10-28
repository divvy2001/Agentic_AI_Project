from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

PLANNER_OPENROUTER_API_KEY = os.getenv("PLANNER_OPENROUTER_API_KEY")
ASSET_OPENROUTER_API_KEY = os.getenv("ASSET_OPENROUTER_API_KEY")
CODER_OPENROUTER_API_KEY = os.getenv("CODER_OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GODOT_BINARY = os.getenv("GODOT_BINARY", "")
ROOT = Path(__file__).parent