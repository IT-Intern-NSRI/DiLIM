"""
Step 1 of the extraction pipeline: turn a raw PDF into a flat list of
text lines with formatting metadata attached. This is the raw material
every later extraction step (section_detector.py) works from.
"""

import fitz  # PyMuPDF
from typing import List

from schema import TextBlock


def extract_text_blocks_with_metadata(pdf_path: str) -> List[TextBlock]:
    """
    Input: pdf_path (str) - path to a single PDF file, e.g. one lab manual
           document such as "input_pdfs/SOP-04-Autoclave.pdf".
    Output: List[TextBlock] - every line of text in the PDF, in reading
            order, tagged with font size, bold flag, and page number.
            Used by section_detector.py to figure out where sections
            start and end.

    Pseudocode:
    1. Open the PDF with fitz.open(pdf_path).
    2. For each page in the document:
        a. Call page.get_text("dict") to get a structured dump of the
           page: blocks -> lines -> spans.
        b. For each span inside each line inside each block:
            - Read span["text"], span["size"], and span["flags"]
              (bold is encoded as a bit flag in PyMuPDF - flags & 2**4
              indicates bold).
            - Skip spans that are empty or whitespace-only.
            - Append a TextBlock(text=span["text"], font_size=span["size"],
              is_bold=<derived from flags>, page_number=<current page
              index>) to the results list.
    3. Close the document.
    4. Return the accumulated list of TextBlock objects, in the same
       order they appear in the PDF.
    """
    blocks: List[TextBlock] = []

    doc = fitz.open(pdf_path)
    try:
        for page_number, page in enumerate(doc):
            page_dict = page.get_text("dict")
            for block in page_dict.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "")
                        if not text or not text.strip():
                            continue
                        is_bold = bool(span.get("flags", 0) & 2**4)
                        blocks.append(
                            TextBlock(
                                text=text,
                                font_size=span.get("size", 0.0),
                                is_bold=is_bold,
                                page_number=page_number,
                            )
                        )
    finally:
        doc.close()

    return blocks
