"""Artifact storage manager for test runs (screenshots and traces)."""

import os
from pathlib import Path
from typing import Optional
from app.core.config import settings


class ArtifactManager:
    def __init__(self, run_id: str, base_dir: Optional[str] = None):
        self.run_id = run_id
        storage_root = base_dir or os.environ.get("ARTIFACT_STORAGE_DIR", settings.ARTIFACT_STORAGE_DIR)
        self.base_dir = Path(storage_root).resolve()
        self.run_dir = (self.base_dir / run_id).resolve()
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def get_screenshot_path(self, step_index: int, name: Optional[str] = None) -> tuple[Path, str]:
        """Returns (absolute_file_path, relative_storage_path)."""
        clean_name = f"_{name.strip()}" if name else ""
        filename = f"step_{step_index}{clean_name}.png"
        abs_path = self.run_dir / filename
        rel_path = f"{self.run_id}/{filename}"
        return abs_path, rel_path

    def get_trace_path(self) -> tuple[Path, str]:
        """Returns (absolute_file_path, relative_storage_path) for Playwright trace zip."""
        filename = "trace.zip"
        abs_path = self.run_dir / filename
        rel_path = f"{self.run_id}/{filename}"
        return abs_path, rel_path
