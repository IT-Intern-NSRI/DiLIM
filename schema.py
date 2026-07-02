"""
Shared data models used by both the extraction pipeline and the WordPress
import pipeline. These are plain data containers - no logic to implement
here, just structure.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TextBlock:
    """
    One line/span of text pulled from a PDF page, tagged with the
    formatting metadata needed to distinguish headings from body text.
    """
    text: str
    font_size: float
    is_bold: bool
    page_number: int


@dataclass
class Section:
    """
    One section within a lab manual document. Each Section becomes one
    tab on that document's webpage.
    """
    title: str
    body_html: str
    order: int


@dataclass
class Signatory:
    """
    One signatory entry from the document's approval block
    (e.g. "Prepared by: Jane Doe, Lab Manager").
    """
    name: str
    title: str
    order: int
    signature_image_path: Optional[str] = None


@dataclass
class ManualDocument:
    """
    The full structured representation of one source PDF. This is what
    gets serialized to JSON after extraction, and what the import
    pipeline reads to create one WordPress page.
    """
    source_pdf_filename: str
    doc_title: str
    doc_number: Optional[str] = None
    sections: List[Section] = field(default_factory=list)
    signatories: List[Signatory] = field(default_factory=list)
    extracted_image_paths: List[str] = field(default_factory=list)
    confidence_flags: List[str] = field(default_factory=list)
