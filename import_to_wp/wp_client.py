"""
Thin wrapper around the WordPress REST API using Application Password
authentication. Every import script talks to WordPress exclusively
through this class - nothing else in the project should call
`requests` directly against the WP site.
"""

import base64
import mimetypes
from typing import Any, Dict, Optional

import requests


class WPClient:
    """
    Input (constructor): base_url, username, app_password (all str).
    Represents one authenticated connection to a WordPress site's REST API.
    """

    def __init__(self, base_url: str, username: str, app_password: str):
        """
        Input: base_url (str) - the site's root URL, e.g.
               "https://labname.university.edu" (no trailing slash).
               username (str) - the WordPress account username used to
               generate the Application Password.
               app_password (str) - the Application Password string
               generated from WordPress admin (Users > Profile >
               Application Passwords).
        Output: None (constructor). Sets self.base_url and a
                self.session (requests.Session) pre-configured with the
                Basic Auth header built from username:app_password.

        Pseudocode:
        1. Store base_url with any trailing slash stripped.
        2. token = base64.b64encode(f"{username}:{app_password}"
           .encode()).decode().
        3. self.session = requests.Session(); set
           self.session.headers["Authorization"] = f"Basic {token}".
        """
        self.base_url = base_url.rstrip("/")
        token = base64.b64encode(f"{username}:{app_password}".encode()).decode()
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Basic {token}"

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Input: endpoint (str) - REST path relative to /wp-json/, e.g.
               "wp/v2/manual_document".
               params (dict, optional) - query string parameters.
        Output: dict - the parsed JSON response body.

        Pseudocode:
        1. url = f"{self.base_url}/wp-json/{endpoint}".
        2. response = self.session.get(url, params=params).
        3. response.raise_for_status() (raise if status is not 2xx).
        4. Return response.json().
        """
        url = f"{self.base_url}/wp-json/{endpoint}"
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def post(self, endpoint: str, json_body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Input: endpoint (str) - REST path relative to /wp-json/.
               json_body (dict) - the payload to send as JSON.
        Output: dict - the parsed JSON response body (typically the newly
                created/updated object, e.g. a post).

        Pseudocode:
        1. url = f"{self.base_url}/wp-json/{endpoint}".
        2. response = self.session.post(url, json=json_body).
        3. response.raise_for_status().
        4. Return response.json().
        """
        url = f"{self.base_url}/wp-json/{endpoint}"
        response = self.session.post(url, json=json_body)
        response.raise_for_status()
        return response.json()

    def post_file(self, endpoint: str, file_path: str, filename: str) -> Dict[str, Any]:
        """
        Input: endpoint (str) - REST path for uploads, typically
               "wp/v2/media".
               file_path (str) - local path to the file being uploaded.
               filename (str) - the filename WordPress should store the
               upload as.
        Output: dict - the parsed JSON response describing the created
                media attachment (includes its numeric "id").

        Pseudocode:
        1. url = f"{self.base_url}/wp-json/{endpoint}".
        2. Open file_path in binary mode and read its bytes.
        3. headers = {"Content-Disposition":
           f'attachment; filename="{filename}"'}.
        4. response = self.session.post(url, headers=headers, data=file_bytes).
        5. response.raise_for_status().
        6. Return response.json().
        """
        url = f"{self.base_url}/wp-json/{endpoint}"

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        # WordPress's media endpoint also needs a Content-Type to store the
        # upload correctly - the pseudocode's headers are extended with a
        # best-effort guess based on the filename's extension.
        content_type, _ = mimetypes.guess_type(filename)
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": content_type or "application/octet-stream",
        }

        response = self.session.post(url, headers=headers, data=file_bytes)
        response.raise_for_status()
        return response.json()
