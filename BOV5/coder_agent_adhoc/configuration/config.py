import os
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')


def _int(name, default):
    value = os.getenv(name)
    return int(value) if value else default


def _float_or_none(name):
    value = os.getenv(name)
    return float(value) if value else None


CODER_OPENROUTER_API_KEY = os.getenv('CODER_OPENROUTER_API_KEY', '')
OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'
PLAN_FILE = ROOT / 'plans/coder_plan.json'
ASSET_MANIFEST_FILE = ROOT / 'plans/asset_manifest.json'
PLAY_MANUAL_FILE = ROOT / 'plans/play_manual.json'
TRACE_FILE = ROOT / 'traces/coder_attempts.jsonl'
GAME_DIR = ROOT / 'game'
PROMPT_FILE = Path(__file__).resolve().parents[1] / 'resources/prompt_coder.txt'
AGENT_MODEL = os.getenv('CODER_MODEL', 'google/gemini-2.5-flash')
TEMPERATURE = 0
# Functionality-first working defaults. Baseline 01 remains frozen; experiments
# must explicitly record their profile instead of assuming equal old/new budgets.
CODER_MAX_STEPS = _int('CODER_MAX_STEPS', 40)
COMMAND_TIMEOUT = _int('CODER_COMMAND_TIMEOUT', 120)
OUTPUT_LIMIT = _int('CODER_OUTPUT_LIMIT', 32768)
CODER_MAX_SECONDS = _int('CODER_MAX_SECONDS', 1800)
CODER_MAX_TOKENS = _int('CODER_MAX_TOKENS', 450000)  # cumulative input+output tokens
CODER_MODEL_MAX_OUTPUT_TOKENS = _int('CODER_MODEL_MAX_OUTPUT_TOKENS', 16384)
CODER_MAX_COST_USD = _float_or_none('CODER_MAX_COST_USD')  # unknown provider cost stays unknown
CODER_STAGNATION_LIMIT = _int('CODER_STAGNATION_LIMIT', 3)
# Older model turns are compacted; this many latest turns are sent verbatim.
CODER_RECENT_TURNS = _int('CODER_RECENT_TURNS', 2)
CODER_PROVIDER_RETRIES_PER_FAILURE = _int('CODER_PROVIDER_RETRIES_PER_FAILURE', 1)
CODER_PROVIDER_RETRIES_TOTAL = _int('CODER_PROVIDER_RETRIES_TOTAL', 3)
CODER_MODEL_TIMEOUT = _int('CODER_MODEL_TIMEOUT', 120)
CODER_PHASE_CHECK_INTERVAL = _int('CODER_PHASE_CHECK_INTERVAL', 2)
CODER_REPEATED_TOOL_FAILURE_LIMIT = _int('CODER_REPEATED_TOOL_FAILURE_LIMIT', 5)
