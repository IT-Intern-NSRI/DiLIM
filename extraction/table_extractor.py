"""
Extracts tables from a PDF and identifies/parses the signatory block
(e.g. "Prepared by / Reviewed by / Approved by") out of them.
"""

from typing import List, Optional

import pdfplumber

from schema import Signatory
import config


def extract_all_tables(pdf_path: str) -> List[List[List[str]]]:
    """
    Input: pdf_path (str) - path to one lab manual PDF.
    Output: List of tables, where each table is a List of rows, and each
            row is a List of cell strings. Represents every table found
            anywhere in the PDF (most documents will have 0-2 tables).

    Pseudocode:
    1. Open the PDF with pdfplumber.open(pdf_path).
    2. For each page in the PDF, call page.extract_tables() (uses
       pdfplumber's default line-detection strategy).
    3. Flatten all tables found across all pages into a single list.
    4. Return that list.
    """
    all_tables: List[List[List[str]]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                all_tables.append(table)

    return all_tables


def find_signatory_table(tables: List[List[List[str]]]) -> Optional[List[List[str]]]:
    """
    Input: tables (List[List[List[str]]]) - all tables extracted from one
           PDF, as returned by extract_all_tables().
    Output: the single table most likely to be the signatory block, or
            None if no candidate is found.

    Pseudocode:
    1. For each table, flatten all of its cell text into one lowercase
       string.
    2. Check whether any keyword from config.SIGNATORY_TABLE_KEYWORDS
       (e.g. "prepared by", "approved by") appears in that string.
    3. Return the first table that matches. If none match, return None.
    """
    for table in tables:
        flattened = " ".join(
            (cell or "").strip().lower() for row in table for cell in row
        )
        if any(keyword in flattened for keyword in config.SIGNATORY_TABLE_KEYWORDS):
            return table

    return None


def parse_signatories_from_table(table: List[List[str]]) -> List[Signatory]:
    """
    Input: table (List[List[str]]) - the raw signatory table rows, as
           returned by find_signatory_table().
    Output: List[Signatory] - one Signatory per person named in the
            table, with name/title populated. (signature_image_path is
            left as None here - matching images to people happens
            separately, if at all, since signature images are usually
            embedded near the table rather than inside individual cells.)

    Pseudocode:
    1. Identify the header row: the row containing column labels like
       "Name", "Position"/"Title", "Signature".
    2. Determine which column index holds names and which holds
       titles/positions, based on the header row.
    3. For each subsequent (non-header) row:
        a. Skip rows that are empty or clearly not a person entry.
        b. Read the name and title from the identified column indices.
        c. Append Signatory(name=..., title=..., order=<incrementing
           counter>).
    4. Return the list of Signatory objects.
    """
    if not table:
        return []

    # 1. Find the header row: the first row containing a "name"-like label.
    header_index = None
    header_cells = None
    for idx, row in enumerate(table):
        cells_lower = [(cell or "").strip().lower() for cell in row]
        if any("name" in cell for cell in cells_lower):
            header_index = idx
            header_cells = cells_lower
            break

    if header_index is None:
        return []

    # 2. Determine which columns hold names and titles/positions.
    name_col = None
    title_col = None
    for col_idx, cell in enumerate(header_cells):
        if name_col is None and "name" in cell:
            name_col = col_idx
        elif title_col is None and ("title" in cell or "position" in cell):
            title_col = col_idx

    if name_col is None:
        return []

    # 3. Walk the rows after the header, building Signatory entries.
    signatories: List[Signatory] = []
    order = 0
    for row in table[header_index + 1:]:
        if not row or all(not (cell or "").strip() for cell in row):
            continue

        name = (row[name_col] or "").strip() if name_col < len(row) else ""
        if not name:
            continue

        title = ""
        if title_col is not None and title_col < len(row):
            title = (row[title_col] or "").strip()

        signatories.append(Signatory(name=name, title=title, order=order))
        order += 1

    return signatories
