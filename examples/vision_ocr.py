"""
M4 example: screenshot OCR + optional UI detection.

Requires: pip install 'agent-browser[vision]' and system Tesseract for real OCR.
Without Tesseract, detection still runs if Pillow is installed.

    python examples/vision_ocr.py
"""

from __future__ import annotations

import asyncio

from agent_browser import Browser
from agent_browser.vision import VisionDependencyError

HTML = """
<!DOCTYPE html>
<html>
<head><title>Vision Demo</title></head>
<body style="font-family: sans-serif; padding: 24px; background: white;">
  <h1>Order Summary</h1>
  <p>Total: $42.00</p>
  <button id="pay" style="padding: 12px 24px; border: 2px solid #000;">Pay Now</button>
</body>
</html>
"""


async def main() -> None:
    async with Browser(headless=True) as browser:
        page = await browser.set_content(HTML)
        png = await page.screenshot()
        print("screenshot bytes:", len(png))

        print("OCR available:", page.vision.is_ocr_available())
        print("Detect available:", page.vision.is_detect_available())

        try:
            regions = await page.get_text_in_screenshot(image_bytes=png)
            print("OCR regions:", regions)
            print("joined:", await page.ocr_text(image_bytes=png))
        except VisionDependencyError as exc:
            print("OCR skipped:", exc)

        detections = await page.detect_ui(image_bytes=png)
        print("UI detections:", len(detections))
        for d in detections[:5]:
            print(" ", d.label, d.bounding_box.model_dump(), round(d.confidence, 2))


if __name__ == "__main__":
    asyncio.run(main())
