from io import BytesIO
from types import SimpleNamespace

from PIL import Image
from pptx import Presentation
from pptx.util import Inches

from ingestion import pdf_loader, ppt_loader, vision


def _png_bytes():
    buffer = BytesIO()
    Image.new("RGB", (80, 60), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_vision_description_uses_grok_image_input(monkeypatch, tmp_path):
    calls = []

    class FakeResponses:
        def create(self, **kwargs):
            calls.append({"request": kwargs})
            return SimpleNamespace(output_text="A box points to a result.")

    class FakeOpenAI:
        def __init__(self, api_key, **kwargs):
            calls.append({"client": {"api_key": api_key, **kwargs}})
            self.responses = FakeResponses()

    monkeypatch.setenv("XAI_API_KEY", "test-key")
    monkeypatch.setenv("GROK_VISION_MODEL", "grok-test-vision")
    monkeypatch.setenv("SYNAPSE_VISUAL_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(vision, "_client", None)
    monkeypatch.setattr(vision, "_create_vision_client", FakeOpenAI)
    monkeypatch.setattr(vision, "_vision_unavailable_until", 0)

    description = vision.describe_visual(_png_bytes(), "slide 4")

    assert description == "A box points to a result."
    request = calls[1]["request"]
    assert request["model"] == "grok-test-vision"
    content = request["input"][0]["content"]
    assert content[1]["text"].startswith("Analyze this figure from slide 4.")
    assert content[0]["image_url"].startswith("data:image/jpeg;base64,")


def test_vision_503_fails_fast_and_skips_queued_images(monkeypatch, tmp_path):
    calls = []

    class FakeResponses:
        def create(self, **kwargs):
            calls.append(kwargs)
            raise RuntimeError("503 UNAVAILABLE")

    class FakeOpenAI:
        def __init__(self, api_key, **kwargs):
            self.responses = FakeResponses()

    monkeypatch.setenv("XAI_API_KEY", "test-key")
    monkeypatch.setenv("SYNAPSE_VISUAL_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(vision, "_client", None)
    monkeypatch.setattr(vision, "_create_vision_client", FakeOpenAI)
    monkeypatch.setattr(vision, "_vision_unavailable_until", 0)
    monkeypatch.setattr(vision.time, "sleep", lambda _: None)

    first = vision.describe_visual(_png_bytes(), "PDF page 4")
    second = vision.describe_visual(_png_bytes(), "PDF page 5")

    assert first == second == ""
    assert len(calls) == 1


def test_pdf_figure_description_keeps_page_metadata(tmp_path, monkeypatch):
    pdf_path = tmp_path / "figure.pdf"
    pdf = pdf_loader.pymupdf.open()
    page = pdf.new_page()
    page.insert_text((40, 40), "Decision tree")
    for index in range(7):
        page.draw_rect((30 + index * 12, 70, 38 + index * 12, 78))
    pdf.save(pdf_path)
    pdf.close()

    monkeypatch.setattr(
        pdf_loader,
        "describe_visual",
        lambda image, location, context="": f"A decision-tree figure on {location}.",
    )

    documents = pdf_loader.load_pdf(str(pdf_path))

    assert len(documents) == 1
    assert documents[0].metadata["page"] == 1
    assert documents[0].metadata["visual_content_extracted"] is True
    assert "decision-tree figure" in documents[0].page_content


def test_pdf_text_indexing_defers_figure_calls(tmp_path, monkeypatch):
    pdf_path = tmp_path / "deferred-figure.pdf"
    pdf = pdf_loader.pymupdf.open()
    page = pdf.new_page()
    page.insert_text((40, 40), "Decision tree")
    for index in range(7):
        page.draw_rect((30 + index * 12, 70, 38 + index * 12, 78))
    pdf.save(pdf_path)
    pdf.close()

    def unexpected_vision_call(*args, **kwargs):
        raise AssertionError("vision should run after the upload response")

    monkeypatch.setattr(pdf_loader, "describe_visual", unexpected_vision_call)

    documents = pdf_loader.load_pdf(str(pdf_path), analyze_visuals=False)

    assert documents[0].page_content.strip() == "Decision tree"
    assert documents[0].metadata["visual_pending"] is True


def test_powerpoint_figure_description_keeps_slide_metadata(tmp_path, monkeypatch):
    image_path = tmp_path / "figure.png"
    Image.new("RGB", (80, 60), "white").save(image_path)
    ppt_path = tmp_path / "figure.pptx"
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    slide.shapes.add_picture(str(image_path), Inches(1), Inches(1))
    slide.shapes.add_textbox(Inches(1), Inches(3), Inches(4), Inches(1)).text_frame.text = "Diagram"
    presentation.save(ppt_path)

    monkeypatch.setattr(
        ppt_loader,
        "describe_visual",
        lambda image, location, context="": f"A flow diagram on {location}.",
    )

    documents = ppt_loader.load_ppt(str(ppt_path))

    assert len(documents) == 1
    assert documents[0].metadata["slide"] == 1
    assert documents[0].metadata["visual_content_extracted"] is True
    assert "flow diagram" in documents[0].page_content


def test_powerpoint_text_indexing_defers_figure_calls(tmp_path, monkeypatch):
    image_path = tmp_path / "deferred-figure.png"
    Image.new("RGB", (80, 60), "white").save(image_path)
    ppt_path = tmp_path / "deferred-figure.pptx"
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    slide.shapes.add_picture(str(image_path), Inches(1), Inches(1))
    slide.shapes.add_textbox(Inches(1), Inches(3), Inches(4), Inches(1)).text_frame.text = "Diagram"
    presentation.save(ppt_path)

    def unexpected_vision_call(*args, **kwargs):
        raise AssertionError("vision should run after the upload response")

    monkeypatch.setattr(ppt_loader, "describe_visual", unexpected_vision_call)

    documents = ppt_loader.load_ppt(str(ppt_path), analyze_visuals=False)

    assert documents[0].page_content == "Diagram"
    assert documents[0].metadata["visual_pending"] is True
