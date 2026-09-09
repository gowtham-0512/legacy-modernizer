import os
import shutil
from pathlib import Path
from typing import Dict, Any

# Determine local application data directory (outside of git repository)
def get_workspace_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base_dir = Path(local_app_data) / "LegacyModernizer"
    else:
        # Fallback for non-Windows or custom environments
        base_dir = Path.home() / ".legacy_modernizer"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir

WORKSPACE_ROOT = get_workspace_root()
JOBS_DIR = WORKSPACE_ROOT / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = WORKSPACE_ROOT / "modernizer.db"

class JobWorkspace:
    """Manages directory lifecycle and file paths for a single modernization run."""
    def __init__(self, job_id: str):
        self.job_id = job_id
        self.root_dir = JOBS_DIR / job_id
        self.input_dir = self.root_dir / "input"
        self.output_dir = self.root_dir / "output"
        self.export_dir = self.root_dir / "export"
        self.logs_dir = self.root_dir / "logs"

    def initialize(self) -> None:
        """Creates the isolated directories for the job."""
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    @property
    def export_zip_path(self) -> Path:
        return self.export_dir / "modernized_project.zip"

    def get_output_file_path(self, relative_path: str) -> Path:
        """Resolves an output path safely, guarding against directory traversal."""
        safe_path = Path(relative_path).resolve()
        target = (self.output_dir / relative_path).resolve()
        if not str(target).startswith(str(self.output_dir.resolve())):
            raise ValueError(f"Path traversal detected: {relative_path}")
        return target

    def cleanup(self) -> None:
        """Removes the entire job folder from disk."""
        if self.root_dir.exists():
            shutil.rmtree(self.root_dir, ignore_errors=True)
