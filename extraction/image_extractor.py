"""
Extracts embedded images (figures, diagrams, signature images) out of a
PDF and saves them to disk with predictable filenames.
"""

import os
from typing import List

import fitz  # PyMuPDF


def extract_images(pdf_path: str, output_dir: str) -> List[str]:
    """
    Input: pdf_path (str) - path to one lab manual PDF.
           output_dir (str) - folder where extracted images should be
           saved, e.g. "./output_images".
    Output: List[str] - file paths of every image saved to disk, named
            "{pdf_filename_stem}_p{page_number}_{index}.png" so each can
            be traced back to its source document and page later.

    Pseudocode:
    1. Ensure output_dir exists (os.makedirs(output_dir, exist_ok=True)).
    2. pdf_stem = filename of pdf_path without extension.
    3. Open the PDF with fitz.open(pdf_path).
    4. For each page (with its page index):
        a. Call page.get_images(full=True) to list embedded image
           references (xrefs) on that page.
        b. For each xref (with an index counter):
            - Extract the raw image bytes and extension via
              doc.extract_image(xref) (returns a dict including "image"
              bytes and "ext").
            - Build the output filename:
              f"{pdf_stem}_p{page_index}_{index}.{ext}".
            - Write the bytes to os.path.join(output_dir, filename).
            - Append the full saved path to a results list.
    5. Close the document.
    6. Return the results list.
    """
    os.makedirs(output_dir, exist_ok=True)
    pdf_stem = os.path.splitext(os.path.basename(pdf_path))[0]

    saved_paths: List[str] = []

    doc = fitz.open(pdf_path)
    try:
        for page_index, page in enumerate(doc):
            image_refs = page.get_images(full=True)
            for img_index, img in enumerate(image_refs):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                ext = base_image["ext"]

                filename = f"{pdf_stem}_p{page_index}_{img_index}.{ext}"
                out_path = os.path.join(output_dir, filename)
                with open(out_path, "wb") as f:
                    f.write(image_bytes)

                saved_paths.append(out_path)
    finally:
        doc.close()

    return saved_paths
