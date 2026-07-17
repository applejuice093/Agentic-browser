"""High-level vision facade combining OCR + optional UI detection (M4)."""

from __future__ import annotations

from typing import Any

from agent_browser.models.element import Element
from agent_browser.models.vision import OCRRegion, VisionDetection, VisionResult
from agent_browser.vision.detect import UIDetector
from agent_browser.vision.ocr import OCREngine, VisionDependencyError


class VisionEngine:
    """
    Orchestrates screenshot OCR and optional UI detection.

    Designed to run selectively (on demand) — not on every navigation —
    to keep latency low.
    """

    def __init__(
        self,
        *,
        ocr: OCREngine | None = None,
        detector: UIDetector | None = None,
        tesseract_cmd: str | None = None,
    ) -> None:
        self.ocr = ocr or OCREngine(tesseract_cmd=tesseract_cmd)
        self.detector = detector or UIDetector()

    def is_ocr_available(self) -> bool:
        return self.ocr.is_available()

    def is_detect_available(self) -> bool:
        return self.detector.is_available()

    async def analyze(
        self,
        image_bytes: bytes,
        *,
        region: tuple[float, float, float, float] | None = None,
        run_ocr: bool = True,
        run_detect: bool = False,
        lang: str | None = None,
    ) -> VisionResult:
        """Run OCR and/or UI detection on a screenshot."""
        ocr_regions: list[OCRRegion] = []
        detections: list[VisionDetection] = []
        engine_name = "none"
        width = height = None

        try:
            from PIL import Image
            import io

            img = Image.open(io.BytesIO(image_bytes))
            width, height = img.size
        except Exception:
            pass

        if run_ocr:
            if not self.ocr.is_available():
                raise VisionDependencyError(
                    "OCR requested but Tesseract/vision extras are not available"
                )
            ocr_regions = await self.ocr.ocr_image(image_bytes, region=region, lang=lang)
            engine_name = "tesseract"

        if run_detect:
            # Detect on full image (region crop not applied to detector by default)
            if region is not None:
                # crop first if possible
                try:
                    from PIL import Image
                    import io

                    img = Image.open(io.BytesIO(image_bytes))
                    x, y, w, h = region
                    cropped = img.crop((int(x), int(y), int(x + w), int(y + h)))
                    buf = io.BytesIO()
                    cropped.save(buf, format="PNG")
                    detections = await self.detector.detect(buf.getvalue())
                    # offset boxes back
                    for d in detections:
                        d.bounding_box.x += x
                        d.bounding_box.y += y
                except Exception:
                    detections = await self.detector.detect(image_bytes)
            else:
                detections = await self.detector.detect(image_bytes)
            if engine_name == "none":
                engine_name = "heuristic"
            else:
                engine_name = f"{engine_name}+heuristic"

        return VisionResult(
            ocr_regions=ocr_regions,
            detections=detections,
            image_width=width,
            image_height=height,
            engine=engine_name,
        )

    async def get_text_in_screenshot(
        self,
        image_bytes: bytes,
        *,
        region: tuple[float, float, float, float] | None = None,
        lang: str | None = None,
    ) -> list[dict[str, Any]]:
        return await self.ocr.get_text_in_screenshot(
            image_bytes, region=region, lang=lang
        )

    def ocr_to_pseudo_elements(
        self,
        regions: list[OCRRegion],
        *,
        start_id: int = 10_000,
    ) -> list[Element]:
        """
        Convert OCR hits into semantic-like elements (role=textImage).

        High ids avoid colliding with DOM stable ids in a single session.
        """
        elements: list[Element] = []
        eid = start_id
        for reg in regions:
            if not reg.text.strip():
                continue
            elements.append(
                Element(
                    id=eid,
                    role="textImage",
                    type="ocr",
                    text=reg.text,
                    name=reg.text,
                    visible=True,
                    enabled=True,
                    bounding_box=reg.bounding_box,
                    confidence=reg.confidence,
                    attributes={"source": "ocr"},
                )
            )
            eid += 1
        return elements
