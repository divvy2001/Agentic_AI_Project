"""

Expected input (illustrative):
{
    "task_id": "asset_task_001",
    "framework": "pygame",  # terminal | pygame | godot
    "game_style": "pixel_art",
    "output_dir": "game/assets",
    "assets": [
        {
            "id": "player",
            "type": "sprite",
            "description": "Blue player character",
            "width": 32,
            "height": 32,
            "required": True
        }
    ]
}

"""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path
from typing import Any


SUPPORTED_FRAMEWORKS = {"terminal", "pygame", "godot"}

# Keep these lists permissive until the team agrees on the final input contract.
SUPPORTED_ASSET_TYPES = {
    "terminal": {"symbol_set", "character", "tile", "ui", "other"},
    "pygame": {"sprite", "spritesheet", "background", "texture", "icon", "font", "ui", "other"},
    "godot": {"sprite", "spritesheet", "background", "texture", "icon", "font", "ui", "other"},
}

DEFAULT_EXTENSIONS = {
    "terminal": {
        "symbol_set": ".json",
        "character": ".json",
        "tile": ".json",
        "ui": ".json",
        "other": ".json",
    },
    "pygame": {
        "sprite": ".png",
        "spritesheet": ".png",
        "background": ".png",
        "texture": ".png",
        "icon": ".png",
        "font": ".ttf",
        "ui": ".png",
        "other": ".dat",
    },
    "godot": {
        "sprite": ".png",
        "spritesheet": ".png",
        "background": ".png",
        "texture": ".png",
        "icon": ".png",
        "font": ".ttf",
        "ui": ".png",
        "other": ".dat",
    },
}


class PlanningError(ValueError):
    """Raised when an asset request cannot be planned safely."""


def _slug(value: str) -> str:
    """Convert a name into a filesystem-safe filename component."""
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip()).strip("_")
    return slug or "asset"


def _positive_int(value: Any, field: str, asset_id: str) -> int | None:
    """Validate an optional positive integer dimension."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PlanningError(
            f"Asset '{asset_id}': '{field}' must be a positive integer."
        )
    return value


def plan_assets(request: dict[str, Any]) -> dict[str, Any]:
    """
    Convert a raw request dictionary into a normalized plan.

    Returns:
        {
            "task_id": str,
            "framework": str,
            "game_style": str | None,
            "output_dir": str,
            "assets": [normalized asset dictionaries],
            "manifest": manifest skeleton
        }

    Notes:
    - `request["assets"]` must be a list of asset objects.
    - Asset `id` and `type` are required; description is optional.
    - Unknown extra request/asset fields are preserved to ease later integration.
    - Output paths are relative to the project root and point inside output_dir.
    """
    if not isinstance(request, dict):
        raise PlanningError("Request must be a JSON object/dictionary.")

    framework = str(request.get("framework", "")).strip().lower()
    if framework not in SUPPORTED_FRAMEWORKS:
        allowed = ", ".join(sorted(SUPPORTED_FRAMEWORKS))
        raise PlanningError(
            f"Unsupported framework '{framework}'. Expected one of: {allowed}."
        )

    raw_assets = request.get("assets")
    if not isinstance(raw_assets, list):
        raise PlanningError("Request field 'assets' must be a list.")

    task_id = str(request.get("task_id", "asset_task")).strip() or "asset_task"
    game_style = request.get("game_style")
    output_dir = str(request.get("output_dir", "game/assets")).strip()
    if not output_dir:
        output_dir = "game/assets"

    output_path = Path(output_dir)
    if output_path.is_absolute() or ".." in output_path.parts:
        raise PlanningError(
            "'output_dir' must be a relative path and must not contain '..'."
        )

    planned_assets: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    manifest_assets: list[dict[str, Any]] = []

    for index, raw_asset in enumerate(raw_assets):
        if not isinstance(raw_asset, dict):
            raise PlanningError(f"Asset at index {index} must be an object.")

        asset = deepcopy(raw_asset)
        raw_id = str(asset.get("id", "")).strip()
        asset_type = str(asset.get("type", "")).strip().lower()

        if not raw_id:
            raise PlanningError(f"Asset at index {index} is missing required field 'id'.")
        if not asset_type:
            raise PlanningError(f"Asset '{raw_id}' is missing required field 'type'.")

        asset_id = _slug(raw_id)
        if asset_id in seen_ids:
            raise PlanningError(
                f"Duplicate asset ID after filename normalization: '{asset_id}'."
            )
        seen_ids.add(asset_id)

        allowed_types = SUPPORTED_ASSET_TYPES[framework]
        if asset_type not in allowed_types:
            allowed = ", ".join(sorted(allowed_types))
            raise PlanningError(
                f"Asset '{raw_id}' has unsupported type '{asset_type}' for "
                f"{framework}. Supported types: {allowed}."
            )

        width = _positive_int(asset.get("width"), "width", raw_id)
        height = _positive_int(asset.get("height"), "height", raw_id)

        # A supplied filename is respected only if it is a simple filename.
        supplied_filename = asset.get("filename")
        if supplied_filename:
            filename_path = Path(str(supplied_filename))
            if filename_path.name != str(supplied_filename) or str(supplied_filename) in {".", ".."}:
                raise PlanningError(
                    f"Asset '{raw_id}': filename must be a simple filename, not a path."
                )
            filename = str(supplied_filename)
        else:
            extension = DEFAULT_EXTENSIONS[framework].get(asset_type, ".dat")
            filename = f"{asset_id}{extension}"

        relative_path = (output_path / filename).as_posix()

        normalized = {
            **asset,
            "id": asset_id,
            "type": asset_type,
            "description": str(asset.get("description", "")).strip(),
            "required": bool(asset.get("required", True)),
            "width": width,
            "height": height,
            "filename": filename,
            "path": relative_path,
            "framework": framework,
        }
        planned_assets.append(normalized)
        manifest_assets.append(
            {
                "id": asset_id,
                "type": asset_type,
                "path": relative_path,
                "format": Path(filename).suffix.lstrip(".").lower() or None,
                "width": width,
                "height": height,
                "required": normalized["required"],
                "generation_status": "planned",
                "validation_status": "pending",
                "errors": [],
            }
        )

    manifest = {
        "task_id": task_id,
        "framework": framework,
        "game_style": game_style,
        "output_dir": output_path.as_posix(),
        "assets": manifest_assets,
        "validation": {
            "passed": False,
            "status": "pending",
            "errors": [],
        },
    }

    return {
        "task_id": task_id,
        "framework": framework,
        "game_style": game_style,
        "output_dir": output_path.as_posix(),
        "assets": planned_assets,
        "manifest": manifest,
    }


def update_manifest(
    plan: dict[str, Any],
    generation_results: list[dict[str, Any]] | None = None,
    validation_results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Update the planner-created manifest with generator and validator results.

    Generator result entries should ideally contain `id`, `status`, and
    optionally `path`, `format`, `width`, `height`, and `error`.

    Validation results may contain `passed`, `errors`, and per-asset entries
    under `assets` (each with `id`, `passed`, and optionally `errors`).
    """
    manifest = deepcopy(plan.get("manifest", {}))
    manifest_by_id = {
        item["id"]: item for item in manifest.get("assets", [])
        if isinstance(item, dict) and item.get("id")
    }

    for result in generation_results or []:
        if not isinstance(result, dict):
            continue
        asset_id = result.get("id")
        if asset_id not in manifest_by_id:
            continue

        entry = manifest_by_id[asset_id]
        if result.get("path"):
            p = Path(str(result["path"]))
            if p.is_absolute() and "game" in p.parts:
                i = len(p.parts) - 1 - p.parts[::-1].index("game")
                p = Path(*p.parts[i:])
            entry["path"] = p.as_posix()
        for field in ("format", "width", "height"):
            if result.get(field) is not None:
                entry[field] = result[field]

        status = result.get("status", "generated")
        entry["generation_status"] = str(status)
        if result.get("error"):
            entry.setdefault("errors", []).append(str(result["error"]))

    validation_results = validation_results or {}
    validation_by_id = {
        item["id"]: item for item in validation_results.get("assets", [])
        if isinstance(item, dict) and item.get("id")
    }

    for asset_id, entry in manifest_by_id.items():
        validation_item = validation_by_id.get(asset_id)
        if validation_item is None:
            # If the validator only returns a global result, use it for assets
            # whose generation succeeded; do not mark ungenerated assets valid.
            if entry["generation_status"] in {"generated", "success", "valid"}:
                if "passed" in validation_results:
                    entry["validation_status"] = (
                        "passed" if validation_results["passed"] else "failed"
                    )
            continue

        passed = bool(validation_item.get("passed", False))
        entry["validation_status"] = "passed" if passed else "failed"
        errors = validation_item.get("errors", [])
        if isinstance(errors, str):
            errors = [errors]
        entry.setdefault("errors", []).extend(str(error) for error in errors)

    global_errors = validation_results.get("errors", [])
    if isinstance(global_errors, str):
        global_errors = [global_errors]

    manifest["validation"] = {
        "passed": bool(validation_results.get("passed", False)),
        "status": "passed" if validation_results.get("passed", False) else "failed",
        "errors": [str(error) for error in global_errors],
    }
    return manifest
