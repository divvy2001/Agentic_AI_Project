import json
from langchain_core.tools import tool
from coder_agent_adhoc.contracts import assets
from coder_agent_adhoc.run_context import current_plan


@tool
def list_assets() -> str:
    """List the validated asset files for THIS Plan (id, path, type, size checks passed).

    Use only these paths in game code. strategy=none/procedural may return [] - draw
    shapes procedurally then. Never reference other files under game/assets."""
    return json.dumps(assets(current_plan()),ensure_ascii=False)
