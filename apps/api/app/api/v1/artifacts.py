"""Artifact retrieval endpoints with path traversal protection and authorization boundaries."""

import os
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Depends, status
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.logging import logger

router = APIRouter(prefix="/artifacts", tags=["Artifacts"])


def verify_artifact_authorization(
    authorization: Optional[str] = Header(None, description="Optional bearer token for artifact authorization"),
) -> None:
    """Authorization boundary for artifact access.
    
    SECURITY NOTICE:
    In local development and MVP mode, this endpoint is intended for trusted local single-tenant use.
    Before exposing this service publicly or in multi-tenant environments:
    - An identity provider (JWT/OAuth2) or project-level access control check MUST be enforced.
    - Public access without authentication is explicitly blocked in production environments.
    """
    if settings.ENVIRONMENT.strip().lower() == "production":
        # Production deployment requires explicit authorization token
        configured_token = os.environ.get("GHOST_USER_ARTIFACT_TOKEN")
        if not configured_token:
            logger.error("Artifact endpoint accessed in production mode without GHOST_USER_ARTIFACT_TOKEN configured.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Artifact access in production requires configured authentication.",
            )
        if not authorization or authorization.strip() != f"Bearer {configured_token}":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing artifact authorization token.",
            )


@router.get("/{test_run_id}/{file_path:path}", dependencies=[Depends(verify_artifact_authorization)])
def get_artifact(test_run_id: str, file_path: str):
    """Safely retrieves a screenshot or trace archive for a test run."""
    # Prevent path traversal and null byte injection
    if ".." in test_run_id or "\x00" in test_run_id or ".." in file_path or "\x00" in file_path:
        logger.warning(f"Illegal path traversal or null byte injection: run={test_run_id}, path={file_path}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path identifier")

    storage_root = os.environ.get("ARTIFACT_STORAGE_DIR", settings.ARTIFACT_STORAGE_DIR)
    base_storage = Path(storage_root).resolve()
    target_dir = (base_storage / test_run_id).resolve()

    try:
        # Check target_dir is strictly inside base_storage
        if not target_dir.is_relative_to(base_storage):
            logger.warning(f"Illegal path traversal attempt with test_run_id: {test_run_id}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path identifier")

        candidate_file = target_dir / file_path
        if candidate_file.is_symlink():
            logger.warning(f"Illegal symlink access attempt: {file_path}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Symlinks not permitted")

        resolved_file = candidate_file.resolve()
        if not resolved_file.is_relative_to(target_dir):
            logger.warning(f"Illegal path traversal attempt with file_path: {file_path}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid artifact path")

        if not resolved_file.exists() or not resolved_file.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

        # Determine media type
        media_type = "application/octet-stream"
        suffix = resolved_file.suffix.lower()
        if suffix == ".png":
            media_type = "image/png"
        elif suffix in (".jpeg", ".jpg"):
            media_type = "image/jpeg"
        elif suffix == ".zip":
            media_type = "application/zip"

        return FileResponse(
            path=str(resolved_file),
            media_type=media_type,
            filename=resolved_file.name,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving artifact {file_path} for run {test_run_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not serve artifact")
