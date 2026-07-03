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

# Whether to verify the WordPress site's TLS certificate. Leave this at the
# default (true) for any real host, including the Oracle Cloud VM setup in
# the README, once it has a real Let's Encrypt certificate. Only set this to
# "false" in .env when pointing at a LocalWP (https://*.local) site whose
# self-signed certificate you have not added to your system's trust store -
# see the "Local development with LocalWP" section of the README.
WP_VERIFY_SSL = os.getenv("WP_VERIFY_SSL", "true").strip().lower() not in (
    "false",
    "0",
    "no",
)

# Must match the custom post type slug registered in WordPress via Pods
# (Pods Admin > Add New Pod > "manual_document").
WP_DOCUMENT_POST_TYPE = "manual_document"
