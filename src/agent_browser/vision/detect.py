"""Optional UI element detection from screenshots (M4 hooks)."""

from __future__ import annotations

import asyncio
import io
import logging
from typing import Any

from agent_browser.models.element import BoundingBox
from agent_browser.models.vision import VisionDetection

logger = logging.getLogger(__name__)


class UIDetector:
    """
    Pluggable UI detector.

    Default implementation uses lightweight Pillow heuristics to find
    high-contrast rectangular regions that *may* be controls. This is a
    stub-quality hook for agents — not a production YOLO model.

    Override or inject a custom detector for ML-backed detection later.
    """

    def __init__(
        self,
        *,
        min_area: int = 400,
        max_regions: int = 30,
        contrast_threshold: int = 40,
    ) -> None:
        self.min_area = min_area
        self.max_regions = max_regions
        self.contrast_threshold = contrast_threshold

    def is_available(self) -> bool:
        try:
            from PIL import Image  # noqa: F401
            return True
        except ImportError:
            return False

    def detect_sync(self, image_bytes: bytes) -> list[VisionDetection]:
        """Heuristic connected-ish region scan via downsampled contrast map."""
        try:
            from PIL import Image, ImageFilter, ImageOps
        except ImportError:
            logger.debug("Pillow missing; UI detection skipped")
            return []

        img = Image.open(io.BytesIO(image_bytes)).convert("L")
        # Downsample for speed
        scale = max(1, max(img.width, img.height) // 400)
        small = img.resize((img.width // scale, img.height // scale))
        edges = small.filter(ImageFilter.FIND_EDGES)
        edges = ImageOps.autocontrast(edges)

        # Simple grid scan for bright edge clusters
        cell = 16
        detections: list[VisionDetection] = []
        w, h = edges.size
        pixels = edges.load()
        assert pixels is not None

        visited: set[tuple[int, int]] = set()
        for cy in range(0, h, cell):
            for cx in range(0, w, cell):
                if (cx, cy) in visited:
                    continue
                # average edge strength in cell
                total = 0
                count = 0
                for y in range(cy, min(cy + cell, h)):
                    for x in range(cx, min(cx + cell, w)):
                        total += pixels[x, y]
                        count += 1
                if count == 0:
                    continue
                avg = total / count
                if avg < self.contrast_threshold:
                    continue
                # Expand bounding box of neighboring high-contrast cells
                min_x, min_y = cx, cy
                max_x, max_y = min(cx + cell, w), min(cy + cell, h)
                stack = [(cx, cy)]
                visited.add((cx, cy))
                while stack:
                    sx, sy = stack.pop()
                    for nx, ny in (
                        (sx - cell, sy),
                        (sx + cell, sy),
                        (sx, sy - cell),
                        (sx, sy + cell),
                    ):
                        if nx < 0 or ny < 0 or nx >= w or ny >= h:
                            continue
                        if (nx, ny) in visited:
                            continue
                        # sample cell average
                        t = c = 0
                        for y in range(ny, min(ny + cell, h)):
                            for x in range(nx, min(nx + cell, w)):
                                t += pixels[x, y]
                                c += 1
                        if c and (t / c) >= self.contrast_threshold:
                            visited.add((nx, ny))
                            stack.append((nx, ny))
                            min_x = min(min_x, nx)
                            min_y = min(min_y, ny)
                            max_x = max(max_x, min(nx + cell, w))
                            max_y = max(max_y, min(ny + cell, h))

                box_w = (max_x - min_x) * scale
                box_h = (max_y - min_y) * scale
                if box_w * box_h < self.min_area:
                    continue
                detections.append(
                    VisionDetection(
                        label="ui_region",
                        bounding_box=BoundingBox(
                            x=float(min_x * scale),
                            y=float(min_y * scale),
                            width=float(box_w),
                            height=float(box_h),
                        ),
                        confidence=min(1.0, avg / 255.0),
                        source="heuristic",
                    )
                )
                if len(detections) >= self.max_regions:
                    return detections

        return detections

    async def detect(self, image_bytes: bytes) -> list[VisionDetection]:
        return await asyncio.to_thread(self.detect_sync, image_bytes)

    def detect_to_dicts(self, detections: list[VisionDetection]) -> list[dict[str, Any]]:
        return [d.model_dump() for d in detections]
