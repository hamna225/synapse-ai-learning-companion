import os

import pymupdf
from langchain_core.documents import Document
from ingestion.vision import describe_visual


def load_pdf(file_path):

    documents = []
    visual_pages_processed = 0
    max_visual_pages = int(os.getenv("VISION_MAX_VISUALS_PER_FILE", "20"))

    pdf = pymupdf.open(file_path)

    for page_number, page in enumerate(pdf):

        text = page.get_text()
        visual_description = ""

        has_embedded_images = bool(page.get_images(full=True))
        has_vector_figure = len(page.get_drawings()) >= 6
        if (
            visual_pages_processed < max_visual_pages
            and (has_embedded_images or has_vector_figure)
        ):
            try:
                image = page.get_pixmap(
                    matrix=pymupdf.Matrix(1.4, 1.4),
                    alpha=False,
                ).tobytes("png")
                visual_description = describe_visual(
                    image,
                    f"PDF page {page_number + 1}",
                    text,
                )
                visual_pages_processed += 1
            except Exception as error:
                print(f"Could not render PDF page {page_number + 1}: {error}")

        if visual_description:
            text = (
                f"{text.rstrip()}\n\n"
                f"Figure or diagram description: {visual_description}"
            ).strip()

        if text.strip():

            document = Document(
                page_content=text,
                metadata={
                    "source": file_path,
                    "source_type": "pdf",
                    "page": page_number + 1,
                    "visual_content_extracted": bool(visual_description),
                }
            )

            documents.append(document)

    pdf.close()

    return documents
