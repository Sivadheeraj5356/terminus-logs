"""Render docs/AppliedWork_Lab_Build_Plan.md as a Word briefing."""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "AppliedWork_Lab_Build_Plan.md"
OUT = ROOT / "docs" / "AppliedWork_Lab_Build_Plan.docx"

NAVY = RGBColor(0x1B, 0x2A, 0x4A)
BODY = RGBColor(0x22, 0x22, 0x22)
MUTED = RGBColor(0x55, 0x55, 0x55)
COPPER = RGBColor(0xB5, 0x47, 0x1A)
HEADER_BG = "1B2A4A"
ALT_ROW = "F4F6F8"

BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
CODE_RE = re.compile(r"`([^`]+)`")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def set_run(run, *, size=11, bold=False, color=BODY, font="Calibri", italic=False):
    run.font.name = font
    run._element.rPr.rFonts.set(qn("w:eastAsia"), font)
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = color


def shade_cell(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), hex_color)
    shd.set(qn("w:val"), "clear")
    tcPr.append(shd)


def set_cell_border(cell):
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), "D0D5DD")
        tcBorders.append(el)
    tcPr.append(tcBorders)


def fill_cell(cell, text, *, header=False):
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(3)
    run = p.add_run(text)
    set_run(
        run,
        size=9,
        bold=header,
        color=RGBColor(0xFF, 0xFF, 0xFF) if header else BODY,
    )
    set_cell_border(cell)
    if header:
        shade_cell(cell, HEADER_BG)


def add_inline(paragraph, text, *, size=11, color=BODY):
    pos = 0
    pattern = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))")
    for match in pattern.finditer(text):
        if match.start() > pos:
            run = paragraph.add_run(text[pos : match.start()])
            set_run(run, size=size, color=color)
        token = match.group(0)
        if token.startswith("**"):
            run = paragraph.add_run(token[2:-2])
            set_run(run, size=size, bold=True, color=color)
        elif token.startswith("`"):
            run = paragraph.add_run(token[1:-1])
            set_run(run, size=size, font="Consolas", color=NAVY)
        else:
            label, url = LINK_RE.match(token).groups()
            run = paragraph.add_run(f"{label} ({url})")
            set_run(run, size=size, color=NAVY)
        pos = match.end()
    if pos < len(text):
        run = paragraph.add_run(text[pos:])
        set_run(run, size=size, color=color)


def is_table_row(line: str) -> bool:
    return line.startswith("|") and line.endswith("|")


def parse_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip("|").split("|")]


def is_separator(cells: list[str]) -> bool:
    return all(re.fullmatch(r":?-{3,}:?", c.replace(" ", "")) for c in cells)


def build() -> Path:
    md = SRC.read_text(encoding="utf-8")
    doc = Document()
    for section in doc.sections:
        section.top_margin = Inches(0.85)
        section.bottom_margin = Inches(0.85)
        section.left_margin = Inches(0.95)
        section.right_margin = Inches(0.95)

    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped == "---":
            i += 1
            continue

        if stripped.startswith("# "):
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(8)
            run = p.add_run(stripped[2:])
            set_run(run, size=20, bold=True, color=NAVY)
            i += 1
            continue

        if stripped.startswith("## "):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(14)
            p.paragraph_format.space_after = Pt(6)
            run = p.add_run(stripped[3:])
            set_run(run, size=15, bold=True, color=COPPER)
            i += 1
            continue

        if stripped.startswith("```"):
            fence = [stripped[3:]]
            i += 1
            body = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                body.append(lines[i])
                i += 1
            i += 1
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(8)
            p.paragraph_format.left_indent = Inches(0.2)
            run = p.add_run("\n".join(body))
            set_run(run, size=9, font="Consolas", color=NAVY)
            continue

        if is_table_row(stripped):
            rows = [parse_row(stripped)]
            i += 1
            while i < len(lines) and is_table_row(lines[i].strip()):
                rows.append(parse_row(lines[i].strip()))
                i += 1
            if len(rows) > 1 and is_separator(rows[1]):
                rows.pop(1)
            table = doc.add_table(rows=len(rows), cols=len(rows[0]))
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            table.autofit = True
            for r_i, row in enumerate(rows):
                for c_i, val in enumerate(row):
                    fill_cell(table.rows[r_i].cells[c_i], LINK_RE.sub(r"\1", val), header=(r_i == 0))
                    if r_i > 0 and r_i % 2 == 0:
                        shade_cell(table.rows[r_i].cells[c_i], ALT_ROW)
            doc.add_paragraph().paragraph_format.space_after = Pt(6)
            continue

        if stripped.startswith("- "):
            p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.space_after = Pt(3)
            add_inline(p, stripped[2:])
            i += 1
            continue

        if re.match(r"^\d+\.\s", stripped):
            p = doc.add_paragraph(style="List Number")
            p.paragraph_format.space_after = Pt(3)
            add_inline(p, re.sub(r"^\d+\.\s+", "", stripped))
            i += 1
            continue

        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(8)
        p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
        add_inline(p, stripped, size=10 if stripped.startswith("**Date:**") else 11, color=MUTED if stripped.startswith("**Date:**") else BODY)
        i += 1

    doc.save(OUT)
    return OUT


if __name__ == "__main__":
    path = build()
    print(path)
