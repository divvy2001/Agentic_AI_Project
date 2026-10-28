"""OpenRouter image-generation client with runtime configuration and procedural fallback.

The API key and selected model can be provided at runtime with
configure_openrouter(api_key, model). The test suite prompts for them and does
not save them to environment variables or files.

Uses OpenRouter's unified image endpoint:
    POST https://openrouter.ai/api/v1/images
    GET  https://openrouter.ai/api/v1/images/models

Framework generators fall back to Pillow procedural drawing if no runtime key
is configured or an API request fails.
"""
from __future__ import annotations

import base64
import getpass
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_OPENROUTER_API_KEY: str | None = None
_OPENROUTER_IMAGE_MODEL: str | None = None
_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def configure_openrouter(api_key: str, model: str, base_url: str = _OPENROUTER_BASE_URL) -> None:
    """Keep credentials/model in process memory only; do not write them to disk."""
    global _OPENROUTER_API_KEY, _OPENROUTER_IMAGE_MODEL, _OPENROUTER_BASE_URL
    _OPENROUTER_API_KEY = api_key.strip()
    _OPENROUTER_IMAGE_MODEL = model.strip()
    _OPENROUTER_BASE_URL = base_url.strip().rstrip("/")


def clear_openrouter_config() -> None:
    """Clear the in-memory API key and selected model."""
    global _OPENROUTER_API_KEY, _OPENROUTER_IMAGE_MODEL
    _OPENROUTER_API_KEY = None
    _OPENROUTER_IMAGE_MODEL = None


def generation_mode() -> str:
    """Legacy compatibility: procedural mode can still be forced by environment."""
    mode = os.getenv("ASSET_GENERATION_MODE", "auto").strip().lower()
    return mode if mode in {"auto", "genai", "procedural"} else "auto"


def genai_configured() -> bool:
    return bool(_OPENROUTER_API_KEY or os.getenv("ASSET_OPENROUTER_API_KEY", "").strip()) and generation_mode() != "procedural"


def _request_json(url: str, api_key: str, method: str = "GET", payload: dict | None = None, timeout: float = 60) -> dict:
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def list_openrouter_image_models(api_key: str, base_url: str = _OPENROUTER_BASE_URL) -> list[dict[str, Any]]:
    """Fetch currently available image-generation models from OpenRouter."""
    response = _request_json(
        base_url.rstrip("/") + "/images/models",
        api_key.strip(),
        timeout=45,
    )
    models = response.get("data") or []
    cleaned = []
    for model in models:
        if not isinstance(model, dict) or not model.get("id"):
            continue
        cleaned.append({
            "id": str(model["id"]),
            "name": str(model.get("name") or model["id"]),
            "description": str(model.get("description") or ""),
            "supported_parameters": model.get("supported_parameters") or {},
        })
    return sorted(cleaned, key=lambda item: item["id"].lower())


def prompt_for_openrouter_api_key() -> str:
    """Prompt for the API key without persisting it."""
    print("\nOpenRouter image-generation setup")
    print("Your API key is entered securely and is not saved to a file.")

    api_key = getpass.getpass(
        "Enter your OpenRouter API key (input hidden): "
    ).strip()

    if not api_key:
        raise ValueError("No OpenRouter API key was entered.")

    return api_key

def _target_api_size(width: int, height: int) -> str:
    ratio = width / max(1, height)
    if ratio >= 1.35:
        return "1536x1024"
    if ratio <= 0.74:
        return "1024x1536"
    return "1024x1024"


def _prompt_for_asset(asset: dict[str, Any], framework: str, game_style: str | None) -> str:
    asset_id = str(asset.get("id", "game asset"))
    asset_type = str(asset.get("type", "sprite")).lower()
    description = str(asset.get("description", "")).strip()
    style = str(asset.get("style") or game_style or "cohesive game art").strip()
    width = int(asset.get("width") or 64)
    height = int(asset.get("height") or 64)
    color = asset.get("color")
    role = "game background" if asset_type == "background" or "background" in asset_id.lower() else "game asset"

    prompt = (
        f"Create one polished 2D video-game {role}. Asset name: {asset_id}. "
        f"Asset type: {asset_type}. Description: {description or asset_id}. "
        f"Visual style: {style}. Main color preference: {color or 'choose colors fitting the description'}. "
        f"Target canvas aspect ratio: {width}:{height}. "
        "Make the subject visually clear, readable at game scale, with clean edges and no lettering, "
        "watermarks, signatures, mockup frames, or extra unrelated objects. "
    )
    if asset_type == "spritesheet":
        frames = max(1, min(int(asset.get("frames") or 4), 16))
        columns = max(1, min(int(asset.get("columns") or frames), frames))
        prompt += (
            f"This is a sprite sheet with exactly {frames} distinct animation frames arranged in "
            f"{columns} columns on a regular grid. Keep the same character design and scale in every frame, "
            "use consistent spacing, and do not add labels."
        )
    elif asset_type == "background" or "background" in asset_id.lower():
        prompt += "Fill the whole canvas with an environment background; do not leave transparent gaps."
    else:
        prompt += (
            "Show one centered subject only. Use a transparent background if supported, with no ground plane "
            "or scene backdrop, so the asset can be composited into a game."
        )
    if framework == "godot":
        prompt += " The output will be used as a texture in a Godot 2D game."
    elif framework == "pygame":
        prompt += " The output will be loaded as a PNG image by a Pygame game."
    return prompt


def generate_image_with_genai(
    asset: dict[str, Any],
    output_path: str | Path,
    framework: str,
    game_style: str | None = None,
) -> dict[str, Any]:
    """Generate an image through OpenRouter, returning ok=False for procedural fallback."""
    if generation_mode() == "procedural":
        return {"ok": False, "reason": "ASSET_GENERATION_MODE=procedural"}

    api_key = (_OPENROUTER_API_KEY or os.getenv("ASSET_OPENROUTER_API_KEY", "")).strip()
    model = (_OPENROUTER_IMAGE_MODEL or os.getenv("ASSET_IMAGE_MODEL", "")).strip()
    if not api_key:
        return {"ok": False, "reason": "No OpenRouter API key configured in this run"}
    if not model:
        return {"ok": False, "reason": "No OpenRouter image model selected"}

    try:
        from PIL import Image
    except ImportError:
        return {"ok": False, "reason": "Pillow is not installed"}

    width = int(asset.get("width") or 64)
    height = int(asset.get("height") or 64)
    if width <= 0 or height <= 0 or width > 4096 or height > 4096:
        return {"ok": False, "reason": "Image width/height must be between 1 and 4096"}

    base_url = _OPENROUTER_BASE_URL.rstrip("/")
    asset_type = str(asset.get("type", "sprite")).lower()
    is_background = asset_type == "background" or "background" in str(asset.get("id", "")).lower()
    prompt = _prompt_for_asset(asset, framework, game_style)

    # OpenRouter's unified Images API accepts model and prompt across image models.
    # Avoid model-specific parameters here so users can switch models more easily.
    payload = {
        "model": model,
        "prompt": prompt,
        "aspect_ratio": "16:9" if width / height >= 1.35 else ("9:16" if width / height <= 0.74 else "1:1"),
    }
    # Keep the request to broadly supported fields so the user can switch among
    # OpenRouter image models with fewer model-specific parameter failures.

    try:
        response_payload = _request_json(
            base_url + "/images",
            api_key,
            method="POST",
            payload=payload,
            timeout=float(os.getenv("ASSET_IMAGE_TIMEOUT", "120")),
        )
        items = response_payload.get("data") or []
        if not items:
            return {"ok": False, "reason": "OpenRouter response did not contain image data"}
        item = items[0]
        image_bytes = None
        if item.get("b64_json"):
            image_bytes = base64.b64decode(item["b64_json"])
        elif item.get("url"):
            # Download only the URL returned by OpenRouter.
            with urllib.request.urlopen(item["url"], timeout=60) as image_response:
                image_bytes = image_response.read()
        if not image_bytes:
            return {"ok": False, "reason": "OpenRouter returned neither b64_json nor url"}

        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        temp_path = out.with_name(out.stem + ".genai.tmp")
        temp_path.write_bytes(image_bytes)
        try:
            with Image.open(temp_path) as im:
                im.load()
                im = im.convert("RGBA")
                resampling = getattr(Image, "Resampling", Image).LANCZOS
                if is_background:
                    scale = max(width / im.width, height / im.height)
                    resized = im.resize(
                        (max(width, int(im.width * scale)), max(height, int(im.height * scale))),
                        resampling,
                    )
                    left = (resized.width - width) // 2
                    top = (resized.height - height) // 2
                    final_image = resized.crop((left, top, left + width, top + height))
                else:
                    im.thumbnail((width, height), resampling)
                    final_image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                    final_image.alpha_composite(im, ((width - im.width) // 2, (height - im.height) // 2))
                final_image.save(out, format="PNG")
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass
        return {"ok": True, "model": model, "api_base": base_url}
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:600]
        except Exception:
            detail = str(exc)
        return {"ok": False, "reason": f"OpenRouter HTTP {exc.code}: {detail}"}
    except Exception as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
