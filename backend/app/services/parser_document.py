"""Layout-aware resume document extraction (PDF, DOCX, TXT) with optional OCR."""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

logger = logging.getLogger(__name__)

MIN_TEXT_CHARS = 40
MIN_TEXT_WORDS = 5

try:
    import fitz
except ImportError:  # pragma: no cover
    fitz = None

try:
    from docx import Document
    from docx.oxml.ns import qn

    DOCX_AVAILABLE = True
except ImportError:  # pragma: no cover
    Document = None
    qn = None
    DOCX_AVAILABLE = False


@dataclass
class TextBlock:
    text: str
    page: int = 0
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0
    font_size: float = 0.0
    kind: str = "text"

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)


@dataclass
class DocumentView:
    text: str = ""
    blocks: list[TextBlock] = field(default_factory=list)
    source: str = "txt"
    filename: str = ""
    page_count: int = 1
    columns: int = 1
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_text(cls, text: str, filename: str = "resume.txt") -> "DocumentView":
        cleaned = clean_text(text)
        blocks = [
            TextBlock(text=line, page=0, y0=float(index), y1=float(index) + 1, kind="text")
            for index, line in enumerate(cleaned.splitlines())
            if line.strip()
        ]
        return cls(text=cleaned, blocks=blocks, source="txt", filename=filename, page_count=1, columns=1)


class OcrEngine(Protocol):
    def image_to_text(self, image_bytes: bytes) -> str:
        ...


class NullOcrEngine:
    def image_to_text(self, image_bytes: bytes) -> str:
        return ""


def _configure_tesseract(pytesseract_module) -> None:
    """Use TESSERACT_CMD when set. Otherwise pytesseract searches PATH (Linux and Windows)."""
    import os

    command = (os.environ.get("TESSERACT_CMD") or "").strip()
    if command:
        pytesseract_module.pytesseract.tesseract_cmd = command


class TesseractOcrEngine:
    def image_to_text(self, image_bytes: bytes) -> str:
        import pytesseract
        from PIL import Image

        _configure_tesseract(pytesseract)
        with Image.open(io.BytesIO(image_bytes)) as image:
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            return pytesseract.image_to_string(image) or ""


_ocr_override: OcrEngine | None = None


def set_ocr_engine_for_tests(engine: OcrEngine | None) -> None:
    global _ocr_override
    _ocr_override = engine


def ocr_engine_available() -> bool:
    try:
        import pytesseract

        _configure_tesseract(pytesseract)
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def get_ocr_engine() -> OcrEngine:
    if _ocr_override is not None:
        return _ocr_override
    if ocr_engine_available():
        return TesseractOcrEngine()
    return NullOcrEngine()


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\x00", " ").replace("\u00a0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def text_is_sufficient(text: str) -> bool:
    cleaned = clean_text(text)
    letters = re.sub(r"[^A-Za-z0-9]+", "", cleaned)
    words = re.findall(r"[A-Za-z]{2,}", cleaned)
    return len(letters) >= MIN_TEXT_CHARS and len(words) >= MIN_TEXT_WORDS


def extract_document(filename: str, file_bytes: bytes, *, enable_ocr: bool = True) -> DocumentView:
    name = (filename or "resume.txt").lower()
    if not file_bytes:
        return DocumentView(source="empty", filename=filename, page_count=0)
    try:
        if name.endswith(".pdf"):
            view = _extract_pdf(filename, file_bytes)
            if enable_ocr and not text_is_sufficient(view.text):
                ocr_view = _ocr_pdf(filename, file_bytes, view)
                if text_is_sufficient(ocr_view.text):
                    return ocr_view
                if ocr_view.warnings:
                    view.warnings.extend(ocr_view.warnings)
                if not view.text:
                    view.source = "empty"
            return view
        if name.endswith(".docx"):
            return _extract_docx(filename, file_bytes)
        if name.endswith(".txt") or name.endswith(".md"):
            text = file_bytes.decode("utf-8", errors="ignore")
            if not text.strip():
                text = file_bytes.decode("latin-1", errors="ignore")
            view = DocumentView.from_text(text, filename=filename)
            if not text_is_sufficient(view.text):
                view.source = "empty" if not view.text else view.source
            return view
        view = DocumentView.from_text(file_bytes.decode("utf-8", errors="ignore"), filename=filename)
        view.source = "empty" if not view.text else view.source
        return view
    except Exception:
        logger.exception("Failed to extract document from %s", filename)
        return DocumentView(source="failed", filename=filename, warnings=["extraction_failed"])


def _extract_pdf(filename: str, file_bytes: bytes) -> DocumentView:
    if fitz is None:
        return DocumentView(source="failed", filename=filename, warnings=["pymupdf_missing"])
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    blocks: list[TextBlock] = []
    max_columns = 1
    try:
        for page_index, page in enumerate(doc):
            page_blocks, columns = _pdf_page_blocks(page, page_index)
            blocks.extend(page_blocks)
            max_columns = max(max_columns, columns)
        ordered_text = "\n".join(block.text for block in blocks if block.text.strip())
        source = "digital_pdf" if text_is_sufficient(ordered_text) else "empty"
        return DocumentView(
            text=clean_text(ordered_text),
            blocks=blocks,
            source=source,
            filename=filename,
            page_count=doc.page_count,
            columns=max_columns,
        )
    finally:
        doc.close()


def _pdf_page_blocks(page: Any, page_index: int) -> tuple[list[TextBlock], int]:
    width = float(page.rect.width or 1)
    height = float(page.rect.height or 1)
    raw_blocks: list[TextBlock] = []
    payload = page.get_text("dict") or {}
    for block in payload.get("blocks", []):
        if block.get("type") != 0:
            continue
        bbox = block.get("bbox") or [0, 0, 0, 0]
        lines_out = []
        max_size = 0.0
        for line in block.get("lines", []):
            spans = line.get("spans") or []
            piece = "".join(span.get("text", "") for span in spans).strip()
            if piece:
                lines_out.append(piece)
            for span in spans:
                max_size = max(max_size, float(span.get("size") or 0))
        text = "\n".join(lines_out).strip()
        if not text:
            continue
        raw_blocks.append(
            TextBlock(
                text=text,
                page=page_index,
                x0=float(bbox[0]),
                y0=float(bbox[1]),
                x1=float(bbox[2]),
                y1=float(bbox[3]),
                font_size=max_size,
                kind="text",
            )
        )
    for table_block in _pdf_table_blocks(page, page_index):
        raw_blocks.append(table_block)
    ordered, columns = _order_blocks(raw_blocks, width, height)
    return ordered, columns


def _pdf_table_blocks(page: Any, page_index: int) -> list[TextBlock]:
    blocks: list[TextBlock] = []
    try:
        finder = page.find_tables()
        tables = finder.tables if finder is not None else []
    except Exception:
        return blocks
    for table in tables or []:
        try:
            bbox = getattr(table, "bbox", None) or [0, 0, 0, 0]
            rows = table.extract() or []
        except Exception:
            continue
        for row_index, row in enumerate(rows):
            cells = [str(cell).strip() for cell in (row or []) if str(cell or "").strip()]
            if not cells:
                continue
            y0 = float(bbox[1]) + row_index * 12
            blocks.append(
                TextBlock(
                    text=" | ".join(cells),
                    page=page_index,
                    x0=float(bbox[0]),
                    y0=y0,
                    x1=float(bbox[2]),
                    y1=y0 + 12,
                    kind="table_cell",
                )
            )
    return blocks


def _order_blocks(blocks: list[TextBlock], page_width: float, page_height: float) -> tuple[list[TextBlock], int]:
    if not blocks:
        return [], 1
    full_width = []
    column_candidates = []
    for block in blocks:
        if _is_full_width(block, page_width):
            full_width.append(block)
        else:
            column_candidates.append(block)
    header = [block for block in full_width if block.y0 <= page_height * 0.24]
    footer = [block for block in full_width if block not in header]
    columns = _cluster_columns(column_candidates, page_width)
    ordered = sorted(header, key=lambda block: (block.y0, block.x0))
    for column in columns:
        ordered.extend(sorted(column, key=lambda block: (block.y0, block.x0)))
    ordered.extend(sorted(footer, key=lambda block: (block.y0, block.x0)))
    return ordered, max(1, len(columns))


def _is_full_width(block: TextBlock, page_width: float) -> bool:
    if page_width <= 0:
        return True
    span = block.width / page_width
    starts_left = block.x0 <= page_width * 0.18
    ends_right = block.x1 >= page_width * 0.72
    return span >= 0.62 or (starts_left and ends_right)


def _cluster_columns(blocks: list[TextBlock], page_width: float) -> list[list[TextBlock]]:
    if len(blocks) < 3 or page_width <= 0:
        return [blocks] if blocks else []
    xs = sorted(block.x0 for block in blocks)
    gaps = [(xs[index + 1] - xs[index], index) for index in range(len(xs) - 1)]
    if not gaps:
        return [blocks]
    max_gap, gap_at = max(gaps)
    if max_gap < page_width * 0.16:
        return [blocks]
    split_x = (xs[gap_at] + xs[gap_at + 1]) / 2
    left = [block for block in blocks if block.x0 < split_x]
    right = [block for block in blocks if block.x0 >= split_x]
    if len(left) < 2 or len(right) < 2:
        return [blocks]
    grouped = []
    for side in (left, right):
        nested = _cluster_columns(side, page_width * 0.7) if len(side) >= 6 else [side]
        grouped.extend(nested)
    return grouped or [blocks]


def _ocr_pdf(filename: str, file_bytes: bytes, fallback: DocumentView) -> DocumentView:
    engine = get_ocr_engine()
    if isinstance(engine, NullOcrEngine) and _ocr_override is None:
        fallback.warnings.append("ocr_unavailable")
        return DocumentView(source="empty", filename=filename, warnings=list(fallback.warnings), page_count=fallback.page_count)
    if fitz is None:
        fallback.warnings.append("ocr_failed")
        return DocumentView(source="empty", filename=filename, warnings=list(fallback.warnings))
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception:
        logger.exception("OCR could not reopen PDF %s", filename)
        return DocumentView(source="empty", filename=filename, warnings=["ocr_failed"])
    texts = []
    try:
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image_bytes = pix.tobytes("png")
            piece = (engine.image_to_text(image_bytes) or "").strip()
            if piece:
                texts.append(piece)
    except Exception:
        logger.exception("OCR failed for %s", filename)
        return DocumentView(source="empty", filename=filename, warnings=["ocr_failed"])
    finally:
        doc.close()
    combined = clean_text("\n".join(texts))
    if not text_is_sufficient(combined):
        return DocumentView(source="empty", filename=filename, warnings=["ocr_insufficient"], page_count=fallback.page_count)
    view = DocumentView.from_text(combined, filename=filename)
    view.source = "ocr"
    view.page_count = fallback.page_count
    return view


def _extract_docx(filename: str, file_bytes: bytes) -> DocumentView:
    if not DOCX_AVAILABLE or Document is None:
        return DocumentView(source="failed", filename=filename, warnings=["docx_unavailable"])
    document = Document(io.BytesIO(file_bytes))
    blocks: list[TextBlock] = []
    y_cursor = 0.0

    def add_block(text: str, kind: str, x0: float = 0.0) -> None:
        nonlocal y_cursor
        cleaned = clean_text(text)
        if not cleaned:
            return
        blocks.append(TextBlock(text=cleaned, page=0, x0=x0, y0=y_cursor, x1=x0 + 240, y1=y_cursor + 12, kind=kind))
        y_cursor += 14

    for paragraph in _docx_header_footer_paragraphs(document):
        add_block(paragraph, "header")
    for paragraph in document.paragraphs:
        add_block(paragraph.text, "text")
    for table in document.tables:
        for row in table.rows:
            cells = [_cell_text(cell) for cell in row.cells]
            cells = [cell for cell in cells if cell]
            if not cells:
                continue
            add_block(" | ".join(cells), "table_cell")
            for index, cell in enumerate(cells):
                add_block(cell, "table_cell", x0=float(index * 160))
    text = clean_text("\n".join(block.text for block in blocks))
    source = "docx" if text_is_sufficient(text) else ("empty" if not text else "docx")
    return DocumentView(text=text, blocks=blocks, source=source, filename=filename, page_count=1, columns=1)


def _docx_header_footer_paragraphs(document: Any) -> list[str]:
    texts: list[str] = []
    for section in document.sections:
        for container in (section.header, section.footer):
            try:
                for paragraph in container.paragraphs:
                    if paragraph.text.strip():
                        texts.append(paragraph.text)
            except Exception:
                continue
    return texts


def _cell_text(cell: Any) -> str:
    pieces = [paragraph.text.strip() for paragraph in cell.paragraphs if paragraph.text.strip()]
    if pieces:
        return clean_text(" ".join(pieces))
    if qn is None:
        return ""
    try:
        raw = cell._tc.xpath(".//w:t")
        return clean_text(" ".join(node.text or "" for node in raw))
    except Exception:
        return ""
