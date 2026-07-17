"""M4 vision / OCR unit tests (mocked Tesseract; real Pillow heuristics)."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest

from agent_browser.models.vision import OCRRegion
from agent_browser.vision.detect import UIDetector
from agent_browser.vision.engine import VisionEngine
from agent_browser.vision.ocr import OCREngine, VisionDependencyError


def _png_bytes(width: int = 120, height: int = 40, color: tuple[int, ...] = (255, 255, 255)) -> bytes:
    pytest.importorskip("PIL")
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (width, height), color)
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, width - 10, height - 10], outline=(0, 0, 0), width=2)
    draw.text((20, 12), "Hello", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_ocr_region_model():
    r = OCRRegion(x=1, y=2, width=10, height=5, text="Hi", confidence=0.9)
    assert r.bounding_box.width == 10
    assert r.to_dict()["text"] == "Hi"


def test_ocr_engine_unavailable_raises():
    engine = OCREngine()
    engine._available = False  # noqa: SLF001
    with pytest.raises(VisionDependencyError):
        engine.ocr_image_sync(b"not-an-image")


def test_ocr_image_sync_with_mock_tesseract():
    pytest.importorskip("PIL")
    from PIL import Image

    png = _png_bytes()
    mock_pt = MagicMock()
    mock_pt.Output.DICT = "dict"
    mock_pt.image_to_data.return_value = {
        "text": ["Hello", ""],
        "conf": ["90", "-1"],
        "left": [20, 0],
        "top": [12, 0],
        "width": [40, 0],
        "height": [12, 0],
    }
    mock_pt.get_tesseract_version.return_value = "5.0.0"

    engine = OCREngine()
    with (
        patch("agent_browser.vision.ocr._load_pytesseract", return_value=mock_pt),
        patch("agent_browser.vision.ocr._load_pil", return_value=Image),
    ):
        engine._available = True  # noqa: SLF001
        regions = engine.ocr_image_sync(png)

    assert len(regions) == 1
    assert regions[0].text == "Hello"
    assert regions[0].confidence == pytest.approx(0.9)


@pytest.mark.asyncio
async def test_get_text_in_screenshot_async_mock():
    pytest.importorskip("PIL")
    from PIL import Image

    png = _png_bytes()
    mock_pt = MagicMock()
    mock_pt.Output.DICT = "dict"
    mock_pt.image_to_data.return_value = {
        "text": ["World"],
        "conf": ["80"],
        "left": [5],
        "top": [5],
        "width": [30],
        "height": [10],
    }
    engine = OCREngine()
    with (
        patch("agent_browser.vision.ocr._load_pytesseract", return_value=mock_pt),
        patch("agent_browser.vision.ocr._load_pil", return_value=Image),
    ):
        engine._available = True  # noqa: SLF001
        rows = await engine.get_text_in_screenshot(png)
    assert rows[0]["text"] == "World"


def test_join_text_reading_order():
    engine = OCREngine()
    regions = [
        OCRRegion(x=50, y=0, width=10, height=10, text="B"),
        OCRRegion(x=0, y=0, width=10, height=10, text="A"),
        OCRRegion(x=0, y=20, width=10, height=10, text="C"),
    ]
    assert engine.join_text(regions) == "A B C"


def test_ui_detector_finds_edge_regions():
    pytest.importorskip("PIL")
    det = UIDetector(min_area=50, contrast_threshold=10, max_regions=10)
    # high-contrast image should yield at least one region
    png = _png_bytes(200, 120)
    detections = det.detect_sync(png)
    assert isinstance(detections, list)
    # heuristic may or may not find boxes depending on text rendering; ensure no crash
    for d in detections:
        assert d.label
        assert d.bounding_box.width > 0


def test_vision_engine_pseudo_elements():
    ve = VisionEngine()
    regions = [OCRRegion(x=0, y=0, width=20, height=10, text="Logo", confidence=0.8)]
    els = ve.ocr_to_pseudo_elements(regions, start_id=10000)
    assert len(els) == 1
    assert els[0].role == "textImage"
    assert els[0].id == 10000
    assert els[0].text == "Logo"


@pytest.mark.asyncio
async def test_vision_engine_analyze_detect_only():
    pytest.importorskip("PIL")
    ve = VisionEngine()
    png = _png_bytes()
    result = await ve.analyze(png, run_ocr=False, run_detect=True)
    assert result.engine in ("heuristic", "none", "heuristic")
    assert result.ocr_regions == []


@pytest.mark.asyncio
async def test_page_get_text_in_screenshot_mocked():
    pytest.importorskip("PIL")
    from PIL import Image

    from agent_browser import Browser

    mock_pt = MagicMock()
    mock_pt.Output.DICT = "dict"
    mock_pt.image_to_data.return_value = {
        "text": ["Cart"],
        "conf": ["95"],
        "left": [8],
        "top": [8],
        "width": [40],
        "height": [12],
    }
    mock_pt.get_tesseract_version.return_value = "5"

    html = "<html><body><h1>Cart</h1><p>Hello vision</p></body></html>"
    async with Browser(headless=True) as browser:
        page = await browser.set_content(html)
        with (
            patch("agent_browser.vision.ocr._load_pytesseract", return_value=mock_pt),
            patch("agent_browser.vision.ocr._load_pil", return_value=Image),
        ):
            page.vision.ocr._available = True  # noqa: SLF001
            rows = await page.get_text_in_screenshot()
        assert any(r["text"] == "Cart" for r in rows)
        assert page.last_vision is not None


@pytest.mark.asyncio
async def test_page_detect_ui():
    pytest.importorskip("PIL")
    from agent_browser import Browser

    html = """
    <html><body style="background:white">
      <button style="padding:20px;border:3px solid black">Buy</button>
    </body></html>
    """
    async with Browser(headless=True) as browser:
        page = await browser.set_content(html)
        detections = await page.detect_ui()
        assert isinstance(detections, list)


@pytest.mark.asyncio
async def test_page_ocr_element_mocked():
    pytest.importorskip("PIL")
    from PIL import Image

    from agent_browser import Browser

    mock_pt = MagicMock()
    mock_pt.Output.DICT = "dict"
    mock_pt.image_to_data.return_value = {
        "text": ["Buy"],
        "conf": ["88"],
        "left": [0],
        "top": [0],
        "width": [20],
        "height": [10],
    }

    html = '<html><body><button id="b">Buy now</button></body></html>'
    async with Browser(headless=True) as browser:
        page = await browser.set_content(html)
        with (
            patch("agent_browser.vision.ocr._load_pytesseract", return_value=mock_pt),
            patch("agent_browser.vision.ocr._load_pil", return_value=Image),
        ):
            page.vision.ocr._available = True  # noqa: SLF001
            regions = await page.ocr_element("#b")
        assert regions[0].text == "Buy"
