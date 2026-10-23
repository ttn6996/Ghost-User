"""Artifact retrieval endpoints with strict path traversal protection."""

import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.logging import logger

router = APIRouter(prefix="/artifacts", tags=["Artifacts"])


@router.get("/{test_run_id}/{file_path:path}")
def get_artifact(test_run_id: str, file_path: str):
    """Safely retrieves a screenshot or trace archive for a test run."""
    # Prevent path traversal
    storage_root = os.environ.get("ARTIFACT_STORAGE_DIR", settings.ARTIFACT_STORAGE_DIR)
    base_storage = Path(storage_root).resolve()
    target_dir = (base_storage / test_run_id).resolve()

    try:
        # Check target_dir is strictly inside base_storage
        if not target_dir.is_relative_to(base_storage):
            logger.warning(f"Illegal path traversal attempt with test_run_id: {test_run_id}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path identifier")

        resolved_file = (target_dir / file_path).resolve()
        if not resolved_file.is_relative_to(target_dir):
            logger.warning(f"Illegal path traversal attempt with file_path: {file_path}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid artifact path")

        if not resolved_file.exists() or not resolved_file.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

        # Determine media type
        media_type = "application/octet-stream"
        if resolved_file.suffix.lower() == ".png":
            media_type = "image/png"
        elif resolved_file.suffix.lower() == ".jpeg" or resolved_file.suffix.lower() == ".jpg":
            media_type = "image/jpeg"
        elif resolved_file.suffix.lower() == ".zip":
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
