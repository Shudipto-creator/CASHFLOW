"""PDF parsing utilities"""

import pdfplumber
from PyPDF2 import PdfReader
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)

# Hard limits to keep parsing fast
MAX_PAGES = 15          # stop after this many pages
MAX_TABLE_PAGES = 5     # only extract tables from first N pages
MAX_TEXT_CHARS = 15_000 # cap total extracted text


def _table_to_text(table: List[List]) -> str:
    """Convert a raw pdfplumber table (list of rows) to a compact pipe-delimited string."""
    rows = []
    for row in table:
        # Replace None cells with empty string
        cells = [str(c).strip() if c is not None else "" for c in row]
        rows.append(" | ".join(cells))
    return "\n".join(rows)


def extract_text_from_pdf(file_path: str) -> Dict[str, Any]:
    """
    Extract text and tables from PDF documents

    Args:
        file_path: Path to PDF file

    Returns:
        Dictionary containing text, tables, metadata
    """
    result = {
        "text": "",
        "tables": [],
        "page_count": 0,
        "metadata": {}
    }

    try:
        # Try pdfplumber first (better for tables)
        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)
            result["page_count"] = total_pages
            pages_to_process = pdf.pages[:MAX_PAGES]

            if total_pages > MAX_PAGES:
                logger.info(f"PDF has {total_pages} pages – capping at {MAX_PAGES}")

            all_text = []
            for page_num, page in enumerate(pages_to_process, start=1):
                # Extract plain text
                page_text = page.extract_text()
                if page_text:
                    all_text.append(page_text)

                # Only extract tables on first MAX_TABLE_PAGES pages (slow operation)
                if page_num <= MAX_TABLE_PAGES:
                    tables = page.extract_tables()
                    if tables:
                        for table in tables:
                            table_text = _table_to_text(table)
                            result["tables"].append({
                                "page": page_num,
                                "data": table_text   # compact string, not raw nested list
                            })
                            # Also append table as structured text inline
                            all_text.append(f"[Table on page {page_num}]\n{table_text}")

            combined = "\n\n".join(all_text)
            # Hard cap on total characters sent downstream
            if len(combined) > MAX_TEXT_CHARS:
                logger.info(f"Truncating extracted text from {len(combined)} to {MAX_TEXT_CHARS} chars")
                combined = combined[:MAX_TEXT_CHARS]
            result["text"] = combined

            # Get metadata if available
            if pdf.metadata:
                result["metadata"] = {
                    "author": pdf.metadata.get("Author", ""),
                    "creation_date": str(pdf.metadata.get("CreationDate", ""))
                }

        # Check if PDF is empty
        if not result["text"].strip():
            return {"error": "Document appears to be empty"}

        return result

    except Exception as e:
        # If pdfplumber fails, try PyPDF2 as fallback
        try:
            reader = PdfReader(file_path)
            result["page_count"] = len(reader.pages)

            all_text = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    all_text.append(text)

            result["text"] = "\n\n".join(all_text)

            if reader.metadata:
                result["metadata"] = {
                    "author": reader.metadata.get("/Author", ""),
                    "creation_date": str(reader.metadata.get("/CreationDate", ""))
                }

            if not result["text"].strip():
                return {"error": "Document appears to be empty"}

            return result

        except Exception as fallback_error:
            logger.error(f"PDF parsing failed: {str(fallback_error)}")

            # Check for common errors
            if "encrypted" in str(e).lower() or "password" in str(e).lower():
                return {"error": "Document is password-protected. Please provide an unencrypted version."}

            return {"error": f"Failed to parse PDF: {str(e)}"}
