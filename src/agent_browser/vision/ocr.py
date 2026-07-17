"""Screenshot OCR (M4). Prefer local Tesseract for privacy."""

from __future__ import annotations

import asyncio
import io
import logging
import os
from typing import Any

from agent_browser.models.vision import OCRRegion

logger = logging.getLogger(__name__)


class VisionDependencyError(ImportError):
    """Raised when optional vision extras or Tesseract binary are missing."""


def _load_pil():
    try:
        from PIL import Image
    except ImportError as exc:
        raise VisionDependencyError(
            "Pillow is required for vision features. "
            "Install with: pip install 'agent-browser[vision]'"
        ) from exc
    return Image


def _load_pytesseract(tesseract_cmd: str | None = None):
    try:
        import pytesseract
    except ImportError as exc:
        raise VisionDependencyError(
            "pytesseract is required for OCR. "
            "Install with: pip install 'agent-browser[vision]'"
        ) from exc
    cmd = tesseract_cmd or os.environ.get("TESSERACT_CMD") or os.environ.get(
        "AGENT_BROWSER_TESSERACT_CMD"
    )
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    return pytesseract


class OCREngine:
    """
    Extract text regions from screenshots or element crops.

    Uses local Tesseract via pytesseract when available. Call
    :meth:`is_available` before OCR in optional environments.
    """

    def __init__(
        self,
        *,
        tesseract_cmd: str | None = None,
        lang: str = "eng",
        min_confidence: float = 0.0,
    ) -> None:
        self.tesseract_cmd = tesseract_cmd
        self.lang = lang
        self.min_confidence = min_confidence
        self._available: bool | None = None

    def is_available(self) -> bool:
        """Return True if Pillow, pytesseract, and the Tesseract binary work."""
        if self._available is not None:
            return self._available
        try:
            _load_pil()
            pt = _load_pytesseract(self.tesseract_cmd)
            # Lightweight probe
            pt.get_tesseract_version()
            self._available = True
        except Exception as exc:
            logger.debug("OCR not available: %s", exc)
            self._available = False
        return self._available

    def require_available(self) -> None:
        if not self.is_available():
            raise VisionDependencyError(
                "OCR is not available. Install vision extras and Tesseract:\n"
                "  pip install 'agent-browser[vision]'\n"
                "  # Windows: install Tesseract-OCR and set TESSERACT_CMD\n"
                "  # Debian: sudo apt install tesseract-ocr"
            )

    def ocr_image_sync(
        self,
        image_bytes: bytes,
        *,
        region: tuple[float, float, float, float] | None = None,
        lang: str | None = None,
    ) -> list[OCRRegion]:
        """
        Run OCR on PNG/JPEG bytes.

        ``region`` is optional ``(x, y, width, height)`` crop in image pixels.
        """
        self.require_available()
        Image = _load_pil()
        pytesseract = _load_pytesseract(self.tesseract_cmd)

        img = Image.open(io.BytesIO(image_bytes))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        offset_x, offset_y = 0.0, 0.0
        if region is not None:
            x, y, w, h = region
            # PIL crop box is (left, upper, right, lower)
            left = max(0, int(x))
            upper = max(0, int(y))
            right = min(img.width, int(x + w))
            lower = min(img.height, int(y + h))
            if right <= left or lower <= upper:
                return []
            img = img.crop((left, upper, right, lower))
            offset_x, offset_y = float(left), float(upper)

        data = pytesseract.image_to_data(
            img,
            lang=lang or self.lang,
            output_type=pytesseract.Output.DICT,
        )
        regions: list[OCRRegion] = []
        n = len(data.get("text", []))
        for i in range(n):
            text = (data["text"][i] or "").strip()
            if not text:
                continue
            try:
                conf = float(data["conf"][i])
            except (TypeError, ValueError):
                conf = -1.0
            # Tesseract uses -1 for non-word boxes; filter low confidence
            if conf >= 0 and conf < self.min_confidence:
                continue
            regions.append(
                OCRRegion(
                    x=offset_x + float(data["left"][i]),
                    y=offset_y + float(data["top"][i]),
                    width=float(data["width"][i]),
                    height=float(data["height"][i]),
                    text=text,
                    confidence=(conf / 100.0) if conf >= 0 else None,
                )
            )
        return regions

    async def ocr_image(
        self,
        image_bytes: bytes,
        *,
        region: tuple[float, float, float, float] | None = None,
        lang: str | None = None,
    ) -> list[OCRRegion]:
        """Async wrapper — OCR runs in a worker thread."""
        return await asyncio.to_thread(
            self.ocr_image_sync,
            image_bytes,
            region=region,
            lang=lang,
        )

    async def get_text_in_screenshot(
        self,
        image_bytes: bytes,
        *,
        region: tuple[float, float, float, float] | None = None,
        lang: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Public API from the design report.

        Returns a list of ``{x, y, width, height, text, confidence}`` dicts.
        """
        regions = await self.ocr_image(image_bytes, region=region, lang=lang)
        return [r.to_dict() for r in regions]

    def join_text(self, regions: list[OCRRegion], *, separator: str = " ") -> str:
        """Concatenate OCR region texts in reading order (top-to-bottom, LTR)."""
        ordered = sorted(regions, key=lambda r: (round(r.y / 10), r.x))
        return separator.join(r.text for r in ordered if r.text)
