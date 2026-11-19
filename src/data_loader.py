"""Data loader supporting Google Drive ingestion with local fallback.
Resilient against network timeouts, credential failures, and schema mismatch.
"""
import io
import re
import os
import requests
import pandas as pd
from typing import Dict, Any, Tuple, Optional
import src.config as cfg


def _extract_year_month(filename: str) -> Tuple[int, int]:
    """Extracts (year, month) from filenames like alquileres_caba_enriquecido_2026_11.csv."""
    m = re.search(r"(\d{4})[_-](\d{2})", filename)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 0, 0


def get_latest_gdrive_csv(
    folder_id: Optional[str] = None,
    service_account_info: Optional[dict] = None,
    file_id: Optional[str] = None,
    direct_url: Optional[str] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Attempts to download the latest monthly CSV from Google Drive."""
    # Case 1: Direct CSV URL
    if direct_url:
        resp = requests.get(direct_url, timeout=cfg.REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        return df, {"source": "GDRIVE_DIRECT_URL", "reason": "SOURCE_GDRIVE_LATEST"}

    # Case 2: File ID (Google Drive public or export link)
    if file_id:
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
        resp = requests.get(url, timeout=cfg.REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        return df, {"source": "GDRIVE_FILE_ID", "reason": "SOURCE_GDRIVE_LATEST"}

    # Case 3: Google Drive API via Service Account
    if folder_id and service_account_info:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload

        creds = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=["https://www.googleapis.com/auth/drive.readonly"],
        )
        service = build("drive", "v3", credentials=creds)

        query = f"'{folder_id}' in parents and trashed = false and name contains 'alquileres_caba_enriquecido_'"
        results = service.files().list(
            q=query,
            fields="files(id, name, modifiedTime)",
            pageSize=20,
        ).execute()

        files = results.get("files", [])
        if not files:
            raise ValueError(f"No files matching pattern found in folder {folder_id}")

        # Sort by (year, month) descending, then modifiedTime descending
        files.sort(key=lambda x: (_extract_year_month(x["name"]), x.get("modifiedTime", "")), reverse=True)
        latest_file = files[0]
        file_id_to_fetch = latest_file["id"]

        request_media = service.files().get_media(fileId=file_id_to_fetch)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request_media)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        fh.seek(0)
        df = pd.read_csv(fh)
        return df, {
            "source": "GDRIVE_FOLDER_API",
            "reason": "SOURCE_GDRIVE_LATEST",
            "file_name": latest_file["name"],
            "file_id": latest_file["id"],
        }

    raise ValueError("No Google Drive configuration provided (folder_id, file_id, or direct_url missing)")


def load_dataset(local_fallback_path: str = "data/fallback_data.csv") -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Loads active dataset from Google Drive if configured, else seamlessly falls back to local data."""
    # Read secrets or environment variables
    folder_id = os.environ.get("GDRIVE_FOLDER_ID")
    file_id = os.environ.get("GDRIVE_FILE_ID")
    direct_url = os.environ.get("GDRIVE_CSV_URL")
    service_account_json = os.environ.get("GCP_SERVICE_ACCOUNT")

    # Check Streamlit secrets if running inside streamlit
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            folder_id = folder_id or st.secrets.get("gdrive_folder_id")
            file_id = file_id or st.secrets.get("gdrive_file_id")
            direct_url = direct_url or st.secrets.get("gdrive_csv_url")
            if "gcp_service_account" in st.secrets:
                service_account_json = st.secrets["gcp_service_account"]
    except Exception:
        pass

    service_account_info = None
    if service_account_json:
        if isinstance(service_account_json, dict):
            service_account_info = service_account_json
        elif isinstance(service_account_json, str):
            import json
            try:
                service_account_info = json.loads(service_account_json)
            except Exception:
                pass

    # Attempt Google Drive download if any config exists
    if folder_id or file_id or direct_url:
        try:
            df, meta = get_latest_gdrive_csv(
                folder_id=folder_id,
                service_account_info=service_account_info,
                file_id=file_id,
                direct_url=direct_url,
            )
            return df, meta
        except Exception as e:
            # Fallback on any failure
            pass

    # Local Fallback
    try:
        df = pd.read_csv(local_fallback_path)
        return df, {
            "source": "LOCAL_FALLBACK",
            "reason": "WARN_DRIVE_FALLBACK_ACTIVE",
            "fallback_path": local_fallback_path,
        }
    except Exception as e:
        return pd.DataFrame(), {
            "source": "FAILED",
            "reason": f"ERR_FALLBACK_FAILED: {str(e)}",
        }
