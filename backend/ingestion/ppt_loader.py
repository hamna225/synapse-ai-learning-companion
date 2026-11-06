from io import BytesIO
import os
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn
from langchain_core.documents import Document

from ingestion.vision import describe_visual


def _iter_shapes(shapes):
    for shape in shapes:
        yield shape
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _iter_shapes(shape.shapes)


def _chart_description(shape):
    try:
        chart = shape.chart
        details = []
        if chart.has_title:
            details.append(chart.chart_title.text_frame.text.strip())

        # Scatter charts may contain intentionally blank cached points.
        # python-pptx converts those blanks to float and raises TypeError.
        scatter_series = [
            series for series in chart.series
            if series._element.find(qn("c:xVal")) is not None
        ]
        if scatter_series:
            for series in scatter_series:
                element = series._element
                x_cache = element.find(
                    f"{qn('c:xVal')}//{qn('c:numCache')}"
                )
                y_cache = element.find(
                    f"{qn('c:yVal')}//{qn('c:numCache')}"
                )

                def cached_values(cache):
                    if cache is None:
                        return {}
                    values = {}
                    for point in cache.findall(qn("c:pt")):
                        value = point.find(qn("c:v"))
                        if value is not None and value.text:
                            values[int(point.get("idx", 0))] = value.text
                    return values

                x_values = cached_values(x_cache)
                y_values = cached_values(y_cache)
                pairs = [
                    f"({x_values[index]}, {y_values[index]})"
                    for index in sorted(x_values.keys() & y_values.keys())
                ][:20]
                if pairs:
                    details.append(f"{series.name}: " + ", ".join(pairs))
            return "; ".join(detail for detail in details if detail)

        categories = []
        if chart.plots:
            categories = [category.label for category in chart.plots[0].categories]

        for series in chart.series:
            values = list(series.values)
            points = [
                f"{categories[index]}: {value}"
                if index < len(categories)
                else str(value)
                for index, value in enumerate(values)
            ]
            details.append(f"{series.name}: " + ", ".join(points))

        return "; ".join(detail for detail in details if detail)
    except Exception as error:
        print(f"Could not extract PowerPoint chart data: {error}")
        return ""


def _picture_contact_sheet(image_bytes_list, start_index=1):
    """Combine slide pictures into one labeled image for a single vision call."""
    tiles = []
    for index, image_bytes in enumerate(image_bytes_list, start=1):
        try:
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            image.thumbnail((560, 420))
            tile = Image.new("RGB", (580, 460), "white")
            tile.paste(image, ((580 - image.width) // 2, 30))
            ImageDraw.Draw(tile).text(
                (10, 8), f"Figure {start_index + index - 1}", fill="black"
            )
            tiles.append(tile)
        except Exception as error:
            print(f"Could not read embedded PowerPoint image: {error}")

    if not tiles:
        return b""

    columns = 2
    rows = (len(tiles) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * 580, rows * 460), "white")
    for index, tile in enumerate(tiles):
        sheet.paste(tile, ((index % columns) * 580, (index // columns) * 460))

    output = BytesIO()
    sheet.save(output, format="JPEG", quality=85, optimize=True)
    return output.getvalue()


def load_ppt(file_path, analyze_visuals=True):
    documents = []
    visual_jobs = []
    presentation = Presentation(file_path)

    for slide_number, slide in enumerate(presentation.slides, start=1):
        slide_text = []
        picture_bytes = []
        has_picture = False
        chart_text = []

        for shape in _iter_shapes(slide.shapes):
            if getattr(shape, "has_text_frame", False):
                text = shape.text.strip()
                if text:
                    slide_text.append(text)

            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                has_picture = True
                if analyze_visuals:
                    picture_bytes.append(shape.image.blob)
            elif getattr(shape, "has_chart", False):
                description = _chart_description(shape)
                if description:
                    chart_text.append(description)

        text = "\n".join(slide_text)
        if chart_text:
            text += "\n\nChart data: " + "\n".join(chart_text)

        picture_batches = []
        if analyze_visuals and picture_bytes:
            for batch_start in range(0, len(picture_bytes), 8):
                batch = picture_bytes[batch_start:batch_start + 8]
                contact_sheet = _picture_contact_sheet(
                    batch,
                    start_index=batch_start + 1,
                )
                if contact_sheet:
                    picture_batches.append((
                        contact_sheet,
                        f"PowerPoint slide {slide_number}, figures "
                        f"{batch_start + 1}-{batch_start + len(batch)}",
                    ))

        if text.strip() or picture_batches or (not analyze_visuals and has_picture):
            slide_content = text
            if not analyze_visuals and not slide_content.strip() and has_picture:
                slide_content = f"Visual content on slide {slide_number}; figure analysis pending."
            documents.append(
                Document(
                    page_content=slide_content,
                    metadata={
                        "source": file_path,
                        "source_type": "ppt",
                        "slide": slide_number,
                        "visual_content_extracted": bool(chart_text),
                        "visual_pending": bool(has_picture and not analyze_visuals),
                    },
                )
            )
            for contact_sheet, location in picture_batches:
                visual_jobs.append((
                    len(documents) - 1,
                    contact_sheet,
                    location,
                    text,
                ))

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
            document = documents[job[0]]
            if visual_description:
                document.page_content = (
                    f"{document.page_content.rstrip()}\n\n"
                    f"Figure or diagram description: {visual_description}"
                ).strip()
                document.metadata["visual_content_extracted"] = True

    return [document for document in documents if document.page_content.strip()]
