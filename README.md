# Lab Manual Digitization

Converts a lab's paper/PDF SOP manuals into structured content and imports
it into a staff-only WordPress site as draft posts, ready for a human to
review and publish.

## Two independent pipelines

1. **Extraction** (`extraction/`) - reads PDFs, writes JSON + images to
   local disk. Run this first, then have a human skim the JSON/flags.
2. **Import** (`import_to_wp/`) - reads that JSON, pushes it into a live
   WordPress site as draft posts via the REST API. Run this second, once
   the JSON has been reviewed.

They are separated deliberately so a bad extraction never touches your
live site directly - you always get a chance to review the intermediate
JSON files first. `app.py` (see below) wraps both pipelines in a UI but
doesn't change this separation - it still extracts to disk first and
only imports what you've approved.

## File map and import graph

```
config.py            <- constants + secrets (from .env), imported by nearly everything
schema.py             <- shared dataclasses (TextBlock, Section, Signatory, ManualDocument)
app.py                 <- optional local Streamlit UI, imports both pipelines directly

extraction/
  pdf_text_extractor.py   imports: schema
  section_detector.py     imports: schema, config
  table_extractor.py      imports: schema, config
  image_extractor.py      imports: (no local imports)
  document_builder.py     imports: schema, pdf_text_extractor, section_detector,
                                    table_extractor, image_extractor
  run_extraction.py       imports: config, document_builder            <- entry point

import_to_wp/
  wp_client.py             imports: (no local imports)
  media_uploader.py        imports: wp_client
  document_importer.py     imports: config, wp_client, media_uploader
  run_import.py            imports: config, wp_client, document_importer  <- entry point

wordpress_theme/            <- lives in WordPress, not in this Python project
  functions.php             enqueues assets/tabs.css and assets/tabs.js
  single-manual_document.php  renders one document's tabs (reads Pods fields)
  archive-manual_document.php renders the document listing/browse page
  assets/tabs.css
  assets/tabs.js

mu-plugins/
  force-login.php          <- copy into wp-content/mu-plugins/ on the live site
```

Data flow, end to end:

```
input_pdfs/*.pdf
   -> extraction/run_extraction.py  (or app.py's "Run extraction" button)
   -> output_json/*.json + output_images/*.png
   -> [human review of confidence_flags]
   -> import_to_wp/run_import.py  (or app.py's "Import approved documents" button)
   -> draft "Manual Document" posts on the live WordPress site
   -> [human review + publish in wp-admin]
   -> single-manual_document.php renders each one as a tabbed page
```

## Part 1: WordPress-side setup (one-time, manual, no code)

This project pushes content into WordPress but does not stand up
WordPress itself. Before running anything here, on the target site:

1. **Install WordPress** and make sure it's reachable at the URL you'll
   use for `WP_BASE_URL` (e.g. `https://labname.university.edu`).
2. **Install the Pods plugin** (Plugins > Add New > search "Pods").
   Using its admin UI (no code required):
   - Create a custom post type with the slug **`manual_document`**.
   - Add a **`sections`** repeater field group with sub-fields:
     `section_title` (text), `section_body` (rich text/HTML),
     `section_order` (number).
   - Add a **`signatories`** repeater field group with sub-fields:
     `signatory_name` (text), `signatory_title` (text),
     `signatory_image` (media/file), `signatory_order` (number).
3. **Copy the theme files** in `wordpress_theme/` into your active
   theme's folder (so `functions.php`, `single-manual_document.php`,
   `archive-manual_document.php`, and `assets/` sit alongside your
   theme's other files). If you don't want to touch an existing theme
   directly, copy them into a child theme instead.
4. **Copy `mu-plugins/force-login.php`** into `wp-content/mu-plugins/`
   on the live site. This forces login on all front-end pages, since the
   manual is meant to be staff-only, not public.
5. **Generate an Application Password** for a WordPress account that has
   permission to create posts and upload media: in wp-admin, go to
   *Users > Profile > Application Passwords*, give it a name (e.g.
   "lab-manual-import"), and click *Add New Application Password*.
   Copy the generated password immediately - WordPress only shows it once.

Once these five steps are done, the site is ready to receive imported
drafts, and the rest of this README is about the Python side.

## Part 2: Local pipeline setup

Requires Python 3.9+ (uses `dataclasses` and modern type hints).

```
cd lab_manual_digitization
pip install -r requirements.txt
cp .env.example .env
```

Then edit `.env` and fill in the values from Part 1:

```
INPUT_PDF_DIR=./input_pdfs
OUTPUT_JSON_DIR=./output_json
OUTPUT_IMAGE_DIR=./output_images

WP_BASE_URL=https://labname.university.edu
WP_USERNAME=your_wordpress_username
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx     # from step 5 above, spaces included
```

`INPUT_PDF_DIR`/`OUTPUT_JSON_DIR`/`OUTPUT_IMAGE_DIR` already default to
`input_pdfs/`, `output_json/`, `output_images/` if you leave them out of
`.env` - those three folders already exist (empty) in this project.

**Everything below must be run from the project root** (the folder
containing `config.py`), so that `import config` / `import schema`
resolve correctly.

## Part 3: Running it - command line

```
# 1. Put your PDFs in input_pdfs/, then extract:
python -m extraction.run_extraction

# 2. Review output. Two things to check:
#    - the "flagged for review" summary printed to the terminal
#    - the actual content of output_json/*.json for each document
#      (especially any document listed as flagged)

# 3. Once you're satisfied with the JSON, import to WordPress:
python -m import_to_wp.run_import
```

`run_import.py` creates every document in `output_json/` as a **draft**
post - nothing goes live automatically. Log into wp-admin, review each
draft under *Manual Documents*, and publish the ones that are correct.
If a document's extraction was bad, fix the source PDF (or manually edit
the JSON) and re-run extraction/import for just that file rather than
publishing something wrong.

## Part 3 (alternative): Running it - local UI

`app.py` wraps both pipelines in a single-user, local-only Streamlit UI
as an alternative to the two commands above:

```
streamlit run app.py
```

This opens a browser tab where you can:
1. Upload PDF(s) (saved into `input_pdfs/`, same as the CLI).
2. Click **Run extraction**.
3. Review each document: its confidence flags are shown as warnings, and
   an **Approve for import** checkbox is pre-checked for documents with
   no flags and unchecked for flagged ones. A "View raw JSON" expander
   shows the same data the CLI writes to `output_json/`.
4. Fill in the WordPress connection fields in the sidebar (pre-filled
   from `.env` if you already set one up).
5. Click **Import approved documents** - only checked documents are
   sent to WordPress as drafts; anything left unchecked is skipped.

This UI is intentionally minimal (no auth, no multi-user support, no
in-browser editing of extracted content) since it's meant for one person
running it on their own machine. It is **not** designed to be exposed on
a network or used by multiple people concurrently - if the lab later
wants a shared, multi-user tool, this would need a real backend (job
queue, per-user access control, and likely a small database instead of
the flat `output_json/` folder) rather than just deploying this
Streamlit app as-is.

## Troubleshooting

- **`ModuleNotFoundError` for `config` or `schema`**: you're not running
  from the project root. `cd` into the folder containing `config.py` first.
- **Import step fails immediately**: double-check `WP_BASE_URL` has no
  trailing slash issues, `WP_APP_PASSWORD` was copied with spaces intact,
  and the WordPress user has permission to create posts/upload media.
- **A document is flagged "Few or no sections detected"**: usually means
  the source PDF's headings aren't meaningfully larger/bolder than body
  text, so `HEADING_FONT_SIZE_MULTIPLIER` in `config.py` isn't catching
  them - inspect the PDF's actual font sizes, or adjust that constant.
- **A document is flagged "No signatory table found"**: the PDF's
  sign-off table doesn't contain any of `SIGNATORY_TABLE_KEYWORDS` in
  `config.py` - either the table uses different wording, or the PDF
  doesn't have one; check manually.
