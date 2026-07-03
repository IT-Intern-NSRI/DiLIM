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

# Must match the custom post type slugs registered in WordPress via Pods.
# NOTE: as of the "no true repeater field group in core Pods" fix (see
# pods-repeater-issue-and-fix.md), sections/signatories are no longer
# nested repeater rows on manual_document - they are their own Custom
# Post Type pods, related to manual_document via Relationship fields.
# So there are three post types now, not one:
#   manual_document  - Pods Admin > Add New Pod > "manual_document"
#   section          - Pods Admin > Add New Pod > "section"
#   signatory        - Pods Admin > Add New Pod > "signatory"
WP_DOCUMENT_POST_TYPE = "manual_document"
WP_SECTION_POST_TYPE = "section"
WP_SIGNATORY_POST_TYPE = "signatory"

# Status to create section/signatory child posts with. These posts are
# pure data records (never browsed directly - see README), so there's no
# separate human review step for them the way there is for the parent
# manual_document draft. They are created as "publish" rather than
# "draft" because Pods relationship-field queries can exclude draft posts
# by default, which would make a freshly-imported document's tabs/
# signature block render empty until someone manually published each
# child post. The parent manual_document post itself still stays "draft"
# (see document_importer.create_document_post) so a human reviews/
# publishes the document as a whole before it's visible to lab staff.
WP_CHILD_POST_STATUS = "publish"
