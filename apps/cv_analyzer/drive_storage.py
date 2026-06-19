from __future__ import annotations
import os
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from io import BytesIO
from functools import lru_cache

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]


@lru_cache(maxsize=1)
def get_drive_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds_path = os.getenv(
        "GOOGLE_SERVICE_ACCOUNT_PATH",
        "credentials/google_service_account.json",
    )
    creds = service_account.Credentials.from_service_account_file(
        creds_path, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)


def _get_or_create_folder(service, name: str, parent_id: str) -> str:
    query = (
        f"name='{name}' and "
        f"'{parent_id}' in parents and "
        f"mimeType='application/vnd.google-apps.folder' and "
        f"trashed=false"
    )
    results = service.files().list(q=query, fields="files(id)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]

    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def _upload_file(
    service, content: bytes, filename: str, mime_type: str, parent_id: str
) -> str:
    from googleapiclient.http import MediaIoBaseUpload

    metadata = {"name": filename, "parents": [parent_id]}
    media = MediaIoBaseUpload(BytesIO(content), mimetype=mime_type)
    file = service.files().create(
        body=metadata, media_body=media, fields="id,webViewLink"
    ).execute()
    return file.get("webViewLink", "")


def _make_folder_name(original_filename: str) -> str:
    stem = Path(original_filename).stem
    clean = stem.replace(" ", "_")[:40]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{clean}_{ts}"


def _save_cv_sync(
    file_bytes: bytes,
    original_filename: str,
    profile_json: str,
    scores_json: str,
    gap_report: str,
) -> str:
    try:
        service = get_drive_service()
        root_id = os.getenv("GDRIVE_ROOT_FOLDER_ID", "")
        if not root_id:
            logger.warning("GDRIVE_ROOT_FOLDER_ID not set — skipping Drive upload")
            return ""

        month_folder = datetime.now().strftime("%Y-%m")
        month_id = _get_or_create_folder(service, month_folder, root_id)

        case_folder_name = _make_folder_name(original_filename)
        case_id = _get_or_create_folder(service, case_folder_name, month_id)

        ext = Path(original_filename).suffix.lower()
        mime = (
            "application/pdf"
            if ext == ".pdf"
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        _upload_file(service, file_bytes, f"CV_original{ext}", mime, case_id)
        _upload_file(
            service,
            profile_json.encode("utf-8"),
            "profile_extracted.json",
            "application/json",
            case_id,
        )
        _upload_file(
            service,
            scores_json.encode("utf-8"),
            "scores.json",
            "application/json",
            case_id,
        )
        _upload_file(
            service,
            gap_report.encode("utf-8"),
            "gap_report.md",
            "text/markdown",
            case_id,
        )

        folder_meta = service.files().get(fileId=case_id, fields="webViewLink").execute()
        drive_url = folder_meta.get("webViewLink", "")
        logger.info(f"Saved CV to Drive: {case_folder_name} → {drive_url}")
        return drive_url

    except Exception as e:
        logger.error(f"Failed to save CV to Drive: {e}", exc_info=True)
        return ""


async def save_cv_to_drive(
    file_bytes: bytes,
    original_filename: str,
    profile_json: str,
    scores_json: str,
    gap_report: str,
) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        _save_cv_sync,
        file_bytes,
        original_filename,
        profile_json,
        scores_json,
        gap_report,
    )
