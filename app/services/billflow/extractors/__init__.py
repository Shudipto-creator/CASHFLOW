"""Format-specific extractors returning normalized transaction dicts."""

from __future__ import annotations

import io
import os
import tempfile
from typing import Any, Dict, List, Tuple

from .common import detect_header_row, rows_to_transactions


def extract_from_csv(content: bytes, filename: str) -> Tuple[List[Dict[str, Any]], List[str], str]:
    from app.services.billflow.csv_importer import parse_bank_csv

    parsed = parse_bank_csv(content, filename)
    txns = parsed.get("transactions", [])
    errors = parsed.get("errors", [])
    bank = parsed.get("bank", "generic")
    # ensure bank field
    for t in txns:
        t.setdefault("bank", bank)
    return txns, errors, bank


def _rows_from_excel(file_path: str) -> List[List[Any]]:
    from app.utils.excel_parser import extract_data_from_excel

    data = extract_data_from_excel(file_path)
    if "error" in data:
        raise ValueError(data["error"])
    rows: List[List[Any]] = []
    for sheet in data.get("sheets", []):
        headers = sheet.get("headers", [])
        rows.append(headers)
        for r in sheet.get("data", []):
            rows.append([r.get(h) for h in headers])
    return rows


def extract_from_excel(file_path: str, filename: str) -> Tuple[List[Dict[str, Any]], List[str], str]:
    rows = _rows_from_excel(file_path)
    found = detect_header_row(rows)
    if not found:
        return [], ["No header row with date/amount found"], "generic"
    idx, colmap = found
    txns, errors = rows_to_transactions(rows[idx + 1:], colmap, filename, "generic")
    return txns, errors, "generic"


def _rows_from_pdf(file_path: str) -> List[List[Any]]:
    from app.utils.pdf_parser import extract_text_from_pdf

    data = extract_text_from_pdf(file_path)
    if "error" in data:
        raise ValueError(data["error"])
    rows: List[List[Any]] = []
    for t in data.get("tables", []):
        text = t.get("data", "")
        for line in text.splitlines():
            cells = [c.strip() for c in line.split("|")]
            rows.append(cells)
    # fallback: try to parse text lines as space-separated? skip for determinism
    return rows


def extract_from_pdf(file_path: str, filename: str) -> Tuple[List[Dict[str, Any]], List[str], str]:
    rows = _rows_from_pdf(file_path)
    found = detect_header_row(rows)
    if not found:
        # try whole text as single-column? no; return empty with hint
        return [], ["No tabular data with date/amount headers found in PDF"], "generic"
    idx, colmap = found
    txns, errors = rows_to_transactions(rows[idx + 1:], colmap, filename, "generic")
    return txns, errors, "generic"


def _rows_from_docx(file_path: str) -> List[List[Any]]:
    try:
        import docx
    except ImportError as e:
        raise ValueError("python-docx not installed") from e
    doc = docx.Document(file_path)
    rows: List[List[Any]] = []
    for table in doc.tables:
        for row in table.rows:
            rows.append([c.text.strip() for c in row.cells])
    return rows


def extract_from_docx(file_path: str, filename: str) -> Tuple[List[Dict[str, Any]], List[str], str]:
    rows = _rows_from_docx(file_path)
    found = detect_header_row(rows)
    if not found:
        return [], ["No tabular data with date/amount headers found in DOCX"], "generic"
    idx, colmap = found
    txns, errors = rows_to_transactions(rows[idx + 1:], colmap, filename, "generic")
    return txns, errors, "generic"


def extract_from_image(file_path: str, filename: str) -> Tuple[List[Dict[str, Any]], List[str], str]:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as e:
        raise ValueError("OCR dependencies not installed (pytesseract, Pillow)") from e
    try:
        text = pytesseract.image_to_string(Image.open(file_path))
    except Exception as e:
        raise ValueError(f"OCR failed: {e}") from e
    # Treat OCR text as lines; try to find a header row by splitting on whitespace
    lines = [ln for ln in text.splitlines() if ln.strip()]
    rows = [ln.split() for ln in lines]
    found = detect_header_row(rows)
    if not found:
        return [], ["No tabular data with date/amount headers found in image OCR"], "generic"
    idx, colmap = found
    txns, errors = rows_to_transactions(rows[idx + 1:], colmap, filename, "generic")
    return txns, errors, "generic"


def extract_transactions(ext: str, file_path: str, filename: str, content: bytes) -> Tuple[List[Dict[str, Any]], List[str], str]:
    ext = ext.lower()
    if ext in (".csv", ".txt"):
        return extract_from_csv(content, filename)
    if ext in (".xlsx", ".xls"):
        return extract_from_excel(file_path, filename)
    if ext == ".pdf":
        return extract_from_pdf(file_path, filename)
    if ext == ".docx":
        return extract_from_docx(file_path, filename)
    if ext in (".png", ".jpg", ".jpeg"):
        return extract_from_image(file_path, filename)
    raise ValueError(f"Unsupported extension: {ext}")