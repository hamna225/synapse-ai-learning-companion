import os
from concurrent.futures import ThreadPoolExecutor

import pymupdf
from langchain_core.documents import Document
from ingestion.vision import describe_visual


def load_pdf(file_path, analyze_visuals=True):

    documents = []
    visual_jobs = []

    pdf = pymupdf.open(file_path)
    try:
        max_pdf_pages = max(1, int(os.getenv("MAX_PDF_PAGES", "50")))
    except ValueError:
        max_pdf_pages = 50
    if len(pdf) > max_pdf_pages:
        page_count = len(pdf)
        pdf.close()
        raise ValueError(
            f"This PDF has {page_count} pages. The current limit is "
            f"{max_pdf_pages} pages."
        )

    for page_number, page in enumerate(pdf):

        text = page.get_text()
        visual_image = None
        has_visual_content = False
        has_visual_content = (
            bool(page.get_images(full=True))
            or len(page.get_drawings()) >= 6
        )
        if analyze_visuals and has_visual_content:
            try:
                image = page.get_pixmap(
                    matrix=pymupdf.Matrix(1.4, 1.4),
                    alpha=False,
                ).tobytes("png")
                visual_image = image
            except Exception as error:
                print(f"Could not render PDF page {page_number + 1}: {error}")

        if text.strip() or visual_image or (not analyze_visuals and has_visual_content):
            page_content = text
            if not analyze_visuals and not page_content.strip() and has_visual_content:
                page_content = f"Visual content on PDF page {page_number + 1}; figure analysis pending."

            document = Document(
                page_content=page_content,
                metadata={
                    "source": file_path,
                    "source_type": "pdf",
                    "page": page_number + 1,
                    "visual_content_extracted": False,
                    "visual_pending": bool(has_visual_content and not analyze_visuals),
                }
            )

            documents.append(document)
            if visual_image:
                visual_jobs.append((
                    len(documents) - 1,
                    visual_image,
                    f"PDF page {page_number + 1}",
                    text,
                ))

    pdf.close()

    if analyze_visuals and visual_jobs:
        try:
            max_workers = max(
                1,
                min(8, int(os.getenv("VISION_CONCURRENCY", "4"))),
            )
        except ValueError:
            max_workers = 4
        max_workers = min(max_workers, len(visual_jobs))

        def describe(job):
            _, image, location, surrounding_text = job
            return describe_visual(image, location, surrounding_text)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            descriptions = list(executor.map(describe, visual_jobs))

        for job, visual_description in zip(visual_jobs, descriptions):
            document_index = job[0]
            if visual_description:
                document = documents[document_index]
                document.page_content = (
                    f"{document.page_content.rstrip()}\n\n"
                    f"Figure or diagram description: {visual_description}"
                ).strip()
                document.metadata["visual_content_extracted"] = True

    return [document for document in documents if document.page_content.strip()]
