# Issue: Pods has no true "repeater field group" — DiLIM's WordPress design needs to change

**Status:** confirmed, not yet fixed in code. This doc has everything a fresh
Claude session needs to pick up the fix without re-deriving the diagnosis.

## Project context

This is for **DiLIM** (Lab Manual Digitization), a two-stage pipeline:
1. `extraction/` — reads lab-manual PDFs, writes structured JSON + images to
   disk (`schema.py` defines `TextBlock`, `Section`, `Signatory`,
   `ManualDocument`).
2. `import_to_wp/` — reads that JSON and pushes it into WordPress via the
   REST API as draft `manual_document` posts, using **Pods** (a WordPress
   plugin) to define the custom post type and custom fields.

WordPress itself is hosted either locally via **LocalWP** (dev) or on an
**Oracle Cloud Always Free VM** (production) — that part is already solved
and documented in `README.md` / `deploy/oracle_cloud_setup.sh`, and is
**not** what this doc is about.

## The problem

The project's original design (in `schema.py`, `import_to_wp/document_importer.py`,
and the `README.md` Pods setup instructions) assumes a single `manual_document`
Pod with two **repeater fields**:

- `sections` — repeating rows of `{section_title, section_body, section_order}`
- `signatories` — repeating rows of `{signatory_name, signatory_title, signatory_image, signatory_order}`

**This is not possible in core Pods.** Verified two ways:

1. **Live UI screenshot** of the `manual_document` pod's Fields tab: the only
   controls are **"+ Add New Group"** (a *visual section* on the admin edit
   screen, not a repeater — e.g. groups fields under a heading like "More
   Fields") and **"Add Field"** (adds one individual field to a group). A
   field's own settings have a **"Repeatable"** tab, but it's a single
   checkbox that only repeats *that one field* (added in Pods 2.9 as "Simple
   Repeatable Fields") — it cannot bundle several different sub-fields
   (title + body + order) into one repeating row.
2. **Pods' own documentation and issue tracker** confirm this is a known,
   long-standing gap, not a version/configuration mistake on our end:
   - docs.pods.io's "Simple Repeatable Fields" page explicitly describes
     single-field repetition only.
   - An open GitHub discussion on `pods-framework/pods` titled
     **"Repeatable Field Groups"** asks for exactly this feature; a
     maintainer's suggested workaround is *"you can already do this by
     using a relationship."*
   - A "Repeatable Field Groups aka Loop Fields" idea is still open/unbuilt
     on Pods' own community roadmap site (friends.pods.io).
   - A paid add-on, **Panda Pods Repeater Field**, exists specifically to
     fill this gap — further confirming core Pods doesn't have it.

## Options considered

| Option | Cost | Codebase impact |
|---|---|---|
| A. Panda Pods Repeater Field add-on | Paid | Smallest code change, but introduces a paid dependency |
| **B. Model Section/Signatory as their own Pods (Custom Post Types), related to `manual_document` via Relationship fields** | **Free** | **Moderate — changes import payload shape and theme templates** |
| C. Switch from Pods to ACF Pro (has native Repeater field) | Paid | Would replace the whole Pods integration |

**Decision: Option B.** Free, stays within the project's existing "no-code,
Pods admin UI" philosophy for WordPress-side setup, and is the officially
suggested Pods-native workaround.

## Prescribed solution (Option B) — what to build

### New Pods structure (replaces the single `manual_document` repeater fields)

Instead of one pod, create **three**:

1. **`manual_document`** (existing, keep `doc_title`, `doc_number`, etc.)
   — add two **Relationship fields**:
   - `sections` → relationship to the `section` pod, multiple/unlimited,
     bidirectional not required.
   - `signatories` → relationship to the `signatory` pod, multiple/unlimited.
2. **`section`** (new Custom Post Type pod) with plain fields:
   - `section_title` (text)
   - `section_body` (rich text/HTML/WYSIWYG)
   - `section_order` (number)
3. **`signatory`** (new Custom Post Type pod) with plain fields:
   - `signatory_name` (text)
   - `signatory_title` (text)
   - `signatory_image` (media/file)
   - `signatory_order` (number)

`section` and `signatory` posts are pure data records, not pages anyone
browses directly — when creating these two pods in Pods admin, set them to
**not public** / excluded from search / no front-end single-post template
needed (they're only ever displayed *through* the parent `manual_document`
via the relationship field, per `wordpress_theme/single-manual_document.php`).
They still need **REST API enabled** (`show_in_rest` = true, with a
matching `rest_base`) so `import_to_wp/` can create them via the REST API.

### Changes needed in the Python import pipeline

`schema.py` — no change needed. `Section` and `Signatory` dataclasses, and
the shape of the extraction-side JSON, can stay exactly as they are; this is
purely an import-time/WordPress-side mapping change.

`import_to_wp/document_importer.py` — **rework the import order**. Currently
`build_fields_payload()` nests sections/signatories directly into one POST.
The new flow must be:

1. Upload all images first (existing `upload_all_images_for_document()` —
   unchanged).
2. For each `Section` in the doc, `POST wp/v2/section` with
   `{"title": ..., "status": "draft", "fields": {"section_title": ...,
   "section_body": ..., "section_order": ...}}` (need to confirm the exact
   post-title requirement / whether `section_title` alone suffices — Pods
   custom post types still have a native WP `post_title`, decide whether to
   duplicate `section_title` into it or just reuse it). Collect the
   resulting post IDs, in section order.
2. Do the same for each `Signatory` against `wp/v2/signatory`, substituting
   `signatory_image` with the already-uploaded media ID (same
   `image_id_map` pattern already used for the parent post).
3. `POST wp/v2/manual_document` with `fields.sections` and
   `fields.signatories` set to the **lists of post IDs** collected above
   (Pods Relationship fields accept an array of related post IDs via REST),
   instead of nested row objects.
4. On any failure partway through, the already-created `section`/`signatory`
   child posts for that document should not orphan silently — decide
   whether to leave them as unattached drafts for manual cleanup, or track
   them for deletion/rollback if the parent `manual_document` POST fails.
   (Minimum bar: log/print their IDs in the failure message so a human can
   clean up.)

`import_to_wp/wp_client.py` — no interface change needed; same `post()`
method works against `wp/v2/section` and `wp/v2/signatory` as it already
does against `wp/v2/manual_document`.

`import_to_wp/run_import.py`, `app.py` — no change expected beyond whatever
falls out of `document_importer.py`'s function signatures, but re-check call
sites after the rework.

### Changes needed in the WordPress theme

`wordpress_theme/single-manual_document.php` (already a prose spec, not
real code — see repo) needs its described behavior updated: instead of
"looping over the `sections` repeater field," it should describe looping
over the **related `section` posts** via the Relationship field (Pods'
`related()` / `->field('sections')` returns related post objects when it's
a Relationship field, not raw rows) — same idea, different Pods API shape
under the hood, but the tab-rendering behavior visible to a site visitor is
unchanged. Same for `signatories`.

### Changes needed in `README.md`

Replace the current "Step 2: Install the Pods plugin" instructions (which
say to add `sections`/`signatories` as repeater field groups on the single
`manual_document` pod) with:

1. Create the `manual_document` pod (as before).
2. Create the `section` pod (Custom Post Type, not public, REST-enabled)
   with its three plain fields.
3. Create the `signatory` pod (Custom Post Type, not public, REST-enabled)
   with its four plain fields.
4. On `manual_document`, add the two Relationship fields (`sections` →
   `section` pod, `signatories` → `signatory` pod), each allowing multiple
   related items.

Also update the field-map table/diagram in the "File map and import graph"
section of the README if `document_importer.py`'s responsibilities change
enough to be worth re-describing there.

## Open questions for whoever implements this

- Exact Pods REST API field name/shape for setting a Relationship field's
  value on create (confirm via a manual test: `GET` an existing pod's REST
  schema, or check Pods' REST API docs at docs.pods.io, before hardcoding
  the payload key — this project's `document_importer.py` already has a
  precedent comment flagging this same kind of uncertainty for the
  `fields` payload key itself).
- Whether `section`/`signatory` posts should be forcibly published
  (instead of `draft`) immediately, since they're invisible data leaves
  with no independent review step of their own — leaving them as `draft`
  might make them fail to appear in the parent's relationship field
  depending on Pods' relationship query defaults (drafts are sometimes
  excluded from relationship pickers/queries).
- Cleanup/rollback strategy for orphaned `section`/`signatory` posts if a
  `manual_document` import fails partway through (see step 4 above).

## Acceptance criteria for the fix

- `document_importer.py` creates `section`/`signatory` posts before the
  parent `manual_document` post, and wires their IDs into the parent's
  relationship fields.
- README's Pods setup steps describe 3 pods + 2 relationship fields, not
  2 repeater field groups on 1 pod.
- `wordpress_theme/single-manual_document.php`'s spec describes rendering
  via related posts, not repeater rows.
- No change to `schema.py`, `extraction/`, or the JSON shape written by
  the extraction pipeline — this is purely an import-side/WordPress-side
  fix.
