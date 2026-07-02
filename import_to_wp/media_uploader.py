"""
Uploads locally-extracted images to the WordPress media library so they
can be referenced by ID inside Section and Signatory fields.
"""

import os
from typing import Dict

from import_to_wp.wp_client import WPClient


def upload_image(client: WPClient, image_path: str) -> int:
    """
    Input: client (WPClient) - authenticated API client.
           image_path (str) - local path to one extracted image file.
    Output: int - the WordPress media attachment ID for the now-uploaded
            image.

    Pseudocode:
    1. filename = os.path.basename(image_path).
    2. response = client.post_file("wp/v2/media", image_path, filename).
    3. Return response["id"].
    """
    filename = os.path.basename(image_path)
    response = client.post_file("wp/v2/media", image_path, filename)
    return response["id"]


def upload_all_images_for_document(client: WPClient, doc_dict: dict) -> Dict[str, int]:
    """
    Input: client (WPClient) - authenticated API client.
           doc_dict (dict) - one document's parsed JSON (from the
           extraction step), containing "extracted_image_paths": List[str].
    Output: Dict[str, int] - mapping of local image path -> WordPress
            media ID, so document_importer.py can substitute the correct
            media ID wherever that image is referenced.

    Pseudocode:
    1. path_to_id = {}.
    2. For each path in doc_dict.get("extracted_image_paths", []):
        a. media_id = upload_image(client, path).
        b. path_to_id[path] = media_id.
    3. Return path_to_id.
    """
    path_to_id: Dict[str, int] = {}

    for path in doc_dict.get("extracted_image_paths", []):
        media_id = upload_image(client, path)
        path_to_id[path] = media_id

    return path_to_id
