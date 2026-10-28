"""
Asset validation for the Asset Generator.

Supports:
- terminal JSON assets
- Pygame image assets (PNG/JPEG/BMP/GIF/WebP when Pillow is installed)
- Godot image resources and common resource-path checks

"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}
TEXT_SUFFIXES = {".json", ".txt", ".csv", ".tsv", ".md"}
GENERATION_SUCCESS_STATUSES = {"generated", "success", "valid", "created"}


def _resolve_asset_path(
    raw_path: str | Path,
    output_dir: str | Path,
    project_root: str | Path | None = None,
) -> Path:
    """Resolve a result path, preferring existing paths and preventing escapes."""
    path = Path(raw_path)
    candidates: list[Path] = []

    if path.is_absolute():
        candidates.append(path)
    else:
        candidates.append(path)
        candidates.append(Path(output_dir) / path.name)
        if project_root is not None:
            candidates.append(Path(project_root) / path)

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    # Return the most likely location for a useful missing-file error.
    if path.is_absolute():
        return path
    return (Path(output_dir) / path.name).resolve()


def _safe_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _check_json_file(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            json.load(handle)
    except json.JSONDecodeError as exc:
        errors.append(f"Invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}")
    except UnicodeDecodeError:
        errors.append("File is not valid UTF-8 text.")
    except OSError as exc:
        errors.append(f"Could not read JSON file: {exc}")
    return errors


def _check_image_file(
    path: Path,
    expected_width: int | None = None,
    expected_height: int | None = None,
) -> tuple[list[str], int | None, int | None]:
    errors: list[str] = []
    width = height = None

    try:
        from PIL import Image
    except ImportError:
        return (
            ["Pillow is required to validate image files; install it with 'pip install Pillow'."],
            None,
            None,
        )

    try:
        with Image.open(path) as image:
            image.verify()
        # Reopen after verify() to inspect dimensions.
        with Image.open(path) as image:
            width, height = image.size
            image_format = (image.format or "").upper()
            if width <= 0 or height <= 0:
                errors.append("Image dimensions must be positive.")
            if expected_width is not None and width != expected_width:
                errors.append(
                    f"Width mismatch: expected {expected_width}, got {width}."
                )
            if expected_height is not None and height != expected_height:
                errors.append(
                    f"Height mismatch: expected {expected_height}, got {height}."
                )
            suffix = path.suffix.lower()
            expected_formats = {
                ".png": {"PNG"},
                ".jpg": {"JPEG"},
                ".jpeg": {"JPEG"},
                ".bmp": {"BMP"},
                ".gif": {"GIF"},
                ".webp": {"WEBP"},
            }
            if suffix in expected_formats and image_format not in expected_formats[suffix]:
                errors.append(
                    f"File extension {suffix} does not match detected image format "
                    f"{image_format or 'unknown'}."
                )
    except Exception as exc:
        errors.append(f"Image could not be opened or verified: {exc}")

    return errors, width, height


def _check_terminal_payload(path: Path) -> list[str]:
    errors = _check_json_file(path)
    if errors:
        return errors

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"Could not parse terminal asset JSON: {exc}"]

    if not isinstance(data, dict):
        return ["Terminal asset file must contain a JSON object."]

    # Individual terminal assets use {"framework": "terminal", "asset": {...}}.
    # The consolidated map uses {"framework": "terminal", "assets": {...}}.
    if data.get("framework") not in (None, "terminal"):
        errors.append(
            f"Expected framework 'terminal', found {data.get('framework')!r}."
        )

    asset = data.get("asset")
    assets = data.get("assets")
    if asset is not None:
        if not isinstance(asset, dict):
            errors.append("'asset' must be a JSON object.")
        else:
            if not isinstance(asset.get("id"), str) or not asset["id"]:
                errors.append("Individual terminal asset is missing a non-empty string 'id'.")
            symbol = asset.get("symbol")
            if not isinstance(symbol, str) or len(symbol) != 1 or not symbol.isprintable():
                errors.append("'symbol' must be one printable character.")
            color = asset.get("color")
            if not isinstance(color, str) or not color:
                errors.append("'color' must be a non-empty string.")
    elif assets is not None:
        if not isinstance(assets, dict):
            errors.append("'assets' in consolidated terminal map must be a JSON object.")
        else:
            for asset_id, entry in assets.items():
                if not isinstance(entry, dict):
                    errors.append(f"Consolidated asset '{asset_id}' must be an object.")
                    continue
                if not isinstance(entry.get("symbol"), str) or len(entry["symbol"]) != 1:
                    errors.append(
                        f"Consolidated asset '{asset_id}' must have a one-character symbol."
                    )
                if not isinstance(entry.get("color"), str) or not entry["color"]:
                    errors.append(
                        f"Consolidated asset '{asset_id}' must have a non-empty color."
                    )
    else:
        errors.append("Terminal JSON must contain either an 'asset' or 'assets' object.")

    return errors


def validate_assets(
    plan_or_results: dict[str, Any] | list[dict[str, Any]],
    output_dir: str | Path | None = None,
    project_root: str | Path | None = None,
) -> dict[str, Any]:
    """
    Validate generated assets and return a manifest-friendly result.

    Args:
        plan_or_results:
            - Planner result: {"framework": ..., "output_dir": ..., "assets": [...]}
              (planned assets may include path, type, width and height)
            - Generator result list: [{"id": ..., "path": ..., "status": ...}, ...]
            - A list of planned assets.
        output_dir: Output directory override; defaults to the planner's
            output_dir or "game/assets".
        project_root: Optional root used to resolve relative paths such as
            "game/assets/player.png" when current working directory differs.

    Returns:
        {
          "passed": bool,
          "errors": [global error strings],
          "assets": [
            {"id": ..., "passed": bool, "errors": [...], "path": ...,
             "width": ..., "height": ..., "format": ...}
          ],
          "usable_assets": int
        }
    """
    if isinstance(plan_or_results, dict):
        framework = str(plan_or_results.get("framework", "")).lower()
        raw_assets = plan_or_results.get("assets")
        output_dir = output_dir or plan_or_results.get("output_dir", "game/assets")
    elif isinstance(plan_or_results, list):
        framework = ""
        raw_assets = plan_or_results
    else:
        return {
            "passed": False,
            "errors": ["Input must be a planner result dictionary or a list."],
            "assets": [],
            "usable_assets": 0,
        }

    if not isinstance(raw_assets, list):
        return {
            "passed": False,
            "errors": ["Input must contain an 'assets' list."],
            "assets": [],
            "usable_assets": 0,
        }

    output_dir = Path(output_dir or "game/assets")
    root = output_dir.resolve()
    results: list[dict[str, Any]] = []
    global_errors: list[str] = []
    usable_assets = 0

    for asset in raw_assets:
        if not isinstance(asset, dict):
            results.append({
                "id": None,
                "passed": False,
                "errors": ["Asset entry must be an object/dictionary."],
            })
            continue

        asset_id = str(asset.get("id", "")).strip() or None
        path_value = asset.get("path")
        if not path_value:
            results.append({
                "id": asset_id,
                "passed": False,
                "errors": ["Asset entry is missing a 'path'."],
            })
            continue

        resolved_path = _resolve_asset_path(path_value, output_dir, project_root)
        errors: list[str] = []

        if not _safe_inside(resolved_path, root):
            errors.append("Asset path resolves outside the configured output directory.")
        elif not resolved_path.exists():
            errors.append(f"Generated asset file does not exist: {resolved_path.as_posix()}")
        elif not resolved_path.is_file():
            errors.append("Asset path exists but is not a regular file.")
        else:
            suffix = resolved_path.suffix.lower()
            asset_type = str(asset.get("type", "")).lower()

            if framework == "terminal" or suffix == ".json":
                errors.extend(_check_terminal_payload(resolved_path))
            elif suffix in IMAGE_SUFFIXES or asset_type in {
                "sprite", "spritesheet", "background", "texture", "icon"
            }:
                image_errors, actual_width, actual_height = _check_image_file(
                    resolved_path,
                    asset.get("width"),
                    asset.get("height"),
                )
                errors.extend(image_errors)
            elif suffix in TEXT_SUFFIXES:
                try:
                    resolved_path.read_text(encoding="utf-8")
                except Exception as exc:
                    errors.append(f"Could not read text asset: {exc}")
            elif resolved_path.stat().st_size == 0:
                errors.append("Generated asset file is empty.")

        passed = not errors
        if passed:
            usable_assets += 1

        result = {
            "id": asset_id,
            "path": resolved_path.as_posix(),
            "passed": passed,
            "errors": errors,
        }

        if resolved_path.exists() and resolved_path.is_file():
            result["format"] = resolved_path.suffix.lstrip(".").lower() or None
            if resolved_path.suffix.lower() in IMAGE_SUFFIXES:
                try:
                    from PIL import Image
                    with Image.open(resolved_path) as image:
                        result["width"], result["height"] = image.size
                except Exception:
                    pass

        results.append(result)

    # Required assets determine overall pass status; optional failed assets are
    # reported but do not necessarily fail the whole batch.
    result_by_id = {item.get("id"): item for item in results}
    required_failures = []
    for asset in raw_assets:
        if not isinstance(asset, dict):
            required_failures.append("Malformed asset entry.")
            continue
        if not bool(asset.get("required", True)):
            continue
        asset_id = str(asset.get("id", "")).strip() or None
        matching = result_by_id.get(asset_id)
        if matching is None or not matching.get("passed", False):
            required_failures.append(
                f"Required asset '{asset_id or '<unknown>'}' failed validation."
            )

    global_errors.extend(required_failures)
    passed = not required_failures and len(raw_assets) > 0

    return {
        "passed": passed,
        "errors": global_errors,
        "assets": results,
        "usable_assets": usable_assets,
    }
