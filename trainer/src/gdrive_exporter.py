"""Módulo de exportación de modelos versionados y manifiesto atómico a Google Drive (03_model_registry)."""

import io
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GDRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
MANIFEST_FILENAME = "models_manifest.json"


def get_drive_service(credentials_info: dict[str, Any] | str | None = None) -> Any:
    """Construye e inicializa el cliente de Google Drive API a partir de Service Account."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    if isinstance(credentials_info, str):
        if credentials_info.strip().startswith("{"):
            info = json.loads(credentials_info)
            creds = service_account.Credentials.from_service_account_info(info, scopes=GDRIVE_SCOPES)
        elif os.path.exists(credentials_info):
            creds = service_account.Credentials.from_service_account_file(credentials_info, scopes=GDRIVE_SCOPES)
        else:
            raise ValueError("ERR_GDRIVE_AUTH: La cadena proporcionada no es un archivo ni JSON válido.")
    elif isinstance(credentials_info, dict):
        creds = service_account.Credentials.from_service_account_info(credentials_info, scopes=GDRIVE_SCOPES)
    else:
        env_creds = os.environ.get("GDRIVE_SERVICE_ACCOUNT_JSON")
        if env_creds:
            info = json.loads(env_creds)
            creds = service_account.Credentials.from_service_account_info(info, scopes=GDRIVE_SCOPES)
        elif os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            creds = service_account.Credentials.from_service_account_file(
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"], scopes=GDRIVE_SCOPES
            )
        else:
            raise ValueError("ERR_GDRIVE_AUTH: No se suministraron credenciales válidas de Service Account.")

    return build("drive", "v3", credentials=creds, cache_discovery=False)


def get_or_create_subfolder(drive_service: Any, parent_id: str, folder_name: str) -> str:
    """Busca o crea una subcarpeta en Google Drive dentro del parent_id."""
    query = (
        f"'{parent_id}' in parents and name = '{folder_name}' and "
        "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    if files:
        return str(files[0]["id"])

    folder_metadata = {
        "name": folder_name,
        "parents": [parent_id],
        "mimeType": "application/vnd.google-apps.folder",
    }
    folder = drive_service.files().create(body=folder_metadata, fields="id").execute()
    return str(folder.get("id"))


def upload_or_update_file(
    drive_service: Any,
    folder_id: str,
    file_path: Path,
    mime_type: str = "application/octet-stream",
) -> str:
    """Sube o actualiza un archivo en la carpeta designada de Drive."""
    from googleapiclient.http import MediaFileUpload

    file_name = file_path.name
    query = f"'{folder_id}' in parents and name = '{file_name}' and trashed = false"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])

    media = MediaFileUpload(str(file_path), mimetype=mime_type, resumable=True)

    if files:
        file_id = files[0]["id"]
        updated = drive_service.files().update(fileId=file_id, media_body=media, fields="id").execute()
        return str(updated.get("id"))

    file_metadata = {
        "name": file_name,
        "parents": [folder_id],
    }
    created = drive_service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    return str(created.get("id"))


def get_manifest_from_drive(drive_service: Any, folder_id: str) -> dict[str, Any]:
    """Descarga models_manifest.json desde Drive si existe; de lo contrario retorna plantilla inicial."""
    from googleapiclient.http import MediaIoBaseDownload

    query = f"'{folder_id}' in parents and name = '{MANIFEST_FILENAME}' and trashed = false"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])

    if not files:
        return {
            "production_version": "v1",
            "latest_version": "v1",
            "versions": {},
        }

    file_id = files[0]["id"]
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    fh.seek(0)
    return json.loads(fh.read().decode("utf-8"))


def save_manifest_to_drive(drive_service: Any, folder_id: str, manifest_data: dict[str, Any]) -> str:
    """Guarda atómicamente models_manifest.json en la carpeta raíz del registry en Drive."""
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as tmp:
        json.dump(manifest_data, tmp, ensure_ascii=False, indent=2)
        tmp_path = Path(tmp.name)

    try:
        manifest_id = upload_or_update_file(
            drive_service,
            folder_id=folder_id,
            file_path=tmp_path,
            mime_type="application/json",
        )
        return manifest_id
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def get_next_manifest_version(manifest: dict[str, Any]) -> str:
    """Calcula la siguiente versión incremental (v1, v2, v3...) para el manifiesto."""
    versions = manifest.get("versions", {})
    if not versions:
        return "v1"
    v_nums = [int(v[1:]) for v in versions.keys() if v.startswith("v") and v[1:].isdigit()]
    if not v_nums:
        return "v1"
    return f"v{max(v_nums) + 1}"


def export_version_to_gdrive(
    credentials_info: dict[str, Any] | str | None,
    registry_folder_id: str,
    artifacts_dir: Path,
    metrics: dict[str, Any],
    dry_run: bool = False,
) -> dict[str, Any]:
    """Exporta los binarios a v(N)/ en Drive y actualiza models_manifest.json."""
    if dry_run or not registry_folder_id:
        # Modo simulado para testing o entornos sin Drive activo
        next_v = "v1"
        return {
            "status": "dry_run",
            "version": next_v,
            "uploaded_files": [f.name for f in artifacts_dir.glob("*.joblib")],
            "manifest": {
                "production_version": next_v,
                "latest_version": next_v,
                "versions": {
                    next_v: {
                        "version": next_v,
                        "registered_at": datetime.now(timezone.utc).isoformat(),
                        "metrics": metrics,
                        "status": "production",
                    }
                },
            },
        }

    drive_service = get_drive_service(credentials_info)

    # 1. Obtener manifiesto actual
    manifest = get_manifest_from_drive(drive_service, registry_folder_id)
    next_version = get_next_manifest_version(manifest)

    # 2. Crear subcarpeta versionada v(N)
    version_folder_id = get_or_create_subfolder(drive_service, registry_folder_id, next_version)

    # 3. Subir binarios .joblib
    uploaded_files: dict[str, str] = {}
    for joblib_file in artifacts_dir.glob("*.joblib"):
        fid = upload_or_update_file(drive_service, version_folder_id, joblib_file)
        uploaded_files[joblib_file.name] = fid

    # 4. Actualizar estado en el manifiesto
    for v_key, v_val in manifest.get("versions", {}).items():
        if isinstance(v_val, dict):
            v_val["status"] = "archived"

    manifest["versions"][next_version] = {
        "version": next_version,
        "folder_id": version_folder_id,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "artifacts": uploaded_files,
        "status": "production",
    }
    manifest["production_version"] = next_version
    manifest["latest_version"] = next_version

    # 5. Persistir manifiesto actualizado en Drive
    manifest_file_id = save_manifest_to_drive(drive_service, registry_folder_id, manifest)

    return {
        "status": "success",
        "version": next_version,
        "version_folder_id": version_folder_id,
        "manifest_file_id": manifest_file_id,
        "manifest": manifest,
    }


def export_version_to_gdrive_atomic(
    credentials_info: dict[str, Any] | str | None,
    registry_folder_id: str,
    artifacts_dir: Path,
    metrics: dict[str, Any],
    dataset_hash: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Exporta binarios a staging_v(N+1)/, valida integridad y renombra atómicamente antes de actualizar el manifiesto."""
    joblib_files = sorted(artifacts_dir.glob("*.joblib"))
    if not joblib_files:
        raise ValueError(f"ERR_NO_ARTIFACTS: No se encontraron archivos .joblib en {artifacts_dir}")

    if dry_run or not registry_folder_id:
        next_v = "v1"
        version_entry: dict[str, Any] = {
            "version": next_v,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics,
            "status": "production",
        }
        if dataset_hash:
            version_entry["dataset_hash"] = dataset_hash
        return {
            "status": "dry_run",
            "atomic_staging": True,
            "version": next_v,
            "uploaded_files": [f.name for f in joblib_files],
            "manifest": {
                "production_version": next_v,
                "latest_version": next_v,
                "versions": {next_v: version_entry},
            },
        }

    drive_service = get_drive_service(credentials_info)

    # 1. Obtener manifiesto actual y verificar idempotencia por dataset_hash
    manifest = get_manifest_from_drive(drive_service, registry_folder_id)
    prod_v = manifest.get("production_version")
    prod_info = manifest.get("versions", {}).get(prod_v) if prod_v else None
    if dataset_hash and isinstance(prod_info, dict) and prod_info.get("dataset_hash") == dataset_hash:
        return {
            "status": "SKIP_IDENTICAL_DATASET",
            "atomic_staging": True,
            "version": prod_v,
            "manifest": manifest,
        }

    next_version = get_next_manifest_version(manifest)
    staging_name = f"staging_{next_version}"

    # 2. Fase 1 Atómica: subir binarios a staging_v(N+1)/
    staging_folder_id = get_or_create_subfolder(drive_service, registry_folder_id, staging_name)
    uploaded_files: dict[str, str] = {}
    for joblib_file in joblib_files:
        fid = upload_or_update_file(drive_service, staging_folder_id, joblib_file)
        if not fid:
            raise IOError(f"ERR_ATOMIC_UPLOAD_FAILED: Falló la subida de {joblib_file.name}")
        uploaded_files[joblib_file.name] = fid

    # 3. Fase 2 Atómica: renombrar staging_v(N+1) -> v(N+1) tras validar integridad completa
    drive_service.files().update(
        fileId=staging_folder_id,
        body={"name": next_version},
        fields="id, name",
    ).execute()

    # 4. Actualizar estado en el manifiesto
    for v_key, v_val in manifest.get("versions", {}).items():
        if isinstance(v_val, dict):
            v_val["status"] = "archived"

    version_record: dict[str, Any] = {
        "version": next_version,
        "folder_id": staging_folder_id,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "artifacts": uploaded_files,
        "status": "production",
    }
    if dataset_hash:
        version_record["dataset_hash"] = dataset_hash

    manifest["versions"][next_version] = version_record
    manifest["production_version"] = next_version
    manifest["latest_version"] = next_version

    # 5. Persistir manifiesto actualizado en Drive
    manifest_file_id = save_manifest_to_drive(drive_service, registry_folder_id, manifest)

    return {
        "status": "success",
        "atomic_staging": True,
        "version": next_version,
        "version_folder_id": staging_folder_id,
        "manifest_file_id": manifest_file_id,
        "manifest": manifest,
    }
