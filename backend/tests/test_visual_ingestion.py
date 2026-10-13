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


def test_vision_description_uses_groq_image_input(monkeypatch):
    calls = []

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(
                    message=SimpleNamespace(content="A box points to a result.")
                )]
            )

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions())
    )
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(vision, "_client", fake_client)

    description = vision.describe_visual(_png_bytes(), "slide 4")

    assert description == "A box points to a result."
    assert calls[0]["model"] == "qwen/qwen3.8-27b"
    assert calls[0]["messages"][0]["content"][1]["image_url"]["url"].startswith(
        "data:image/jpeg;base64,"
    )


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
