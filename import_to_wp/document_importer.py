"""
Turns one extracted document's JSON into a WordPress "Manual Document"
draft post, plus its "section" and "signatory" child posts.

Historical note: the original design here nested sections/signatories
directly into the manual_document POST as repeater-field rows. That
turned out not to be possible in core Pods (no true "repeater field
group" - see pods-repeater-issue-and-fix.md for the full diagnosis).
The fix (Option B from that doc): section and signatory are now their
own Custom Post Type pods, related to manual_document via Relationship
fields. So importing one document now means creating several posts, in
this order:
  1. images (unchanged - upload_all_images_for_document())
  2. one wp/v2/section post per Section
  3. one wp/v2/signatory post per Signatory
  4. one wp/v2/manual_document post, whose "sections"/"signatories"
     fields are the lists of post IDs created in steps 2-3.
"""

import json
from typing import Dict, List, Tuple

import config
from import_to_wp.wp_client import WPClient
from import_to_wp.media_uploader import upload_all_images_for_document


class DocumentImportError(Exception):
    """
    Raised when a manual_document import fails partway through, after at
    least one child (section/signatory) post was already created on the
    live site. Carries the child post type/ID pairs that were created so
    far, so the caller can log them (or attempt cleanup) rather than
    losing track of the orphans.
    """

    def __init__(self, message: str, orphaned_child_posts: List[Tuple[str, int]]):
        super().__init__(message)
        self.orphaned_child_posts = orphaned_child_posts


def build_section_payload(section: dict) -> dict:
    """
    Input: section (dict) - one entry from doc_dict["sections"], shaped
           like schema.Section ({"title", "body_html", "order"}).
    Output: dict - the REST payload for creating one wp/v2/section post.

    Pseudocode:
    1. Reuse section["title"] as the native WP post_title too (so the
       post is identifiable in wp-admin's post list by more than an ID),
       in addition to setting the Pods "section_title" field.
    2. fields = {"section_title": section["title"],
       "section_body": section["body_html"],
       "section_order": section["order"]}.
    3. Return {"title": section["title"], "status":
       config.WP_CHILD_POST_STATUS, "fields": fields}.
    """
    fields = {
        "section_title": section["title"],
        "section_body": section["body_html"],
        "section_order": section["order"],
    }
    return {
        "title": section["title"],
        "status": config.WP_CHILD_POST_STATUS,
        "fields": fields,
    }


def build_signatory_payload(sig: dict, image_id_map: Dict[str, int]) -> dict:
    """
    Input: sig (dict) - one entry from doc_dict["signatories"], shaped
           like schema.Signatory ({"name", "title", "order",
           "signature_image_path"}).
           image_id_map (Dict[str, int]) - local image path -> WordPress
           media ID, from upload_all_images_for_document().
    Output: dict - the REST payload for creating one wp/v2/signatory
            post.

    Pseudocode:
    1. Reuse sig["name"] as the native WP post_title.
    2. fields = {"signatory_name": sig["name"], "signatory_title":
       sig["title"], "signatory_image":
       image_id_map.get(sig.get("signature_image_path")),
       "signatory_order": sig["order"]}.
    3. Return {"title": sig["name"], "status":
       config.WP_CHILD_POST_STATUS, "fields": fields}.
    """
    fields = {
        "signatory_name": sig["name"],
        "signatory_title": sig["title"],
        "signatory_image": image_id_map.get(sig.get("signature_image_path")),
        "signatory_order": sig["order"],
    }
    return {
        "title": sig["name"],
        "status": config.WP_CHILD_POST_STATUS,
        "fields": fields,
    }


def create_section_posts(client: WPClient, doc_dict: dict) -> List[int]:
    """
    Input: client (WPClient) - authenticated API client.
           doc_dict (dict) - one document's parsed JSON.
    Output: List[int] - the created wp/v2/section post IDs, in the same
            order as doc_dict["sections"] (which is expected to already
            be in section_order, per the extraction pipeline).

    Pseudocode:
    1. ids = [].
    2. For each section in doc_dict["sections"]:
        a. payload = build_section_payload(section).
        b. response = client.post(f"wp/v2/{config.WP_SECTION_POST_TYPE}",
           payload).
        c. ids.append(response["id"]).
    3. Return ids.
    """
    ids: List[int] = []
    for section in doc_dict["sections"]:
        payload = build_section_payload(section)
        response = client.post(f"wp/v2/{config.WP_SECTION_POST_TYPE}", payload)
        ids.append(response["id"])
    return ids


def create_signatory_posts(client: WPClient, doc_dict: dict, image_id_map: Dict[str, int]) -> List[int]:
    """
    Input: client (WPClient) - authenticated API client.
           doc_dict (dict) - one document's parsed JSON.
           image_id_map (Dict[str, int]) - from
           upload_all_images_for_document().
    Output: List[int] - the created wp/v2/signatory post IDs, in the
            same order as doc_dict["signatories"].

    Pseudocode:
    1. ids = [].
    2. For each sig in doc_dict["signatories"]:
        a. payload = build_signatory_payload(sig, image_id_map).
        b. response = client.post(f"wp/v2/{config.WP_SIGNATORY_POST_TYPE}",
           payload).
        c. ids.append(response["id"]).
    3. Return ids.
    """
    ids: List[int] = []
    for sig in doc_dict["signatories"]:
        payload = build_signatory_payload(sig, image_id_map)
        response = client.post(f"wp/v2/{config.WP_SIGNATORY_POST_TYPE}", payload)
        ids.append(response["id"])
    return ids


def build_document_fields_payload(doc_dict: dict, section_ids: List[int], signatory_ids: List[int]) -> dict:
    """
    Input: doc_dict (dict) - one document's parsed JSON.
           section_ids (List[int]) - wp/v2/section post IDs, from
           create_section_posts().
           signatory_ids (List[int]) - wp/v2/signatory post IDs, from
           create_signatory_posts().
    Output: dict - the field payload for the parent manual_document post.
            "sections"/"signatories" are now Pods Relationship fields, so
            they take a plain list of related post IDs rather than
            nested row objects.

    Pseudocode:
    1. Return {"sections": section_ids, "signatories": signatory_ids,
       "doc_number": doc_dict.get("doc_number")}.
    """
    return {
        "sections": section_ids,
        "signatories": signatory_ids,
        "doc_number": doc_dict.get("doc_number"),
    }


def create_document_post(client: WPClient, doc_dict: dict, image_id_map: Dict[str, int]) -> int:
    """
    Input: client (WPClient) - authenticated API client.
           doc_dict (dict) - one document's parsed JSON.
           image_id_map (Dict[str, int]) - from
           upload_all_images_for_document().
    Output: int - the newly created parent WordPress post ID. The post
            is created with status "draft" so a human reviews/publishes
            it rather than it going live automatically. (Its
            section/signatory children are created "publish"/
            config.WP_CHILD_POST_STATUS beforehand - see
            config.WP_CHILD_POST_STATUS for why.)

    Raises: DocumentImportError if section/signatory child posts were
            created but the parent manual_document POST then failed -
            the exception carries the (post_type, id) pairs of the
            already-created children so run_import.py/app.py can log
            them for manual cleanup instead of losing track of the
            orphans.

    Pseudocode:
    1. section_ids = create_section_posts(client, doc_dict).
    2. signatory_ids = create_signatory_posts(client, doc_dict,
       image_id_map).
    3. fields = build_document_fields_payload(doc_dict, section_ids,
       signatory_ids).
    4. payload = {"title": doc_dict["doc_title"], "status": "draft",
       "fields": fields}.
       (Note: the exact key that carries custom field data - "fields" -
       and the exact shape Pods expects for a Relationship field's value
       on create should be confirmed against the live site's REST API
       schema before relying on this for real, per the open question in
       pods-repeater-issue-and-fix.md.)
    5. Try: response = client.post(f"wp/v2/{config.WP_DOCUMENT_POST_TYPE}",
       payload); return response["id"].
       Except Exception: raise DocumentImportError, attaching the
       (post_type, id) pairs from steps 1-2 so the caller can log/clean
       them up - do not let them disappear silently.
    """
    orphaned_child_posts: List[Tuple[str, int]] = []

    section_ids = create_section_posts(client, doc_dict)
    orphaned_child_posts.extend((config.WP_SECTION_POST_TYPE, pid) for pid in section_ids)

    signatory_ids = create_signatory_posts(client, doc_dict, image_id_map)
    orphaned_child_posts.extend((config.WP_SIGNATORY_POST_TYPE, pid) for pid in signatory_ids)

    fields = build_document_fields_payload(doc_dict, section_ids, signatory_ids)
    payload = {
        "title": doc_dict["doc_title"],
        "status": "draft",
        "fields": fields,
    }

    try:
        response = client.post(f"wp/v2/{config.WP_DOCUMENT_POST_TYPE}", payload)
    except Exception as e:
        orphan_list = ", ".join(f"{ptype}/{pid}" for ptype, pid in orphaned_child_posts)
        raise DocumentImportError(
            f"Created {len(orphaned_child_posts)} section/signatory post(s) "
            f"({orphan_list}) but failed to create the parent manual_document "
            f"post: {e}. These are now orphaned - clean them up manually in "
            f"wp-admin, or via WPClient.delete().",
            orphaned_child_posts,
        ) from e

    return response["id"]


def import_single_document(client: WPClient, json_path: str) -> int:
    """
    Input: client (WPClient) - authenticated API client.
           json_path (str) - path to one document's JSON file (an output
           of the extraction pipeline).
    Output: int - the created parent WordPress post ID.

    Pseudocode:
    1. Open json_path and json.load() its contents into doc_dict.
    2. image_id_map = upload_all_images_for_document(client, doc_dict).
    3. post_id = create_document_post(client, doc_dict, image_id_map).
    4. Return post_id.

    Note: DocumentImportError (raised by create_document_post if the
    parent post fails after children were already created) is allowed to
    propagate up - run_import.py/app.py already catch generic
    Exceptions per-document and print/display the message, and
    DocumentImportError's message already includes the orphaned child
    post count so nothing is lost by not special-casing it here.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        doc_dict = json.load(f)

    image_id_map = upload_all_images_for_document(client, doc_dict)
    post_id = create_document_post(client, doc_dict, image_id_map)
    return post_id
