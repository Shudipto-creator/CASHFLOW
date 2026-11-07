"""Build LLM_CONTEXT_REPORT.docx from the markdown report and requirements.txt."""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "LLM_CONTEXT_REPORT.md"
REQUIREMENTS = ROOT / "requirements.txt"
OUTPUT = ROOT / "LLM_CONTEXT_REPORT.docx"

for path in (REPORT, REQUIREMENTS):
    if not path.exists():
        raise SystemExit(f"Missing input: {path}")


def set_run_font(run, name: str, size: float, bold: bool | None = None, color=None):
    run.font.name = name
    run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if color is not None:
        run.font.color.rgb = color
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), name)


def set_style_east_asia(style, name: str = "Microsoft YaHei"):
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), name)


def clean(text: str) -> str:
    return text.replace("**", "").replace("`", "").strip()


def shade_cell(cell, fill: str):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    cell._tc.get_or_add_tcPr().append(shd)


def add_code_block(doc, lines: list[str]):
    table = doc.add_table(rows=1, cols=1)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.cell(0, 0)
    shade_cell(cell, "F3F4F6")
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.line_spacing = 1.0
    run = paragraph.add_run("\n".join(lines) if lines else " ")
    set_run_font(run, "Consolas", 8.5)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def add_markdown_table(doc, rows: list[list[str]]):
    cols = max(len(row) for row in rows)
    table = doc.add_table(rows=len(rows), cols=cols)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for row_index, row in enumerate(rows):
        for col_index in range(cols):
            text = row[col_index] if col_index < len(row) else ""
            cell = table.cell(row_index, col_index)
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_after = Pt(1)
            run = paragraph.add_run(text or " ")
            set_run_font(run, "Calibri", 8.5, bold=(row_index == 0))
            if row_index == 0:
                shade_cell(cell, "DCE6F1")
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


doc = Document()
for section in doc.sections:
    section.top_margin = Inches(0.8)
    section.bottom_margin = Inches(0.8)
    section.left_margin = Inches(0.85)
    section.right_margin = Inches(0.85)

normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(10.5)
set_style_east_asia(normal)
for heading_name in ("Heading 1", "Heading 2"):
    set_style_east_asia(doc.styles[heading_name])

footer = doc.sections[0].footer.paragraphs[0]
footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
footer_run = footer.add_run("CASHFLOW — FINN CFO conversation memory report")
set_run_font(footer_run, "Calibri", 8, color=RGBColor(0x66, 0x66, 0x66))

title = doc.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
title_run = title.add_run("CASHFLOW — FINN CFO Conversation Memory")
set_run_font(title_run, "Calibri", 20, bold=True, color=RGBColor(0x1F, 0x3A, 0x5F))

subtitle = doc.add_paragraph()
subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
subtitle_run = subtitle.add_run("Implementation report and complete package list")
set_run_font(subtitle_run, "Calibri", 12, color=RGBColor(0x44, 0x44, 0x44))

meta = doc.add_paragraph()
meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
meta_run = meta.add_run(
    "2026-11-07  ·  Local Ollama llama3.2  ·  SQLite (FINNDB + cfone)"
)
set_run_font(meta_run, "Calibri", 9, color=RGBColor(0x66, 0x66, 0x66))
doc.add_paragraph()

lines = REPORT.read_text(encoding="utf-8").splitlines()
index = 0
skipped_title = False

while index < len(lines):
    stripped = lines[index].strip()

    if stripped.startswith("```"):
        index += 1
        code_lines = []
        while index < len(lines) and not lines[index].strip().startswith("```"):
            code_lines.append(lines[index])
            index += 1
        index += 1
        add_code_block(doc, code_lines)
        continue

    if not stripped:
        index += 1
        continue

    if stripped.startswith("# "):
        if not skipped_title:
            skipped_title = True
        else:
            doc.add_heading(clean(stripped[2:]), level=1)
        index += 1
        continue

    if stripped.startswith("## "):
        doc.add_heading(clean(stripped[3:]), level=1)
        index += 1
        continue

    if stripped.startswith("### "):
        doc.add_heading(clean(stripped[4:]), level=2)
        index += 1
        continue

    if stripped.startswith("|"):
        table_lines = []
        while index < len(lines) and lines[index].strip().startswith("|"):
            table_lines.append(lines[index].strip())
            index += 1
        rows = []
        for row_index, table_line in enumerate(table_lines):
            cells = [clean(cell) for cell in table_line.strip("|").split("|")]
            if row_index == 1 and all(
                re.fullmatch(r":?-{3,}:?", cell) for cell in cells
            ):
                continue
            rows.append(cells)
        if rows:
            add_markdown_table(doc, rows)
        continue

    if stripped.startswith("- "):
        paragraph = doc.add_paragraph(style="List Bullet")
        paragraph.paragraph_format.space_after = Pt(2)
        paragraph.add_run(clean(stripped[2:]))
        index += 1
        continue

    numbered = re.match(r"^\d+\.\s+(.*)$", stripped)
    if numbered:
        paragraph = doc.add_paragraph(style="List Number")
        paragraph.paragraph_format.space_after = Pt(2)
        paragraph.add_run(clean(numbered.group(1)))
        index += 1
        continue

    paragraph_lines = [stripped]
    index += 1
    while index < len(lines):
        upcoming = lines[index].strip()
        if (
            not upcoming
            or upcoming.startswith(("#", "|", "- ", "```"))
            or re.match(r"^\d+\.\s+", upcoming)
        ):
            break
        paragraph_lines.append(upcoming)
        index += 1

    paragraph_text = clean(" ".join(paragraph_lines))
    if paragraph_text.startswith("Date: 2026-11-07"):
        continue
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(4)
    paragraph.add_run(paragraph_text)

doc.add_page_break()
doc.add_heading("requirements.txt — all packages used", level=1)
doc.add_paragraph(
    "The conversation-memory work added no new Python dependency; it uses the existing "
    "FastAPI, SQLAlchemy and local Ollama stack. The full project requirements are "
    "reproduced below. The canonical file remains requirements.txt at the repository root."
)

requirements_text = REQUIREMENTS.read_text(encoding="utf-8")
package_entries = [
    line.strip()
    for line in requirements_text.splitlines()
    if line.strip() and not line.strip().startswith("#")
]
doc.add_paragraph(
    f"{len(package_entries)} package entries are listed, including the banking-gate "
    "runtime and the optional IM SDKs."
)

changes_table = doc.add_table(rows=5, cols=3)
changes_table.style = "Table Grid"
changes_table.alignment = WD_TABLE_ALIGNMENT.CENTER
change_rows = [
    ("Package", "Version", "Why it is listed"),
    ("bank2ai", "0.6.1", "FINN zero-trust gate / mock bank"),
    ("fastmcp", "4.1.3", "MCP transport used by the gate"),
    ("python-telegram-bot", "unpinned", "Optional Telegram channel"),
    ("wecom-aibot-python-sdk", "unpinned", "Optional WeCom channel"),
]
for row_index, row in enumerate(change_rows):
    for col_index, value in enumerate(row):
        cell = changes_table.cell(row_index, col_index)
        paragraph = cell.paragraphs[0]
        paragraph.paragraph_format.space_after = Pt(1)
        run = paragraph.add_run(value)
        set_run_font(run, "Calibri", 8.5, bold=(row_index == 0))
        if row_index == 0:
            shade_cell(cell, "DCE6F1")
doc.add_paragraph().paragraph_format.space_after = Pt(2)

doc.add_heading("Complete requirements.txt", level=2)
add_code_block(doc, requirements_text.splitlines())

doc.save(OUTPUT)

saved = Document(str(OUTPUT))
all_text = "\n".join(paragraph.text for paragraph in saved.paragraphs)
for table in saved.tables:
    for row in table.rows:
        for cell in row.cells:
            all_text += "\n" + cell.text
headings = [
    paragraph.text
    for paragraph in saved.paragraphs
    if paragraph.style.name.startswith("Heading")
]

assert "finn cfo conversation memory" in all_text.lower()
assert "51 passed" in all_text
assert "bank2ai==0.6.1" in all_text
assert "wecom-aibot-python-sdk" in all_text
assert any("requirements.txt" in heading for heading in headings)

print(f"saved: {OUTPUT}")
print(f"size: {OUTPUT.stat().st_size:,} bytes")
print(f"paragraphs: {len(saved.paragraphs)}, tables: {len(saved.tables)}")
print("headings:")
for heading in headings:
    print("  -", heading)
print(f"package entries in requirements: {len(package_entries)}")
print("docx verification: OK")
