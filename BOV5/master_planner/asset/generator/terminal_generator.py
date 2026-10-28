"""
Terminal asset generator.

Expected planned asset fields:
    id, type, description, path, required
Optional fields:
    symbol, color, background_color, style

"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_SYMBOLS = {
    "player": "@",
    "enemy": "E",
    "wall": "#",
    "floor": ".",
    "door": "+",
    "exit": "X",
    "key": "k",
    "coin": "$",
    "health": "+",
    "projectile": "*",
    "npc": "N",
    "unknown": "?",
}

DEFAULT_COLORS = {
    "player": "cyan",
    "enemy": "red",
    "wall": "white",
    "floor": "white",
    "door": "yellow",
    "exit": "green",
    "key": "yellow",
    "coin": "yellow",
    "health": "red",
    "projectile": "magenta",
    "npc": "blue",
    "unknown": "white",
}

ALLOWED_COLORS = {
    "black", "red", "green", "yellow", "blue", "magenta", "cyan", "white",
    "bright_black", "bright_red", "bright_green", "bright_yellow",
    "bright_blue", "bright_magenta", "bright_cyan", "bright_white",
}


class TerminalGenerationError(RuntimeError):
    """Raised when terminal assets cannot be generated."""


def _safe_output_path(output_dir: str | Path, filename: str) -> Path:
    """Return a path inside output_dir, rejecting path traversal."""
    root = Path(output_dir).resolve()
    candidate = (root / filename).resolve()
    if candidate != root and root not in candidate.parents:
        raise TerminalGenerationError(
            f"Asset filename '{filename}' resolves outside output directory."
        )
    return candidate


def _infer_role(asset: dict[str, Any]) -> str:
    """Infer a common terminal-game role from ID, type and description."""
    text = " ".join(
        str(asset.get(key, "")) for key in ("id", "type", "description")
    ).lower()

    # Order matters: more specific roles should be checked first.
    for role in (
        "projectile", "player", "enemy", "wall", "floor", "door",
        "exit", "key", "coin", "health", "npc",
    ):
        if role in text:
            return role
    return "unknown"


def _safe_symbol(value: Any, fallback: str) -> str:
    """Keep a symbol to one printable character, with a safe fallback."""
    if value is None:
        value = fallback
    symbol = str(value)
    if not symbol or len(symbol) != 1 or symbol in "\r\n\t":
        raise TerminalGenerationError(
            f"Terminal symbol must be exactly one printable character: {symbol!r}"
        )
    if not symbol.isprintable():
        raise TerminalGenerationError(
            f"Terminal symbol must be printable: {symbol!r}"
        )
    return symbol


def _normalize_color(value: Any, fallback: str) -> str:
    color = str(value if value is not None else fallback).strip().lower()
    if color not in ALLOWED_COLORS:
        raise TerminalGenerationError(
            f"Unsupported terminal color '{color}'. Allowed colors: "
            + ", ".join(sorted(ALLOWED_COLORS))
        )
    return color


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON atomically to avoid leaving a partially written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.stem}_", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def generate_terminal_assets(
    plan_or_assets: dict[str, Any] | list[dict[str, Any]],
    output_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    """
    Generate terminal asset metadata and return one result per planned asset.

    Args:
        plan_or_assets: Either the full result from planner.plan_assets(), or a
            list of normalized asset dictionaries.
        output_dir: Optional output directory override. If omitted with a full
            plan, uses plan["output_dir"]. If omitted with a list, defaults to
            game/assets.

    Returns:
        A list of result dictionaries with id, path, format, status and any
        error information. This is designed to be consumed by update_manifest().
    """
    if isinstance(plan_or_assets, dict):
        assets = plan_or_assets.get("assets")
        output_dir = output_dir or plan_or_assets.get("output_dir", "game/assets")
    else:
        assets = plan_or_assets
        output_dir = output_dir or "game/assets"

    if not isinstance(assets, list):
        raise TerminalGenerationError(
            "Expected a planner result containing an 'assets' list, or a list of assets."
        )

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    symbol_set: dict[str, Any] = {}

    for asset in assets:
        if not isinstance(asset, dict):
            results.append({
                "id": None,
                "status": "failed",
                "error": "Asset entry must be an object/dictionary.",
            })
            continue

        asset_id = str(asset.get("id", "")).strip()
        if not asset_id:
            results.append({
                "id": None,
                "status": "failed",
                "error": "Asset is missing an id.",
            })
            continue

        try:
            role = _infer_role(asset)
            symbol = _safe_symbol(
                asset.get("symbol"), DEFAULT_SYMBOLS.get(role, DEFAULT_SYMBOLS["unknown"])
            )
            color = _normalize_color(
                asset.get("color"), DEFAULT_COLORS.get(role, DEFAULT_COLORS["unknown"])
            )
            background_color = asset.get("background_color")
            if background_color is not None:
                background_color = _normalize_color(background_color, "black")

            entry = {
                "id": asset_id,
                "type": asset.get("type", "symbol_set"),
                "description": str(asset.get("description", "")),
                "symbol": symbol,
                "color": color,
                "background_color": background_color,
                "role": role,
                "required": bool(asset.get("required", True)),
            }
            symbol_set[asset_id] = entry

            # Each asset may have a planner-assigned path. If not, use a stable
            # per-asset filename. Keep all paths inside the requested directory.
            planned_path = asset.get("path")
            if planned_path:
                candidate = Path(str(planned_path))
                # Planner paths are commonly "game/assets/name.json". When an
                # explicit output_dir is supplied, use the basename so the
                # result stays under that directory.
                filename = candidate.name
            else:
                filename = f"{asset_id}.json"

            path = _safe_output_path(root, filename)
            payload = {
                "framework": "terminal",
                "asset": entry,
            }
            _atomic_write_json(path, payload)

            results.append({
                "id": asset_id,
                "path": path.as_posix(),
                "format": "json",
                "status": "generated",
                "role": role,
                "symbol": symbol,
                "color": color,
            })
        except Exception as exc:
            results.append({
                "id": asset_id,
                "status": "failed",
                "error": str(exc),
            })

    # Also emit a consolidated symbol map for easy consumption by game logic.
    # The map is generated from this request, not a prewritten game template.
    if symbol_set:
        try:
            combined_path = _safe_output_path(root, "terminal_assets.json")
            _atomic_write_json(
                combined_path,
                {
                    "framework": "terminal",
                    "assets": symbol_set,
                },
            )
        except Exception as exc:
            results.append({
                "id": "__terminal_assets__",
                "status": "failed",
                "error": f"Could not write consolidated symbol map: {exc}",
            })

    return results
