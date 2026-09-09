import os
import shutil
import uuid
import datetime
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .config import JobWorkspace, WORKSPACE_ROOT
from .database import get_db, JobRecord, SessionLocal

app = FastAPI(title="Legacy Modernizer V2 API", version="2.0.0")
PROJECT_ROOT = Path(__file__).resolve().parents[2]

@app.get("/api/health")
def health_check():
    """Health check endpoint to verify backend and storage status."""
    return {
        "status": "healthy",
        "workspace_root": str(WORKSPACE_ROOT),
        "workspace_exists": WORKSPACE_ROOT.exists()
    }

@app.get("/api/profiles")
def get_target_profiles():
    """Returns available target modernization stack profiles."""
    from .profiles import list_profiles
    return list_profiles()

@app.post("/api/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    project_name: Optional[str] = Form("legacy_project"),
    target_stack: Optional[str] = Form("fastapi-sqlalchemy"),
    db: Session = Depends(get_db)
):
    """
    Accepts project files, saves them into an isolated job workspace in %LOCALAPPDATA%,
    and triggers the modernization pipeline with the selected target stack.
    """
    job_id = uuid.uuid4().hex[:12]
    workspace = JobWorkspace(job_id)
    workspace.initialize()

    saved_files = []
    try:
        for file in files:
            clean_filename = file.filename.lstrip("/\\")
            file_path = workspace.input_dir / clean_filename
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with file_path.open("wb") as buffer:
                content = await file.read()
                buffer.write(content)
            saved_files.append(clean_filename)

        chosen_stack = target_stack or "fastapi-sqlalchemy"

        # Create initial database record
        job_record = JobRecord(
            job_id=job_id,
            project_name=project_name or "legacy_project",
            target_stack=chosen_stack,
            status="IN_PROGRESS",
            progress_percent=10,
            total_files=len(saved_files)
        )
        db.add(job_record)
        db.commit()

        # Run AI modernization pipeline with selected target stack
        from .ai_agent import modernize_project
        ai_result = modernize_project(
            upload_dir=workspace.input_dir,
            output_dir=workspace.output_dir,
            export_path=workspace.export_zip_path,
            target_stack=chosen_stack
        )

        if ai_result.get("status") == "error":
            job_record.status = "FAILED"
            job_record.error_message = ai_result.get("message")
            db.commit()
            raise HTTPException(status_code=500, detail=ai_result.get("message"))

        # Archive modernized output into export folder
        archive_base = str(workspace.export_dir / "modernized_project")
        shutil.make_archive(archive_base, "zip", str(workspace.output_dir))

        # Update record to success
        job_record.status = "COMPLETED"
        job_record.progress_percent = 100
        job_record.completed_at = datetime.datetime.utcnow()
        db.commit()

        return {
            "message": "Project uploaded and modernized successfully!",
            "job_id": job_id,
            "total_files": len(saved_files),
            "files_saved": saved_files,
            "ai_status": ai_result,
            "download_url": f"/api/jobs/{job_id}/download"
        }

    except HTTPException:
        raise
    except Exception as e:
        # Mark job as failed on unexpected exception
        job_record = db.query(JobRecord).filter(JobRecord.job_id == job_id).first()
        if job_record:
            job_record.status = "FAILED"
            job_record.error_message = str(e)
            db.commit()
        raise HTTPException(status_code=500, detail=f"Upload processing failed: {e}")

@app.get("/api/jobs")
def list_jobs(db: Session = Depends(get_db)):
    """Returns a list of all historical modernization jobs."""
    records = db.query(JobRecord).order_by(JobRecord.created_at.desc()).all()
    return [r.to_dict() for r in records]

@app.get("/api/jobs/{job_id}")
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Returns status, progress, and metadata for a specific job."""
    record = db.query(JobRecord).filter(JobRecord.job_id == job_id).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    
    workspace = JobWorkspace(job_id)
    files = []
    if workspace.output_dir.exists():
        files = [
            str(p.relative_to(workspace.output_dir))
            for p in workspace.output_dir.rglob("*")
            if p.is_file()
        ]
    
    data = record.to_dict()
    data["generated_files"] = files
    data["download_url"] = f"/api/jobs/{job_id}/download" if workspace.export_zip_path.exists() else None
    return data

@app.get("/api/jobs/{job_id}/files")
def get_job_files(job_id: str):
    """Lists generated files in a job's output directory."""
    workspace = JobWorkspace(job_id)
    if not workspace.output_dir.exists():
        raise HTTPException(status_code=404, detail=f"No output found for job '{job_id}'.")
    files = [
        str(p.relative_to(workspace.output_dir))
        for p in workspace.output_dir.rglob("*")
        if p.is_file()
    ]
    return {"job_id": job_id, "files": sorted(files)}

@app.get("/api/jobs/{job_id}/file-content")
def get_job_file_content(job_id: str, filename: str):
    """Returns the text content of a generated file inside a job's output directory."""
    workspace = JobWorkspace(job_id)
    try:
        file_path = workspace.get_output_file_path(filename)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found for job '{job_id}'.")

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        return {"job_id": job_id, "filename": filename, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not read file: {e}")

@app.get("/api/jobs/{job_id}/download")
def download_job_export(job_id: str):
    """Downloads the zipped archive of a modernized job."""
    workspace = JobWorkspace(job_id)
    zip_file = workspace.export_zip_path
    if not zip_file.exists():
        raise HTTPException(status_code=404, detail=f"No export archive found for job '{job_id}'.")
    return FileResponse(
        str(zip_file),
        media_type="application/zip",
        filename=f"{job_id}_modernized.zip"
    )

# Backward compatibility endpoints
@app.get("/api/history")
def get_history(db: Session = Depends(get_db)):
    """Legacy alias for /api/jobs."""
    return list_jobs(db)

@app.get("/api/download")
def download_latest_project(db: Session = Depends(get_db)):
    """Legacy alias: downloads the most recent completed job's archive."""
    latest = db.query(JobRecord).filter(JobRecord.status == "COMPLETED").order_by(JobRecord.created_at.desc()).first()
    if not latest:
        raise HTTPException(status_code=404, detail="No completed modernized projects found.")
    return download_job_export(latest.job_id)

@app.get("/api/file-content")
def get_latest_file_content(filename: str, db: Session = Depends(get_db)):
    """Legacy alias: reads file from the most recent completed job."""
    latest = db.query(JobRecord).filter(JobRecord.status == "COMPLETED").order_by(JobRecord.created_at.desc()).first()
    if not latest:
        raise HTTPException(status_code=404, detail="No completed modernized projects found.")
    return get_job_file_content(latest.job_id, filename)

# Mount frontend if web directory has index.html
web_dir = PROJECT_ROOT / "apps" / "web"
if (web_dir / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="frontend")
