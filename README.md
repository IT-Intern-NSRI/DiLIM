# Lab Manual Digitization - Project Skeleton

This is a skeleton, not a finished project. Every function raises
`NotImplementedError` (or has a `// TODO`) and contains a docstring with
its input/output types and step-by-step pseudocode. Fill in the function
bodies according to the pseudocode and the pipeline works end to end -
no file structure or wiring should need to change.

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

This skeleton only covers the automatable half of the project (PDF ->
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

None of that is code this project can run for you - see the earlier
conversation for the full breakdown of what can be built here versus
what requires direct access to your live WordPress site.

## Setup

```
cd lab_manual_digitization
pip install -r requirements.txt
cp .env.example .env        # then fill in real values in .env
```

Put source PDFs in `input_pdfs/`, then run everything **from the
project root** (so the plain `import schema` / `import config` lines
resolve correctly):

```
python -m extraction.run_extraction
# review output_json/*.json and the printed confidence flags
python -m import_to_wp.run_import
```
