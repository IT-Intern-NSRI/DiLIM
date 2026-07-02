# Lab Manual Digitization (DiLIM)

This project turns scanned/authored lab-manual PDFs into structured
"Manual Document" posts on a WordPress site. Every function in this
repo is already implemented (no `NotImplementedError`/`TODO` stubs
remain) - the docstrings you'll see in the code are the original design
spec, kept in place as documentation of intent alongside the working
code.

## Two independent pipelines

1. **Extraction** (`extraction/`) - reads PDFs, writes JSON + images to
   local disk. Run this first, then have a human skim the JSON/flags.
2. **Import** (`import_to_wp/`) - reads that JSON, pushes it into a live
   WordPress site as draft posts via the REST API. Run this second, once
   the JSON has been reviewed.

They are separated deliberately so a bad extraction never touches your
live site directly - you always get a chance to review the intermediate
JSON files first.

## File map and import graph

```
config.py            <- constants + secrets (from .env), imported by nearly everything
schema.py             <- shared dataclasses (TextBlock, Section, Signatory, ManualDocument)

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
   -> extraction/run_extraction.py
   -> output_json/*.json + output_images/*.png
   -> [human review of confidence_flags]
   -> import_to_wp/run_import.py
   -> draft "Manual Document" posts on the live WordPress site
   -> [human review + publish in wp-admin]
   -> single-manual_document.php renders each one as a tabbed page
```

## What still needs to happen outside this codebase

This codebase only covers the automatable half of the project (PDF ->
structured content -> WordPress draft). It assumes:

- WordPress is already installed and reachable at `WP_BASE_URL`.
- The Pods plugin has been used (via its admin UI, no code) to create a
  "manual_document" custom post type with a "sections" repeater field
  group (section_title, section_body, section_order) and a
  "signatories" repeater field group (signatory_name, signatory_title,
  signatory_image, signatory_order).
- An Application Password has been generated for a WordPress account
  with permission to create posts and upload media.
- `wordpress_theme/*` files have been copied into the active theme's
  folder, and `mu-plugins/force-login.php` into `wp-content/mu-plugins/`.

None of that is code this project can run for you - it has to be done
by hand in wp-admin/your hosting control panel before the import
pipeline will work against a real site.

## Tutorial: running the pipeline step by step

This walks through both pipelines from a clean checkout, in order.
Steps 1-6 (extraction) only need Python and your PDFs - no WordPress
site required yet. Steps 7-11 (import) need a working WordPress site
that meets the prerequisites in the section above.

### 1. Get the code and move into the project root

```bash
cd DiLIM
```

All commands below assume you're standing in this folder, since
`config.py` and `schema.py` are imported as plain top-level modules
(`import config`, `import schema`) by files inside `extraction/` and
`import_to_wp/`. Running from anywhere else will break those imports.

### 2. Install Python dependencies

You need **Python 3.8+**. Install the packages listed in
`requirements.txt`:

```bash
pip install -r requirements.txt
```

This installs four packages - see "Do I need to install any packages?"
below for exactly what each one does and why the extraction pipeline
needs it.

### 3. Create your `.env` file

The pipeline reads all configuration (folder paths now, WordPress
credentials later) from environment variables via `config.py`, which
loads a local `.env` file with `python-dotenv`. Copy the template and
fill it in:

```bash
cp .env.example .env
```

For extraction only, you can leave the defaults as-is:

```
INPUT_PDF_DIR=./input_pdfs
OUTPUT_JSON_DIR=./output_json
OUTPUT_IMAGE_DIR=./output_images
```

Leave `WP_BASE_URL`, `WP_USERNAME`, and `WP_APP_PASSWORD` blank for now
- you only need those for the import step (Section 7 onward). Never
commit your real `.env` file.

### 4. Add source PDFs

Drop the lab manual PDFs you want to digitize into `input_pdfs/`:

```bash
cp /path/to/your/manuals/*.pdf input_pdfs/
```

Extraction quality depends on how the source PDFs are formatted:

- **Section headings** are detected either by font size (anything
  noticeably larger than the document's most common/body font size,
  scaled by `HEADING_FONT_SIZE_MULTIPLIER` in `config.py`, default
  `1.15`) or by short bold lines (fewer than ~12 words). PDFs whose
  headings are just larger/bolder text - not images - work best.
- **Bulleted/numbered lists** are recognized from leading markers
  (`-`, `•`, `1.`, `2)`, etc.) and converted to `<ul><li>` HTML.
- **Signatory blocks** ("Prepared by / Reviewed by / Approved by")
  need to be an actual extractable table (not a scanned image of a
  table) containing one of the keywords in
  `config.SIGNATORY_TABLE_KEYWORDS`, with a header row that has "Name"
  and "Title"/"Position" columns.
- **Images** (figures, diagrams, embedded signature images) are pulled
  out of the PDF's embedded image objects, whatever their format.

### 5. Run the extraction pipeline

From the project root:

```bash
python -m extraction.run_extraction
```

What happens, file by file:

1. `run_extraction.py` globs every `*.pdf` in `INPUT_PDF_DIR`.
2. For each PDF, `document_builder.build_document()` runs the full
   chain:
   - `pdf_text_extractor.extract_text_blocks_with_metadata()` opens the
     PDF with PyMuPDF and pulls every text span with its font size,
     bold flag, and page number.
   - `section_detector.split_into_sections()` uses those spans to
     figure out the body-text font size, decide which lines are
     headings, and split the rest into `Section` objects with
     HTML bodies.
   - `table_extractor.extract_all_tables()` / `find_signatory_table()`
     / `parse_signatories_from_table()` use pdfplumber to pull out
     tables and, if one looks like a signatory block, parse it into
     `Signatory` objects.
   - `image_extractor.extract_images()` saves every embedded image to
     `OUTPUT_IMAGE_DIR` as
     `{pdf_filename_stem}_p{page_number}_{index}.{ext}`.
   - A document title is derived from the PDF's filename, and
     `confidence_flags` are added if fewer than 2 sections were found
     or no signatory table was found.
3. The resulting `ManualDocument` is serialized to JSON and written to
   `OUTPUT_JSON_DIR/{pdf_filename_stem}.json`.
4. At the end, a summary prints how many PDFs were processed and lists
   every file that was flagged for manual review, with its flags.

Example output:

```
Processing ./input_pdfs/SOP-04-Autoclave.pdf...

Processed 1 PDF(s).
1 document(s) flagged for review:
  ./input_pdfs/SOP-04-Autoclave.pdf:
    - No signatory table found - verify manually.
```

### 6. Review the extracted JSON before touching WordPress

Open each file in `output_json/` and check:

- `doc_title` reads correctly.
- `sections` are split in sensible places, with the right titles and
  HTML bodies (no headings misfiled as body text or vice versa).
- `signatories` were parsed correctly, if the document had a
  signatory table.
- `extracted_image_paths` point to the images you expect in
  `output_images/`.
- `confidence_flags` - fix anything flagged here (or accept it and
  fix it manually in WordPress after import) before proceeding.

This human-review step is the entire reason extraction and import are
two separate scripts: nothing reaches your live site until you've
looked at this JSON.

### 7. Set up WordPress (outside this codebase)

Before running the import step, make sure all of this is done on the
live WordPress site (see "What still needs to happen outside this
codebase" above for detail):

1. WordPress is installed and reachable at the URL you'll put in
   `WP_BASE_URL`.
2. The **Pods** plugin is installed and used (via its admin UI) to
   create a `manual_document` custom post type with:
   - a `sections` repeater group: `section_title`, `section_body`,
     `section_order`
   - a `signatories` repeater group: `signatory_name`,
     `signatory_title`, `signatory_image`, `signatory_order`
3. An **Application Password** is generated for a WordPress user with
   permission to create posts and upload media: **Users > Profile >
   Application Passwords** in wp-admin.
4. Copy `wordpress_theme/*` into your active theme's folder (so
   `functions.php` enqueues `assets/tabs.css`/`assets/tabs.js`, and
   `single-manual_document.php` / `archive-manual_document.php` render
   the tabbed document pages and the browse/listing page).
5. Copy `mu-plugins/force-login.php` into `wp-content/mu-plugins/` on
   the live site.

### 8. Fill in your WordPress credentials in `.env`

```
WP_BASE_URL=https://your-lab-site.example.com
WP_USERNAME=your_admin_or_editor_username
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
```

Use the Application Password exactly as WordPress generates it
(spaces included) - don't substitute your normal account password.

### 9. Run the import pipeline

Once you're happy with the reviewed JSON in `output_json/`:

```bash
python -m import_to_wp.run_import
```

What happens, file by file:

1. `run_import.py` builds one authenticated `WPClient` (Basic Auth via
   your Application Password) and globs every `*.json` in
   `OUTPUT_JSON_DIR`.
2. For each JSON file, `document_importer.import_single_document()`:
   - Loads the JSON back into a dict.
   - `media_uploader.upload_all_images_for_document()` uploads every
     path in `extracted_image_paths` to `wp/v2/media` and builds a
     local-path -> WordPress-media-ID map.
   - `document_importer.build_fields_payload()` reshapes the sections
     and signatories into the Pods repeater field format, swapping any
     signature image path for its uploaded media ID.
   - `document_importer.create_document_post()` POSTs a new
     `manual_document` post with `status: "draft"` to
     `wp/v2/manual_document`.
3. Each success/failure is printed as it happens, and a summary prints
   at the end - failed documents don't stop the rest of the batch, so
   you can fix and re-run just the failed ones.

Example output:

```
Importing ./output_json/SOP-04-Autoclave.json...
  Created draft post (id=142).

Imported 1 of 1 document(s) successfully.
No failures.
```

> **Note:** `document_importer.py` sends field data under a `"fields"`
> key by convention. Confirm this matches your real site's REST API
> schema (Pods vs. Secure Custom Fields can differ) by `GET`ting an
> existing `manual_document` post and checking the response shape
> before your first real import run. Adjust `build_fields_payload()`'s
> output key if needed.

### 10. Review and publish in wp-admin

Every imported document lands as a **draft**, not published. In
wp-admin:

1. Open each new "Manual Document" draft.
2. Check the sections/signatories repeater fields rendered correctly
   and images attached properly.
3. Publish the ones that look right; fix and republish the rest.

### 11. View the published pages

Once published, `single-manual_document.php` renders each document as
a tabbed page (one tab per section, powered by `assets/tabs.js`/
`tabs.css`), and `archive-manual_document.php` renders the browse
listing of all manual documents.

### Quick reference: the two commands

```bash
python -m extraction.run_extraction   # PDFs -> JSON + images (local only)
python -m import_to_wp.run_import     # reviewed JSON -> WordPress drafts
```

## Do I need to install any packages for the extraction pipeline?

Yes. The extraction pipeline (`extraction/`) relies on two third-party
libraries, both listed in `requirements.txt` along with two more used
by the import pipeline:

```
PyMuPDF>=1.23.0      # imported as `fitz` - used by pdf_text_extractor.py
                      # and image_extractor.py to read text spans (with
                      # font size/bold metadata) and embedded images
                      # out of each PDF.
pdfplumber>=0.10.0    # used by table_extractor.py to detect and pull
                      # tables out of each PDF (for the signatory block).
requests>=2.31.0      # used by import_to_wp/wp_client.py to talk to the
                      # WordPress REST API. Not needed to just run
                      # extraction, but installing everything up front
                      # is simplest.
python-dotenv>=1.0.0  # used by config.py to load your .env file.
```

Install all four with:

```bash
pip install -r requirements.txt
```

If you only ever intend to run extraction and never the WordPress
import step, you technically only need `PyMuPDF`, `pdfplumber`, and
`python-dotenv` (config.py imports `dotenv` unconditionally, even
though only the import step uses the WordPress variables it loads) -
but there's no real downside to installing all four together.

Everything else the code imports (`json`, `os`, `glob`, `re`,
`base64`, `mimetypes`, `dataclasses`, `collections`, `typing`) is part
of the Python standard library and needs no installation - just a
reasonably recent Python 3 (3.8+, since the code uses standard
`dataclasses` and `typing` features available from that version on).
