"""Vision / OCR data models (M4)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agent_browser.models.element import BoundingBox


class OCRRegion(BaseModel):
    """A recognized text region in a screenshot."""

    x: float
    y: float
    width: float
    height: float
    text: str
    confidence: float | None = None

    @property
    def bounding_box(self) -> BoundingBox:
        return BoundingBox(x=self.x, y=self.y, width=self.width, height=self.height)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class VisionDetection(BaseModel):
    """A UI object detected from pixels (optional detector)."""

    label: str
    bounding_box: BoundingBox
    confidence: float = 1.0
    source: str = "heuristic"


class VisionResult(BaseModel):
    """Aggregate result of a vision pass over a screenshot."""

    ocr_regions: list[OCRRegion] = Field(default_factory=list)
    detections: list[VisionDetection] = Field(default_factory=list)
    image_width: int | None = None
    image_height: int | None = None
    engine: str = "unknown"
