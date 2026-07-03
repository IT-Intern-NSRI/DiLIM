"""
Lightweight local UI for the Lab Manual Digitization pipelines.

Wraps extraction/document_builder.py and import_to_wp/document_importer.py
directly (no subprocess calls) so upload -> extract -> review -> import all
happen inside one Streamlit session on one machine.

Run from the project root with:
    streamlit run app.py
"""

import glob
import os

import streamlit as st

import config
from extraction.document_builder import build_document, document_to_json, save_json
from import_to_wp.wp_client import WPClient
from import_to_wp.document_importer import import_single_document, DocumentImportError


st.set_page_config(page_title="Lab Manual Digitization", layout="wide")
st.title("Lab Manual Digitization")

if "processed_docs" not in st.session_state:
    # filename -> {"doc": ManualDocument, "json_path": str, "approved": bool}
    st.session_state.processed_docs = {}

# --- Sidebar: WordPress connection (pre-filled from .env, editable) ---
st.sidebar.header("WordPress connection")
wp_base_url = st.sidebar.text_input("Site URL", value=config.WP_BASE_URL or "")
wp_username = st.sidebar.text_input("Username", value=config.WP_USERNAME or "")
wp_app_password = st.sidebar.text_input(
    "Application Password", value=config.WP_APP_PASSWORD or "", type="password"
)
wp_verify_ssl = st.sidebar.checkbox(
    "Verify SSL certificate",
    value=config.WP_VERIFY_SSL,
    help=(
        "Leave this checked for any real host, including the Oracle "
        "Cloud VM setup once it has a Let's Encrypt certificate. Only "
        "uncheck it for a local LocalWP (https://*.local) site whose "
        "self-signed certificate you haven't trusted in LocalWP's SSL "
        "tab."
    ),
)
if st.sidebar.button("Reset session"):
    st.session_state.processed_docs = {}
    st.rerun()

# --- Step 1: Upload ---
st.header("1. Upload PDFs")
uploaded_files = st.file_uploader(
    "Select lab manual PDF(s)", type=["pdf"], accept_multiple_files=True
)

if uploaded_files:
    os.makedirs(config.INPUT_PDF_DIR, exist_ok=True)
    for uploaded_file in uploaded_files:
        dest_path = os.path.join(config.INPUT_PDF_DIR, uploaded_file.name)
        with open(dest_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
    st.success(f"Saved {len(uploaded_files)} file(s) to {config.INPUT_PDF_DIR}")

# --- Step 2: Extraction ---
st.header("2. Extract")
if st.button("Run extraction"):
    pdf_paths = glob.glob(os.path.join(config.INPUT_PDF_DIR, "*.pdf"))
    if not pdf_paths:
        st.warning("No PDFs found in input_pdfs/. Upload some first.")
    else:
        progress = st.progress(0)
        for i, pdf_path in enumerate(pdf_paths):
            with st.spinner(f"Extracting {os.path.basename(pdf_path)}..."):
                doc = build_document(pdf_path, config.OUTPUT_IMAGE_DIR)
                doc_json = document_to_json(doc)

                stem = os.path.splitext(os.path.basename(pdf_path))[0]
                json_path = os.path.join(config.OUTPUT_JSON_DIR, f"{stem}.json")
                save_json(doc_json, json_path)

                st.session_state.processed_docs[doc.source_pdf_filename] = {
                    "doc": doc,
                    "json_path": json_path,
                    # Pre-approve documents with no flags so a clean batch
                    # needs zero clicks; flagged ones default to unapproved.
                    "approved": len(doc.confidence_flags) == 0,
                }
            progress.progress((i + 1) / len(pdf_paths))
        st.success(f"Extracted {len(pdf_paths)} document(s).")

# --- Step 3: Review (minimal: flags + approve/reject) ---
st.header("3. Review")
if not st.session_state.processed_docs:
    st.info("Run extraction to see documents here.")
else:
    for filename, info in st.session_state.processed_docs.items():
        doc = info["doc"]
        with st.container(border=True):
            cols = st.columns([4, 1])
            with cols[0]:
                st.subheader(doc.doc_title)
                st.caption(filename)
                if doc.confidence_flags:
                    for flag in doc.confidence_flags:
                        st.warning(flag)
                else:
                    st.success("No issues flagged.")
                st.caption(
                    f"{len(doc.sections)} section(s), "
                    f"{len(doc.signatories)} signatory(ies), "
                    f"{len(doc.extracted_image_paths)} image(s)"
                )
                with st.expander("View raw JSON"):
                    st.json(document_to_json(doc))
            with cols[1]:
                info["approved"] = st.checkbox(
                    "Approve for import",
                    value=info["approved"],
                    key=f"approve_{filename}",
                )

# --- Step 4: Import ---
st.header("4. Import to WordPress")
approved = [info for info in st.session_state.processed_docs.values() if info["approved"]]
st.write(f"{len(approved)} document(s) approved for import.")

if not wp_base_url or not wp_username or not wp_app_password:
    st.info("Fill in the WordPress connection details in the sidebar to enable import.")

if st.button("Import approved documents", disabled=(len(approved) == 0 or not wp_base_url)):
    client = WPClient(wp_base_url, wp_username, wp_app_password, verify_ssl=wp_verify_ssl)
    for info in approved:
        json_path = info["json_path"]
        try:
            post_id = import_single_document(client, json_path)
            st.success(f"{os.path.basename(json_path)} -> created draft post (id={post_id})")
        except DocumentImportError as e:
            st.error(f"{os.path.basename(json_path)} -> failed: {e}")
            orphan_list = ", ".join(f"{ptype}/{pid}" for ptype, pid in e.orphaned_child_posts)
            st.warning(f"Orphaned child posts (no parent - clean up manually): {orphan_list}")
        except Exception as e:
            st.error(f"{os.path.basename(json_path)} -> failed: {e}")
