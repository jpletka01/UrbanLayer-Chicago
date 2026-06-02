"""Process uploaded files into Anthropic multimodal content blocks for Claude Vision."""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path

from backend import db
from backend.config import get_settings

log = logging.getLogger(__name__)

_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_MAX_DIM = 1568


def _maybe_resize_image(data: bytes, mime_type: str) -> tuple[bytes, str]:
    """Resize image if any dimension exceeds _MAX_DIM. Returns (bytes, mime_type)."""
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(data))

        if max(img.size) <= _MAX_DIM:
            return data, mime_type

        img.thumbnail((_MAX_DIM, _MAX_DIM), Image.LANCZOS)

        buf = io.BytesIO()
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue(), "image/jpeg"
    except Exception:
        log.warning("Image resize failed, sending original", exc_info=True)
        return data, mime_type


async def prepare_upload_content_blocks(upload_ids: list[str]) -> list[dict]:
    """Build Anthropic content blocks from upload IDs. Skips files that can't be read."""
    settings = get_settings()
    blocks: list[dict] = []

    for uid in upload_ids:
        upload = await db.get_upload(uid)
        if not upload:
            log.warning("Upload %s not found in DB, skipping", uid)
            continue

        storage_path = Path(upload["storage_path"])
        if not storage_path.is_file():
            log.warning("Upload file missing at %s, skipping", storage_path)
            continue

        mime_type: str = upload["mime_type"]

        try:
            raw = storage_path.read_bytes()
        except Exception:
            log.warning("Failed to read upload %s", uid, exc_info=True)
            continue

        if mime_type in _IMAGE_TYPES:
            data, final_mime = _maybe_resize_image(raw, mime_type)
            b64 = base64.standard_b64encode(data).decode("ascii")
            blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": final_mime,
                    "data": b64,
                },
            })
        elif mime_type == "application/pdf":
            b64 = base64.standard_b64encode(raw).decode("ascii")
            blocks.append({
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": b64,
                },
            })
        else:
            log.warning("Unsupported upload type %s for vision, skipping", mime_type)

    return blocks
