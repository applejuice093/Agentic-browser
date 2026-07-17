"""Screenshot OCR (M4). Prefer local Tesseract for privacy."""

from __future__ import annotations

from typing import Any


class OCREngine:
    """Extract text regions from screenshots or canvas nodes."""

    def __init__(self, *, tesseract_cmd: str | None = None) -> None:
        self.tesseract_cmd = tesseract_cmd

    async def get_text_in_screenshot(self, image_bytes: bytes) -> list[dict[str, Any]]:
        raise NotImplementedError("OCREngine is implemented in M4 (install [vision] extras)")
