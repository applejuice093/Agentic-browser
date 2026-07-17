# M4 — Vision / OCR

**Branch:** `milestone/m4-vision-ocr`  
**Goal:** Local OCR on screenshots/regions, `get_text_in_screenshot` API, optional UI detection hooks.

## Acceptance

| Item | Status |
|------|--------|
| Local OCR on screenshot regions | Done (Tesseract via pytesseract) |
| `get_text_in_screenshot` API | Done |
| Optional UI detection hooks | Done (heuristic `UIDetector`; pluggable) |

## Install

```bash
pip install -e ".[vision]"
# System Tesseract binary required for real OCR:
#   Windows: https://github.com/UB-Mannheim/tesseract/wiki  + set TESSERACT_CMD
#   Debian/Ubuntu: sudo apt install tesseract-ocr
```

Optional env:

```
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

## API

```python
# Full-page / viewport OCR
regions = await page.get_text_in_screenshot()
# -> [{x, y, width, height, text, confidence}, ...]

# Crop region (CSS pixels)
regions = await page.get_text_in_screenshot(region=(0, 0, 400, 200))

# Typed models + joined text
ocr_regions = await page.ocr()
text = await page.ocr_text()

# Element crop (useful for <canvas> / <img>)
await page.ocr_element("#logo")

# Optional UI detection (heuristic)
detections = await page.detect_ui()

# Combined
result = await page.analyze_vision(run_ocr=True, run_detect=True)
```

## Design notes

- **Local-first:** Tesseract runs on-device; no cloud OCR by default (privacy).
- **On-demand:** OCR is not run on every navigation — call APIs explicitly.
- **Async:** Heavy work uses `asyncio.to_thread` so the event loop stays responsive.
- **Pseudo-elements:** `VisionEngine.ocr_to_pseudo_elements()` maps hits to `role=textImage` for later semantic merge (M6+ polish).

## Modules

| Path | Role |
|------|------|
| `models/vision.py` | `OCRRegion`, `VisionDetection`, `VisionResult` |
| `vision/ocr.py` | `OCREngine`, `get_text_in_screenshot` |
| `vision/detect.py` | `UIDetector` heuristic hooks |
| `vision/engine.py` | `VisionEngine` facade |

## Tests

Unit/integration tests **mock Tesseract** so CI works without the binary. Install Pillow for detector tests:

```bash
pip install Pillow pytesseract
pytest tests/test_vision_ocr.py -q
```
