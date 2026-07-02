"""
Entry point for the second half of Part 1 (pushing extracted content
into WordPress). Run this from the project root with:
    python -m import_to_wp.run_import

Reads every JSON file in config.OUTPUT_JSON_DIR (produced by
extraction/run_extraction.py and ideally reviewed by a human first) and
creates one draft "Manual Document" post per file on the live site.
"""

import glob
import os

import config
from import_to_wp.wp_client import WPClient
from import_to_wp.document_importer import import_single_document


def main() -> None:
    """
    Input: None (reads all JSON files from config.OUTPUT_JSON_DIR, and
           WordPress credentials from config).
    Output: None (side effect: creates one draft post per JSON file on
            the live WordPress site, and prints a summary of successes
            and failures).

    Pseudocode:
    1. client = WPClient(config.WP_BASE_URL, config.WP_USERNAME,
       config.WP_APP_PASSWORD).
    2. json_paths = glob.glob(os.path.join(config.OUTPUT_JSON_DIR, "*.json")).
    3. successes = []; failures = [].
    4. For each json_path in json_paths:
        a. Print progress, e.g. f"Importing {json_path}...".
        b. Try:
            post_id = import_single_document(client, json_path);
            append (json_path, post_id) to successes;
            print a success line.
           Except Exception as e:
            append (json_path, str(e)) to failures;
            print a failure line, but continue the loop rather than
            aborting the whole run.
    5. Print a final summary: total imported successfully, total failed,
       and list the failed filenames with their error messages so a
       human can retry or fix them individually.
    """
    client = WPClient(config.WP_BASE_URL, config.WP_USERNAME, config.WP_APP_PASSWORD)
    json_paths = glob.glob(os.path.join(config.OUTPUT_JSON_DIR, "*.json"))

    successes = []
    failures = []

    for json_path in json_paths:
        print(f"Importing {json_path}...")
        try:
            post_id = import_single_document(client, json_path)
            successes.append((json_path, post_id))
            print(f"  Created draft post (id={post_id}).")
        except Exception as e:
            failures.append((json_path, str(e)))
            print(f"  Failed: {e}")

    print(f"\nImported {len(successes)} of {len(json_paths)} document(s) successfully.")
    if failures:
        print(f"{len(failures)} document(s) failed:")
        for json_path, error in failures:
            print(f"  {json_path}: {error}")
    else:
        print("No failures.")


if __name__ == "__main__":
    main()
