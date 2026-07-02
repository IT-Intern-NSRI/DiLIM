"""
Combines every extraction step (text/sections, tables/signatories,
images) into one ManualDocument object per PDF, and handles writing that
object out as JSON for the import pipeline to consume later.
"""

import json
import os
from dataclasses import asdict

from schema import ManualDocument
from extraction.pdf_text_extractor import extract_text_blocks_with_metadata
from extraction.section_detector import split_into_sections
from extraction.table_extractor import (
    extract_all_tables,
    find_signatory_table,
    parse_signatories_from_table,
)
from extraction.image_extractor import extract_images


def build_document(pdf_path: str, output_image_dir: str) -> ManualDocument:
    """
    Input: pdf_path (str) - path to one lab manual PDF.
           output_image_dir (str) - folder to save this PDF's extracted
           images into.
    Output: ManualDocument - the fully assembled, structured
            representation of this one PDF: sections, signatories,
            extracted image paths, and confidence flags for human review.

    Pseudocode:
    1. blocks = extract_text_blocks_with_metadata(pdf_path).
    2. sections = split_into_sections(blocks).
    3. tables = extract_all_tables(pdf_path).
    4. signatory_table = find_signatory_table(tables).
    5. signatories = parse_signatories_from_table(signatory_table) if
       signatory_table is not None else [].
    6. image_paths = extract_images(pdf_path, output_image_dir).
    7. doc_title = derive a readable title, e.g. from the PDF's filename
       (strip extension, replace underscores/dashes with spaces) or from
       the first detected section heading if it looks like a title.
    8. Build confidence_flags (List[str]):
        - If len(sections) < 2: add "Few or no sections detected - check
          heading formatting in the source PDF."
        - If len(signatories) == 0: add "No signatory table found -
          verify manually."
    9. Construct and return:
       ManualDocument(source_pdf_filename=os.path.basename(pdf_path),
       doc_title=doc_title, sections=sections, signatories=signatories,
       extracted_image_paths=image_paths, confidence_flags=confidence_flags).
    """
    blocks = extract_text_blocks_with_metadata(pdf_path)
    sections = split_into_sections(blocks)

    tables = extract_all_tables(pdf_path)
    signatory_table = find_signatory_table(tables)
    signatories = (
        parse_signatories_from_table(signatory_table)
        if signatory_table is not None
        else []
    )

    image_paths = extract_images(pdf_path, output_image_dir)

    # Derive a readable title from the PDF's filename.
    stem = os.path.splitext(os.path.basename(pdf_path))[0]
    doc_title = " ".join(stem.replace("_", " ").replace("-", " ").split())

    confidence_flags = []
    if len(sections) < 2:
        confidence_flags.append(
            "Few or no sections detected - check heading formatting in the source PDF."
        )
    if len(signatories) == 0:
        confidence_flags.append("No signatory table found - verify manually.")

    return ManualDocument(
        source_pdf_filename=os.path.basename(pdf_path),
        doc_title=doc_title,
        sections=sections,
        signatories=signatories,
        extracted_image_paths=image_paths,
        confidence_flags=confidence_flags,
    )


def document_to_json(doc: ManualDocument) -> str:
    """
    Input: doc (ManualDocument) - a fully built document object.
    Output: str - a JSON string representing that document, matching the
            schema the WordPress import pipeline expects (title,
            sections[], signatories[], extracted_image_paths[],
            confidence_flags[]).

    Pseudocode:
    1. Convert the dataclass (including nested Section/Signatory
       dataclasses) into a plain dict using dataclasses.asdict(doc).
    2. Serialize that dict with json.dumps(doc_dict, indent=2).
    3. Return the resulting JSON string.
    """
    doc_dict = asdict(doc)
    return json.dumps(doc_dict, indent=2)


def save_json(doc_json: str, output_path: str) -> None:
    """
    Input: doc_json (str) - JSON string from document_to_json().
           output_path (str) - file path to write to, e.g.
           "./output_json/SOP-04-Autoclave.json".
    Output: None (side effect: writes doc_json to output_path on disk).

    Pseudocode:
    1. Ensure the parent directory of output_path exists.
    2. Open output_path in write mode ("w", encoding="utf-8") and write
       doc_json to it.
    """
    parent_dir = os.path.dirname(output_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(doc_json)
