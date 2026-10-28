"""
GenAI-first asset generator for Godot games, with procedural fallback.

Attempts to generate artwork using an OpenAI-compatible Images API when a key
is configured. If unavailable or unsuccessful, creates a procedural PNG using
Pillow. Godot imports PNG textures; this module does not create scenes/scripts.

Public API:
    generate_godot_assets(plan_or_assets, output_dir=None) -> list[dict]

Optional fields:
    color, background_color, source_path, frames, columns, rows
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .image_generation import generate_image_with_genai

class GodotGenerationError(RuntimeError):
    """Raised when Godot assets cannot be generated."""


PALETTE = {
    "blue": (65, 130, 230, 255),
    "cyan": (40, 210, 220, 255),
    "red": (220, 65, 70, 255),
    "green": (70, 185, 105, 255),
    "yellow": (245, 205, 65, 255),
    "orange": (240, 135, 55, 255),
    "purple": (155, 95, 210, 255),
    "pink": (235, 115, 170, 255),
    "white": (240, 240, 240, 255),
    "black": (22, 25, 32, 255),
    "gray": (115, 125, 140, 255),
    "grey": (115, 125, 140, 255),
    "brown": (135, 90, 55, 255),
    "transparent": (0, 0, 0, 0),
}


def _color(value: Any, fallback=(90, 150, 220, 255)):
    if isinstance(value, (list, tuple)) and len(value) in (3, 4):
        vals = tuple(max(0, min(255, int(v))) for v in value)
        return vals + (255,) if len(vals) == 3 else vals
    return PALETTE.get(str(value or "").strip().lower(), fallback)


def _role(asset: dict[str, Any]) -> str:
    text = " ".join(str(asset.get(k, "")) for k in ("id", "type", "description")).lower()
    for role in ("player", "enemy", "boss", "wall", "floor", "coin", "key",
                 "health", "projectile", "npc", "tree", "rock", "button",
                 "icon", "background", "tile"):
        if role in text:
            return role
    return str(asset.get("type", "sprite")).lower()


def _safe_path(root: Path, filename: str) -> Path:
    root = root.resolve()
    result = (root / Path(filename).name).resolve()
    if result == root or root not in result.parents:
        raise GodotGenerationError(f"Unsafe asset filename: {filename!r}")
    return result


def _draw_texture(asset: dict[str, Any], path: Path):
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise GodotGenerationError(
            "Pillow is required to generate PNG assets. Install it with: pip install Pillow"
        ) from exc

    width = int(asset.get("width") or 64)
    height = int(asset.get("height") or 64)
    if width <= 0 or height <= 0 or width > 4096 or height > 4096:
        raise GodotGenerationError("Image width/height must be between 1 and 4096.")

    role = _role(asset)
    kind = str(asset.get("type", "sprite")).lower()
    fg = _color(asset.get("color"), _color({
        "player": "blue", "enemy": "red", "boss": "purple", "coin": "yellow",
        "key": "yellow", "health": "green", "projectile": "orange",
        "npc": "cyan", "wall": "gray", "tree": "green", "rock": "gray",
        "button": "blue", "icon": "white",
    }.get(role, "blue")))
    bg = _color(asset.get("background_color"), (0, 0, 0, 0))
    image = Image.new("RGBA", (width, height), bg)
    draw = ImageDraw.Draw(image)

    if kind == "background" or role == "background":
        image = Image.new("RGBA", (width, height), _color(asset.get("background_color"), (22, 32, 58, 255)))
        draw = ImageDraw.Draw(image)
        for y in range(height):
            factor = y / max(1, height - 1)
            base = (int(18 + 20*factor), int(28 + 28*factor), int(54 + 38*factor), 255)
            draw.line((0, y, width, y), fill=base)
        step = max(12, min(width, height) // 5)
        for x in range(step // 2, width, step):
            for y in range(step // 2, height, step):
                draw.ellipse((x-1, y-1, x+1, y+1), fill=(220, 230, 255, 190))
    elif kind == "texture" or role in ("wall", "floor", "tile", "rock"):
        draw.rectangle((0, 0, width-1, height-1), fill=fg)
        step = max(4, min(width, height) // 4)
        darker = tuple(max(0, c - 32) for c in fg[:3]) + (255,)
        for x in range(0, width, step):
            draw.line((x, 0, x, height), fill=darker, width=1)
        for y in range(0, height, step):
            draw.line((0, y, width, y), fill=darker, width=1)
    elif kind == "spritesheet":
        frames = max(1, min(int(asset.get("frames") or 4), 64))
        columns = max(1, min(int(asset.get("columns") or frames), frames))
        rows = (frames + columns - 1) // columns
        cell_w, cell_h = max(1, width // columns), max(1, height // rows)
        for i in range(frames):
            col, row = i % columns, i // columns
            x0, y0 = col * cell_w, row * cell_h
            inset_x, inset_y = max(1, cell_w // 6), max(1, cell_h // 6)
            box = (x0 + inset_x, y0 + inset_y,
                   min(width-1, x0 + cell_w-inset_x),
                   min(height-1, y0 + cell_h-inset_y))
            frame_color = ((fg[0] + i*17) % 256, (fg[1] + i*29) % 256, (fg[2] + i*11) % 256, 255)
            draw.ellipse(box, fill=frame_color)
    else:
        pad = max(2, min(width, height) // 8)
        x1, y1, x2, y2 = pad, pad, max(pad, width-pad-1), max(pad, height-pad-1)
        if role in ("coin", "health", "icon"):
            draw.ellipse((x1, y1, x2, y2), fill=fg, outline=(255,255,255,255), width=max(1,min(width,height)//16))
        elif role in ("key", "projectile"):
            draw.ellipse((x1+(x2-x1)//4, y1+(y2-y1)//4, x2, y2), fill=fg)
            draw.rectangle((x1, y1+(y2-y1)//2, x1+(x2-x1)//2, y1+(y2-y1)//2+max(2,height//10)), fill=fg)
        elif role in ("player", "enemy", "boss", "npc"):
            draw.rounded_rectangle((x1,y1,x2,y2), radius=max(2,min(width,height)//6), fill=fg, outline=(255,255,255,255), width=max(1,min(width,height)//24))
            eye_y = y1 + max(2,(y2-y1)//3)
            eye_r = max(1,min(width,height)//16)
            for ex in (x1+(x2-x1)//3, x1+2*(x2-x1)//3):
                draw.ellipse((ex-eye_r,eye_y-eye_r,ex+eye_r,eye_y+eye_r), fill=(255,255,255,255))
        elif role == "button" or kind == "ui":
            draw.rounded_rectangle((x1,y1,x2,y2), radius=max(2,min(width,height)//8), fill=fg, outline=(255,255,255,255), width=max(1,min(width,height)//24))
        else:
            draw.rectangle((x1,y1,x2,y2), fill=fg, outline=(255,255,255,255), width=max(1,min(width,height)//24))

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")
    return width, height, role


def generate_godot_assets(
    plan_or_assets: dict[str, Any] | list[dict[str, Any]],
    output_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    """
    Generate Godot-compatible PNG assets and return manifest-friendly results.

    PNG files can be imported by Godot and assigned to Sprite2D, TextureRect,
    TileSet, or other texture-consuming nodes by the game-generation agent.
    """
    if isinstance(plan_or_assets, dict):
        assets = plan_or_assets.get("assets")
        output_dir = output_dir or plan_or_assets.get("output_dir", "game/assets")
    else:
        assets = plan_or_assets
        output_dir = output_dir or "game/assets"

    if not isinstance(assets, list):
        raise GodotGenerationError("Expected a planner result or a list of assets.")

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    results = []

    for asset in assets:
        if not isinstance(asset, dict) or not str(asset.get("id", "")).strip():
            results.append({"id": None, "status": "failed", "error": "Asset must be an object with a non-empty id."})
            continue
        asset_id = str(asset["id"]).strip()
        try:
            planned = Path(str(asset.get("path", ""))).name
            filename = planned or f"{asset_id}.png"
            path = _safe_path(root, filename)
            kind = str(asset.get("type", "sprite")).lower()
            width_dbg = asset.get("width") or 64
            height_dbg = asset.get("height") or 64
            print(f"[ASSET GEN] generating '{asset_id}' ({kind}, {width_dbg}x{height_dbg}) -> {path.name}")
            if kind == "font":
                source = asset.get("source_path")
                if not source or not Path(str(source)).is_file():
                    raise GodotGenerationError(
                        "Font assets cannot be synthesized. Provide an existing font file in 'source_path'."
                    )
                shutil.copy2(source, path)
                results.append({"id": asset_id, "path": path.as_posix(), "format": path.suffix.lstrip(".").lower(), "status": "generated", "source": str(source)})
            elif kind == "other":
                payload = {
                    "framework": "godot",
                    "id": asset_id,
                    "description": str(asset.get("description", "")),
                    "note": "Metadata only; Godot game logic/scenes are not generated here."
                }
                path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
                results.append({"id": asset_id, "path": path.as_posix(), "format": path.suffix.lstrip(".").lower() or "dat", "status": "generated"})
            else:
                print(f"[ASSET GEN]   -> calling OpenRouter for '{asset_id}'...")
                genai_result = generate_image_with_genai(asset, path, "godot", plan_or_assets.get("game_style") if isinstance(plan_or_assets, dict) else None)
                if genai_result.get("ok"):
                    width = int(asset.get("width") or 64)
                    height = int(asset.get("height") or 64)
                    print(f"[ASSET GEN]   <- '{asset_id}' OK via genai (model={genai_result.get('model')})")
                    results.append({
                        "id": asset_id, "path": path.as_posix(), "format": "png",
                        "width": width, "height": height, "status": "generated",
                        "role": _role(asset), "generation_method": "genai",
                        "model": genai_result.get("model"), "godot_compatible": True,
                        "import_note": "Godot imports PNG textures automatically when the project is opened."
                    })
                else:
                    print(f"[ASSET GEN]   <- '{asset_id}' genai failed ({genai_result.get('reason')}), drawing procedural fallback")
                    width, height, role = _draw_texture(asset, path)
                    results.append({
                        "id": asset_id, "path": path.as_posix(), "format": "png",
                        "width": width, "height": height, "status": "generated",
                        "role": role, "generation_method": "procedural_fallback",
                        "fallback_reason": genai_result.get("reason"),
                        "godot_compatible": True,
                        "import_note": "Godot imports PNG textures automatically when the project is opened."
                    })
        except Exception as exc:
            results.append({"id": asset_id, "status": "failed", "error": str(exc)})

    return results