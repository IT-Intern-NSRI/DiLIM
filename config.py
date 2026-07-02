"""
Central configuration for the whole pipeline. Every other file imports
from here rather than hardcoding paths, keywords, or credentials.
No functions to implement in this file - it is just constants.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Extraction settings ---
INPUT_PDF_DIR = os.getenv("INPUT_PDF_DIR", "./input_pdfs")
OUTPUT_JSON_DIR = os.getenv("OUTPUT_JSON_DIR", "./output_json")
OUTPUT_IMAGE_DIR = os.getenv("OUTPUT_IMAGE_DIR", "./output_images")

# Multiplier applied to the detected "body text" font size to decide what
# counts as a section heading. e.g. if body text is 11pt, a line must be
# at least 11 * 1.15 pt to be treated as a heading.
HEADING_FONT_SIZE_MULTIPLIER = 1.15

# Keywords used to identify which extracted table (if any) is the
# signatory block, e.g. a "Prepared by / Reviewed by / Approved by" table.
SIGNATORY_TABLE_KEYWORDS = ["prepared by", "reviewed by", "approved by", "signature"]

# --- WordPress import settings ---
WP_BASE_URL = os.getenv("WP_BASE_URL")
WP_USERNAME = os.getenv("WP_USERNAME")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD")

# Must match the custom post type slug registered in WordPress via Pods
# (Pods Admin > Add New Pod > "manual_document").
WP_DOCUMENT_POST_TYPE = "manual_document"
