"""
Turns one extracted document's JSON into a WordPress "Manual Document"
draft post, with its Sections and Signatories repeater fields populated
and images already swapped for their uploaded media IDs.
"""

import json
from typing import Dict

import config
from import_to_wp.wp_client import WPClient
from import_to_wp.media_uploader import upload_all_images_for_document


def build_fields_payload(doc_dict: dict, image_id_map: Dict[str, int]) -> dict:
    """
    Input: doc_dict (dict) - one document's parsed JSON from the
           extraction step.
           image_id_map (Dict[str, int]) - local image path -> WordPress
           media ID, from upload_all_images_for_document().
    Output: dict - the field payload shaped exactly as the "Manual
            Document" post type (built with Pods) expects it: a
            "sections" repeater (title, body, order per row) and a
            "signatories" repeater (name, title, signature image media
            ID, order per row).

    Pseudocode:
    1. sections_payload = []; for each section in doc_dict["sections"]:
       append {"section_title": section["title"],
       "section_body": section["body_html"],
       "section_order": section["order"]}.
    2. signatories_payload = []; for each sig in doc_dict["signatories"]:
       append {"signatory_name": sig["name"],
       "signatory_title": sig["title"],
       "signatory_image": image_id_map.get(sig.get("signature_image_path")),
       "signatory_order": sig["order"]}.
    3. Return {"sections": sections_payload,
       "signatories": signatories_payload,
       "doc_number": doc_dict.get("doc_number")}.
    """
    sections_payload = []
    for section in doc_dict["sections"]:
        sections_payload.append({
            "section_title": section["title"],
            "section_body": section["body_html"],
            "section_order": section["order"],
        })

    signatories_payload = []
    for sig in doc_dict["signatories"]:
        signatories_payload.append({
            "signatory_name": sig["name"],
            "signatory_title": sig["title"],
            "signatory_image": image_id_map.get(sig.get("signature_image_path")),
            "signatory_order": sig["order"],
        })

    return {
        "sections": sections_payload,
        "signatories": signatories_payload,
        "doc_number": doc_dict.get("doc_number"),
    }


def create_document_post(client: WPClient, doc_dict: dict, image_id_map: Dict[str, int]) -> int:
    """
    Input: client (WPClient) - authenticated API client.
           doc_dict (dict) - one document's parsed JSON.
           image_id_map (Dict[str, int]) - from
           upload_all_images_for_document().
    Output: int - the newly created WordPress post ID. The post is
            created with status "draft" so a human reviews/publishes it
            rather than it going live automatically.

    Pseudocode:
    1. fields = build_fields_payload(doc_dict, image_id_map).
    2. payload = {"title": doc_dict["doc_title"], "status": "draft",
       "fields": fields}.
       (Note: the exact key that carries custom field data depends on
       whether Pods or Secure Custom Fields is installed - confirm the
       real key name against the live site's REST API schema, e.g. by
       GETting an existing post, before wiring this up for real.)
    3. response = client.post(f"wp/v2/{config.WP_DOCUMENT_POST_TYPE}", payload).
    4. Return response["id"].
    """
    fields = build_fields_payload(doc_dict, image_id_map)
    payload = {
        "title": doc_dict["doc_title"],
        "status": "draft",
        "fields": fields,
    }
    response = client.post(f"wp/v2/{config.WP_DOCUMENT_POST_TYPE}", payload)
    return response["id"]


def import_single_document(client: WPClient, json_path: str) -> int:
    """
    Input: client (WPClient) - authenticated API client.
           json_path (str) - path to one document's JSON file (an output
           of the extraction pipeline).
    Output: int - the created WordPress post ID.

    Pseudocode:
    1. Open json_path and json.load() its contents into doc_dict.
    2. image_id_map = upload_all_images_for_document(client, doc_dict).
    3. post_id = create_document_post(client, doc_dict, image_id_map).
    4. Return post_id.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        doc_dict = json.load(f)

    image_id_map = upload_all_images_for_document(client, doc_dict)
    post_id = create_document_post(client, doc_dict, image_id_map)
    return post_id
