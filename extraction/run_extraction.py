"""
Entry point for Part 1 (Content Transfer Automation).
Run this from the project root with:  python -m extraction.run_extraction

Reads every PDF in config.INPUT_PDF_DIR, extracts it into a structured
ManualDocument, and writes one JSON file per PDF into
config.OUTPUT_JSON_DIR (plus extracted images into
config.OUTPUT_IMAGE_DIR). Nothing is uploaded to WordPress here - that is
run_import.py's job, after a human reviews these JSON files/flags.
"""

import glob
import os

import config
from extraction.document_builder import build_document, document_to_json, save_json


def main() -> None:
    """
    Input: none (reads all PDFs from config.INPUT_PDF_DIR).
    Output: None (side effect: writes one JSON file per PDF into
            config.OUTPUT_JSON_DIR, extracted images into
            config.OUTPUT_IMAGE_DIR, and prints a summary of which
            documents were flagged for manual review).

    Pseudocode:
    1. pdf_paths = glob.glob(os.path.join(config.INPUT_PDF_DIR, "*.pdf")).
    2. flagged_documents = [] (for the end-of-run summary).
    3. For each pdf_path in pdf_paths:
        a. Print progress, e.g. f"Processing {pdf_path}...".
        b. doc = build_document(pdf_path, config.OUTPUT_IMAGE_DIR).
        c. doc_json = document_to_json(doc).
        d. output_filename = matching filename in
           config.OUTPUT_JSON_DIR with a ".json" extension instead of
           ".pdf".
        e. save_json(doc_json, output_filename).
        f. If doc.confidence_flags is non-empty, append
           (pdf_path, doc.confidence_flags) to flagged_documents.
    4. Print a final summary: total PDFs processed, and for each entry in
       flagged_documents, print the filename and its flags so a human
       knows exactly which documents need closer review before import.
    """
    pdf_paths = glob.glob(os.path.join(config.INPUT_PDF_DIR, "*.pdf"))
    flagged_documents = []

    for pdf_path in pdf_paths:
        print(f"Processing {pdf_path}...")
        doc = build_document(pdf_path, config.OUTPUT_IMAGE_DIR)
        doc_json = document_to_json(doc)

        stem = os.path.splitext(os.path.basename(pdf_path))[0]
        output_filename = os.path.join(config.OUTPUT_JSON_DIR, f"{stem}.json")
        save_json(doc_json, output_filename)

        if doc.confidence_flags:
            flagged_documents.append((pdf_path, doc.confidence_flags))

    print(f"\nProcessed {len(pdf_paths)} PDF(s).")
    if flagged_documents:
        print(f"{len(flagged_documents)} document(s) flagged for review:")
        for pdf_path, flags in flagged_documents:
            print(f"  {pdf_path}:")
            for flag in flags:
                print(f"    - {flag}")
    else:
        print("No documents flagged for review.")


if __name__ == "__main__":
    main()
