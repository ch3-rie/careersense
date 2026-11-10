"""Build a DOCX from the ITE40 markdown package. Tables and headings are preserved."""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]


def add_runs(paragraph, text: str) -> None:
    pattern = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`)")
    pos = 0
    for match in pattern.finditer(text):
        if match.start() > pos:
            paragraph.add_run(text[pos:match.start()])
        token = match.group(0)
        if token.startswith("**"):
            run = paragraph.add_run(token[2:-2])
            run.bold = True
        else:
            run = paragraph.add_run(token[1:-1])
            run.font.name = "Consolas"
            run._element.rPr.rFonts.set(qn("w:eastAsia"), "Consolas")
            run.font.size = Pt(10)
        pos = match.end()
    if pos < len(text):
        paragraph.add_run(text[pos:])


def add_table(document: Document, rows: list[list[str]]) -> None:
    if len(rows) < 2:
        return
    width = max(len(row) for row in rows)
    table = document.add_table(rows=len(rows), cols=width)
    table.style = "Table Grid"
    for r_index, row in enumerate(rows):
        for c_index in range(width):
            value = row[c_index] if c_index < len(row) else ""
            cell = table.cell(r_index, c_index)
            cell.text = ""
            paragraph = cell.paragraphs[0]
            add_runs(paragraph, value)
            for run in paragraph.runs:
                run.font.size = Pt(9)
                if r_index == 0:
                    run.bold = True
    document.add_paragraph()


def convert(source: Path, target: Path, title: str) -> None:
    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)
    styles = document.styles
    styles["Normal"].font.name = "Calibri"
    styles["Normal"].font.size = Pt(11)
    styles["Normal"].font.color.rgb = RGBColor(0x1F, 0x29, 0x37)

    lines = source.read_text(encoding="utf-8").splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        if not line.strip():
            index += 1
            continue
        image_match = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", line)
        if image_match:
            image_path = (source.parent / image_match.group(2)).resolve()
            caption = image_match.group(1).strip() or image_path.name
            if image_path.exists():
                document.add_picture(str(image_path), width=Inches(6.2))
                paragraph = document.add_paragraph()
                run = paragraph.add_run(caption)
                run.italic = True
                run.font.size = Pt(9)
            else:
                paragraph = document.add_paragraph()
                add_runs(paragraph, f"Image not found: {image_match.group(2)}")
            index += 1
            continue
        if line.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].startswith("|"):
                raw = lines[index].strip().strip("|")
                cells = [cell.strip() for cell in raw.split("|")]
                if not all(set(cell) <= set("-: ") for cell in cells):
                    rows.append(cells)
                index += 1
            add_table(document, rows)
            continue
        if line.startswith("# "):
            document.add_heading(line[2:].strip(), level=1)
        elif line.startswith("## "):
            document.add_heading(line[3:].strip(), level=2)
        elif line.startswith("### "):
            document.add_heading(line[4:].strip(), level=3)
        elif line.startswith("- "):
            paragraph = document.add_paragraph(style="List Bullet")
            add_runs(paragraph, line[2:].strip())
        elif re.match(r"^\d+\. ", line):
            paragraph = document.add_paragraph(style="List Number")
            add_runs(paragraph, re.sub(r"^\d+\. ", "", line).strip())
        else:
            paragraph = document.add_paragraph()
            if line.startswith("**") and line.endswith("**"):
                paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            add_runs(paragraph, line)
        index += 1
    document.core_properties.title = title
    document.core_properties.subject = "ITE40 Software Quality Assurance"
    target.parent.mkdir(parents=True, exist_ok=True)
    document.save(target)
    print(target)


if __name__ == "__main__":
    convert(
        ROOT / "ITE40-Software-Testing-Package.md",
        ROOT / "ITE40-Software-Testing-Package.docx",
        "CareerSense ITE40 Software Testing Package",
    )
    convert(
        ROOT / "ITE40-Outstanding-Activities.md",
        ROOT / "ITE40-Outstanding-Activities.docx",
        "CareerSense ITE40 Outstanding Activities",
    )
