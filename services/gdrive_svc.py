"""Google Drive integration via Service Account."""
import json
import logging
from datetime import datetime

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

import config

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents",
]

_drive_service = None
_docs_service = None


def _get_credentials() -> Credentials:
    """Build credentials from service account JSON (file path or inline string)."""
    sa_json = config.GOOGLE_SERVICE_ACCOUNT_JSON
    if not sa_json:
        raise ValueError("Google service account JSON not configured")

    if sa_json.strip().startswith("{"):
        info = json.loads(sa_json, strict=False)
        return Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        return Credentials.from_service_account_file(sa_json, scopes=SCOPES)


def _get_drive_service():
    global _drive_service
    if _drive_service is None:
        creds = _get_credentials()
        _drive_service = build("drive", "v3", credentials=creds)
    return _drive_service


def _get_docs_service():
    global _docs_service
    if _docs_service is None:
        creds = _get_credentials()
        _docs_service = build("docs", "v1", credentials=creds)
    return _docs_service


def _build_doc_content(summary: dict, audio_duration: float, created_at: float) -> tuple[str, list]:
    """Build document text and heading format requests.

    Returns (full_text, heading_requests) where heading_requests are
    batchUpdate requests to apply after inserting the text.
    """
    meeting_time = datetime.fromtimestamp(created_at).strftime("%B %d, %Y at %I:%M %p")
    duration_min = int(audio_duration // 60)
    duration_sec = int(audio_duration % 60)

    # Build lines with markers for which are headings
    # Each entry: (text, heading_level) where None = body text
    sections = []
    sections.append(("Meeting Summary\n", "HEADING_1"))
    sections.append((f"{meeting_time}  |  Duration: {duration_min}m {duration_sec}s\n\n", None))

    sections.append(("Executive Summary\n", "HEADING_2"))
    sections.append((f"{summary['executive_summary']}\n\n", None))

    sections.append(("Action Items\n", "HEADING_2"))
    if summary.get("action_items"):
        for item in summary["action_items"]:
            assignee = f" ({item['assignee']})" if item.get("assignee") else ""
            sections.append((f"    {item['task']}{assignee}\n", None))
    else:
        sections.append(("    None identified\n", None))
    sections.append(("\n", None))

    sections.append(("Key Decisions\n", "HEADING_2"))
    if summary.get("key_decisions"):
        for d in summary["key_decisions"]:
            sections.append((f"    {d}\n", None))
    else:
        sections.append(("    None identified\n", None))
    sections.append(("\n", None))

    sections.append(("Topics Discussed\n", "HEADING_2"))
    if summary.get("topics_discussed"):
        sections.append((f"    {', '.join(summary['topics_discussed'])}\n", None))

    # Combine into full text
    full_text = "".join(text for text, _ in sections)

    # Build heading requests by tracking character indices
    heading_requests = []
    idx = 1  # Google Docs index starts at 1
    for text, level in sections:
        if level is not None:
            heading_requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": idx, "endIndex": idx + len(text)},
                    "paragraphStyle": {"namedStyleType": level},
                    "fields": "namedStyleType"
                }
            })
        idx += len(text)

    return full_text, heading_requests


def upload_to_drive(summary: dict, audio_duration: float, created_at: float) -> dict:
    """Create a formatted Google Doc in the shared folder.

    Returns {"success": True, "url": "...", "doc_id": "..."}.
    """
    folder_id = config.GOOGLE_DRIVE_FOLDER_ID
    if not folder_id:
        raise ValueError("Google Drive folder ID not configured")

    meeting_time = datetime.fromtimestamp(created_at).strftime("%Y-%m-%d %H:%M")
    doc_title = f"Meeting Notes - {meeting_time}"

    drive = _get_drive_service()
    docs = _get_docs_service()

    # Create empty doc in the target folder
    file_metadata = {
        "name": doc_title,
        "mimeType": "application/vnd.google-apps.document",
        "parents": [folder_id],
    }
    file = drive.files().create(
        body=file_metadata,
        fields="id,webViewLink",
        supportsAllDrives=True
    ).execute()
    doc_id = file["id"]
    doc_url = file["webViewLink"]

    logger.info("Created Google Doc: %s", doc_id)

    # Populate with formatted content
    full_text, heading_requests = _build_doc_content(summary, audio_duration, created_at)

    requests = [{"insertText": {"location": {"index": 1}, "text": full_text}}]
    requests.extend(heading_requests)

    docs.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()

    logger.info("Google Doc populated: %s", doc_url)

    return {"success": True, "url": doc_url, "doc_id": doc_id}
