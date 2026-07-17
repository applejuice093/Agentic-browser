"""Vision / OCR integration (M4)."""

from agent_browser.vision.detect import UIDetector
from agent_browser.vision.engine import VisionEngine
from agent_browser.vision.ocr import OCREngine, VisionDependencyError

__all__ = [
    "OCREngine",
    "UIDetector",
    "VisionEngine",
    "VisionDependencyError",
]
