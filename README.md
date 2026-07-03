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
pods-repeater-issue-and-fix.md  <- why sections/signatories are separate
                                    Pods Custom Post Types + Relationship
                                    fields instead of repeater fields

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
                            <- creates wp/v2/section and wp/v2/signatory
                               posts first, then wp/v2/manual_document
                               with "sections"/"signatories" set to the
                               lists of related post IDs (Pods
                               Relationship fields, not repeater rows -
                               see pods-repeater-issue-and-fix.md)
  run_import.py            imports: config, wp_client, document_importer  <- entry point

wordpress_theme/            <- lives in WordPress, not in this Python project
  functions.php             enqueues assets/tabs.css and assets/tabs.js
  single-manual_document.php  renders one document's tabs (reads Pods fields)
  archive-manual_document.php renders the document listing/browse page
  assets/tabs.css
  assets/tabs.js

mu-plugins/
  force-login.php          <- copy into wp-content/mu-plugins/ on the live site

deploy/
  oracle_cloud_setup.sh    <- run on a fresh Oracle Cloud Always Free VM to
                              install Nginx/MySQL/PHP/WordPress/Certbot
```

Data flow, end to end:

```
input_pdfs/*.pdf
   -> extraction/run_extraction.py  (or app.py's "Run extraction" button)
   -> output_json/*.json + output_images/*.png
   -> [human review of confidence_flags]
   -> import_to_wp/run_import.py  (or app.py's "Import approved documents" button)
   -> one wp/v2/section post per section, one wp/v2/signatory post per
      signatory (published), then a draft "Manual Document" post whose
      Relationship fields point at those posts' IDs
   -> [human review + publish in wp-admin]
   -> single-manual_document.php renders each one as a tabbed page
```

## Part 1: WordPress-side setup (one-time, mostly manual)

This project's two Python pipelines don't care where WordPress lives -
they only need a URL, a username, and an Application Password. This repo
covers two ways to get a running WordPress site to point them at:

- **LocalWP** - a free desktop app that runs a full WordPress site on
  your own machine in a few clicks. Good for developing/testing the
  theme in `wordpress_theme/` before anything is public, or for a lab
  that's fine keeping the manual on one shared computer.
- **Oracle Cloud "Always Free" tier** - a free-forever cloud VM you
  provision once, so the manual is reachable by every staff member from
  anywhere, not just one machine. `deploy/oracle_cloud_setup.sh`
  automates most of the server-side setup.

You don't have to pick just one - a common workflow is to build and test
everything against LocalWP first, then repeat the same WordPress-admin
steps (Pods, theme, Application Password) on the Oracle VM once you're
happy with it, and point `WP_BASE_URL` at whichever one you're currently
working against.

### Step 1a: Local WordPress with LocalWP (development/testing)

1. Download and install **LocalWP** (also just called "Local") from
   https://localwp.com - available for macOS, Windows, and Linux, free.
2. Click **+ Create a new site**, give it a name (e.g. "lab-manual"),
   and accept the defaults (PHP/MySQL/webserver versions) unless you
   have a reason not to.
3. Once it's running, LocalWP gives the site a local domain like
   `https://lab-manual.local` - this is what you'll use for
   `WP_BASE_URL` in Part 2 below.
4. LocalWP's certificate for `*.local` sites is self-signed, so your OS
   won't trust it by default. In LocalWP, open the site, go to the
   **SSL** tab, and click **Trust** - this adds the certificate to your
   system's trust store so both your browser and this project's Python
   code (`requests`) can verify it normally. If you'd rather skip that
   step, you can instead set `WP_VERIFY_SSL=false` in `.env`, but
   trusting the certificate is the safer option and only takes one
   click.
5. Continue with Step 2 below ("Install the Pods plugin...") using this
   site.

### Step 1b: Free permanent hosting with Oracle Cloud (Always Free tier)

Oracle Cloud's Always Free tier includes a small VM - and, on many
accounts, an Ampere A1 "ARM" shape with up to 4 OCPUs / 24 GB RAM - that
stays free indefinitely, not just for a trial period. That's enough to
comfortably run WordPress for a lab-sized audience.

1. **Create an Oracle Cloud account** at
   https://www.oracle.com/cloud/free/ (requires a credit card for
   identity verification, but Always Free resources are never billed).
2. **Create a Compute instance**:
   - Console > Compute > Instances > Create Instance.
   - Choose an **Always Free-eligible** shape - either the Ampere A1
     (ARM, larger free allowance) or `VM.Standard.E2.1.Micro` (x86,
     smaller). The console labels eligible shapes "Always Free".
   - Choose the **Ubuntu 22.04** image.
   - Add your SSH public key (or let the console generate one) so you
     can log in.
   - Create the instance and note its **public IP address**.
3. **Open ports 80 and 443** for the instance's subnet. This is a step
   in the OCI console, not on the VM itself, and is easy to miss:
   - Console > Networking > Virtual Cloud Networks > (your VCN) >
     (the subnet the instance is in) > Security Lists > (default
     security list).
   - Add Ingress Rules: source `0.0.0.0/0`, TCP, destination port `80`;
     and another for destination port `443`.
   - If the instance also has a Network Security Group attached, add
     the same two rules there too.
4. **SSH in and run the provisioning script**:
   ```
   ssh ubuntu@<the instance's public IP>
   # on the VM, get this repo's deploy/ folder onto it, e.g.:
   git clone <this repo's URL>
   cd DiLIM/deploy
   chmod +x oracle_cloud_setup.sh
   ./oracle_cloud_setup.sh your-domain.example.com
   ```
   This installs Nginx, MySQL, PHP-FPM, downloads WordPress core,
   creates the database, writes `wp-config.php`, configures the Nginx
   site, opens 80/443 in the VM's *local* firewall (separate from the
   console step above, and just as easy to forget), and installs
   Certbot. It prints the generated database password and a checklist
   of remaining manual steps at the end - read that output before
   continuing.

   If you don't have a domain yet, a free option is a dynamic-DNS
   hostname (e.g. from https://www.duckdns.org) pointed at the VM's
   public IP; pass that hostname to the script instead of a real domain.
5. **Point DNS at the VM**: an `A` record for your domain/DDNS hostname
   pointing at the instance's public IP, then wait for it to propagate.
6. **Issue a free TLS certificate**, once DNS resolves:
   ```
   sudo certbot --nginx -d your-domain.example.com
   ```
   A real certificate (not a self-signed one) is required for
   WordPress Application Passwords to work over the public internet -
   WordPress only allows them over plain HTTP for `localhost`.
7. Visit `https://your-domain.example.com/` and finish WordPress's own
   install wizard (site title, admin username/password).
8. Continue with Step 2 below ("Install the Pods plugin...") using this
   site. Once everything is set up, `WP_BASE_URL` in `.env` should be
   `https://your-domain.example.com` and `WP_VERIFY_SSL` should stay at
   its default, `true`.

### Step 2: Install the Pods plugin (Plugins > Add New > search "Pods")

> **Why three pods, not one:** Pods has no true "repeater field group" -
> the field-group repeater that this project originally assumed (one
> `sections` group and one `signatories` group, each with several
> sub-fields, repeating as a bundle) does not exist in core Pods. Pods
> only offers "Simple Repeatable Fields" (one field repeats *by itself*,
> not a whole group), plus a paid "Panda Pods Repeater Field" add-on for
> the real thing. The free, Pods-native workaround - and the one this
> project uses - is to give Section and Signatory their own Custom Post
> Type pods and relate them to `manual_document` with Relationship
> fields. See `pods-repeater-issue-and-fix.md` in this repo for the full
> diagnosis if you're curious why.

Using the Pods admin UI (no code required), create **three pods** in
this order:

1. **`manual_document`** - Custom Post Type, public (this is the page
   staff actually browse to). Fields:
   - `doc_number` (text)
   - any other top-level document fields you want (title/revision/date
     etc. - `doc_title` maps to the native WP post title, so it doesn't
     need its own Pods field).
   - `sections` - **Relationship** field, related pod = `section`,
     allow **multiple** related items (unlimited).
   - `signatories` - **Relationship** field, related pod = `signatory`,
     allow **multiple** related items (unlimited).

2. **`section`** - Custom Post Type. On the pod's **Advanced Options**
   tab, set **not public** and exclude it from search - these posts are
   pure data records, only ever displayed *through* a parent
   `manual_document` via the relationship field above, never browsed to
   directly (no single-post template needed). Fields:
   - `section_title` (text)
   - `section_body` (rich text/HTML/WYSIWYG)
   - `section_order` (number)

3. **`signatory`** - Custom Post Type, same **not public** / excluded-
   from-search setting as `section`. Fields:
   - `signatory_name` (text)
   - `signatory_title` (text)
   - `signatory_image` (media/file)
   - `signatory_order` (number)

**Turn on REST API access for all three pods** (this is what
`import_to_wp/` needs to POST to them - it's easy to miss because it's
not on the Advanced Options tab). For **each** of `manual_document`,
`section`, and `signatory`:
   - Open the pod in Pods Admin and click its own **REST API** tab
     (a top-level tab next to "Manage Fields," "Labels," and "Advanced
     Options" - not a checkbox buried inside another tab).
   - Click **Enable** to turn on REST API support for that content
     type. This exposes the standard `wp/v2/<pod name>` route (`section`
     -> `wp-json/wp/v2/section`, etc.) - the **REST Base** field that
     appears once enabled controls that route name and can stay as the
     pod's default.
   - Enabling the route alone does **not** expose the pod's own custom
     fields (`section_title`, `signatory_image`, etc.) through it - on
     the same tab, also check **"Show all fields in REST API"** (or, if
     you'd rather be selective, leave that off and instead open each
     individual field's own **REST API** sub-tab in the field editor and
     enable it there). Without this, POSTs to `fields.section_title` and
     friends will silently be ignored.

Then go back to **`manual_document`** and add the two Relationship
fields described in step 1 (`sections` -> `section` pod, `signatories`
-> `signatory` pod), if you haven't already - Pods needs the `section`
and `signatory` pods to exist first before you can point a Relationship
field at them.

### Step 3: Copy the theme files

Copy `wordpress_theme/` into your active theme's folder (so
`functions.php`, `single-manual_document.php`,
`archive-manual_document.php`, and `assets/` sit alongside your theme's
other files). If you don't want to touch an existing theme directly,
copy them into a child theme instead. (On LocalWP, the theme folder is
under the site's `app/public/wp-content/themes/` directory, reachable
via LocalWP's **Open site shell** button or by opening that folder
directly in Finder/Explorer. On the Oracle VM, it's under
`/var/www/wordpress/wp-content/themes/`, reachable over SSH/SFTP.)

### Step 4: Copy the force-login mu-plugin

Copy `mu-plugins/force-login.php` into `wp-content/mu-plugins/` on the
site. This forces login on all front-end pages, since the manual is
meant to be staff-only, not public.

### Step 5: Generate an Application Password

For a WordPress account that has permission to create posts and upload
media: in wp-admin, go to *Users > Profile > Application Passwords*,
give it a name (e.g. "lab-manual-import"), and click *Add New
Application Password*. Copy the generated password immediately -
WordPress only shows it once.

Note: WordPress only allows Application Passwords over plain HTTP for
`localhost`. LocalWP's sites are served over HTTPS by default so this
isn't an issue there; on the Oracle VM, make sure you've completed the
Certbot step (Step 1b.6 above) first, or Application Password
authentication will fail.

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
WP_VERIFY_SSL=true                                # false only for an untrusted LocalWP cert
```

Two concrete examples, depending which of Step 1a/1b you did:

```
# Pointing at a LocalWP site (Step 1a), certificate trusted via LocalWP's SSL tab:
WP_BASE_URL=https://lab-manual.local
WP_VERIFY_SSL=true

# Pointing at a LocalWP site, certificate NOT trusted:
WP_BASE_URL=https://lab-manual.local
WP_VERIFY_SSL=false

# Pointing at the Oracle Cloud VM (Step 1b), after Certbot has issued a real cert:
WP_BASE_URL=https://labname.duckdns.org
WP_VERIFY_SSL=true
```

`app.py`'s sidebar has the same `WP_VERIFY_SSL` toggle if you'd rather
switch it per-session instead of editing `.env`.

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

- **Import fails partway through with "Created N section/signatory
  post(s) ... but failed to create the parent manual_document post"**:
  the `section`/`signatory` child posts for that document were already
  created on the live site before the failure, and now have no parent -
  the error message lists their `post_type/id` pairs. Either delete them
  by hand in wp-admin (they're `publish`-status but not public, so they
  won't show up in the normal post list - use *Pods Admin > Edit Section*
  / *Edit Signatory*, or `wp/v2/section/<id>` with `DELETE` via
  `WPClient.delete()`), or fix the underlying cause and re-run the import
  for that one document (this will create a fresh set of children rather
  than reusing the orphans, so clean up the old ones either way).
- **A document's tabs/signature block are empty on the front end even
  though the import reported success**: this is almost always the
  `config.WP_CHILD_POST_STATUS` / relationship-query issue, not REST -
  if a `section`/`signatory` post ended up `draft` (e.g. you changed
  `WP_CHILD_POST_STATUS`), Pods' relationship query can silently exclude
  drafts, so the parent renders with no tabs and no obvious error.
  Double-check the child posts' status in wp-admin if this happens.
- **`POST wp/v2/section` (or `signatory`) succeeds but `section_title`/
  `signatory_image`/etc. don't actually save**: the pod's REST API route
  is enabled but its fields aren't exposed for writing through it. On
  that pod's own **REST API** tab in Pods Admin, check **"Show all
  fields in REST API"** (or enable each field individually on its own
  REST API sub-tab in the field editor) - see Step 2 above.
- **A `POST` to `wp/v2/section`, `wp/v2/signatory`, or
  `wp/v2/manual_document` returns 404 or "rest_no_route"**: that pod's
  REST API support itself isn't enabled yet. Open the pod in Pods Admin,
  go to its own **REST API** tab (not Advanced Options), and click
  **Enable** - see Step 2 above.

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
- **`SSLCertVerificationError` / `CERTIFICATE_VERIFY_FAILED` when
  importing**: you're pointed at a LocalWP site whose self-signed
  certificate isn't trusted yet. Either click **Trust** in LocalWP's SSL
  tab for that site (recommended), or set `WP_VERIFY_SSL=false` in
  `.env` (or uncheck "Verify SSL certificate" in `app.py`'s sidebar).
  Don't do this against a real public site.
- **Can't reach the Oracle Cloud VM at all (connection times out)**:
  almost always the port-opening step was missed or incomplete - check
  *both* places, since either one alone will still block traffic: the
  VCN's Security List/NSG in the OCI console (Step 1b.3), and the VM's
  own iptables rules (handled by `deploy/oracle_cloud_setup.sh`, but
  worth re-checking with `sudo iptables -L -n` if you changed anything
  by hand afterwards).
- **`certbot --nginx` fails with a DNS/validation error**: DNS hasn't
  propagated yet, or the `A` record doesn't point at the VM's current
  public IP. Check with `dig your-domain.example.com` and retry once it
  resolves correctly; propagation can take anywhere from a few minutes
  to a few hours depending on your DNS provider's TTL.
- **Application Password requests fail on the Oracle VM but work on
  LocalWP**: WordPress requires HTTPS for Application Passwords on any
  non-`localhost` site. Make sure Certbot has successfully issued a
  certificate (Step 1b.6) and `WP_BASE_URL` uses `https://`, not
  `http://`.
