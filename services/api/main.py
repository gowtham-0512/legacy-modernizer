import os
import shutil
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from typing import List
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Legacy Modernizer V2")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = PROJECT_ROOT / "uploaded_files"
GENERATED_DIR = PROJECT_ROOT / "modernized_files"
EXPORT_BASE_PATH = PROJECT_ROOT / "modernized_project"

@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """
    This endpoint accepts multiple files, saves them to a folder, 
    and returns a summary of what was uploaded.
    """
    # Create a directory to save the files if it doesn't exist
    upload_dir = UPLOAD_DIR
    upload_dir.mkdir(exist_ok=True)
    
    saved_files = []
    
    # Loop through every file the user sent
    for file in files:
        # 1. The browser sends the full path (e.g., "my_project/frontend/src/app.js")
        # We clean it up just in case to avoid security issues
        clean_filename = file.filename.lstrip("/")
        
        # 2. We figure out exactly what the final path should be on our server
        file_path = upload_dir / clean_filename
        
        # 3. MAGIC HAPPENS HERE: We look at the file path and say "create whatever folders this file needs!"
        # If the file is going into "uploaded_files/my_project/backend/", this creates those folders on the fly.
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 4. Now that the folder definitely exists, we open a new file and save the data
        with file_path.open("wb") as buffer:
            content = await file.read()
            buffer.write(content)
            
        saved_files.append(clean_filename)
        
    # After ALL files are saved, tell the AI Agent to start working on the folder!
    print("Upload complete. Triggering AI Agent...")
    from .ai_agent import modernize_project
    
    ai_result = modernize_project(upload_dir)
    if ai_result.get("status") == "error":
        raise HTTPException(status_code=500, detail=ai_result.get("message"))
        
    # Log the successful upload to the database!
    from .database import SessionLocal, ProjectRecord
    db = SessionLocal()
    record = ProjectRecord(
        project_name="legacy_project_upload",
        total_files=len(saved_files),
        status="Success"
    )
    db.add(record)
    db.commit()
    db.close()
        
    # Create the downloadable zip archive of the modernized project
    shutil.make_archive(str(EXPORT_BASE_PATH), "zip", str(GENERATED_DIR))
        
    return {
        "message": "Files uploaded and modernized successfully!",
        "total_files": len(saved_files),
        "files_saved": saved_files,
        "ai_status": ai_result,
        "download_url": "/api/download"
    }

@app.get("/api/download")
def download_modernized_project():
    """Returns the zipped archive of the modernized project."""
    zip_file = EXPORT_BASE_PATH.with_suffix(".zip")
    if not zip_file.exists():
        raise HTTPException(status_code=404, detail="No modernized project zip available to download.")
    return FileResponse(
        str(zip_file),
        media_type="application/zip",
        filename="modernized_project.zip"
    )

@app.get("/api/file-content")
def get_file_content(filename: str):
    """Returns the text content of a generated file for browser preview."""
    # Prevent path traversal attacks
    safe_filename = os.path.basename(filename)
    file_path = GENERATED_DIR / safe_filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File '{safe_filename}' not found.")
    try:
        with file_path.open("r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return {"filename": safe_filename, "content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not read file: {e}")

@app.get("/api/history")
def get_history():
    """Returns all project upload history from the database."""
    from .database import SessionLocal, ProjectRecord
    db = SessionLocal()
    records = db.query(ProjectRecord).all()
    db.close()
    
    return [
        {
            "id": r.id, 
            "project_name": r.project_name, 
            "total_files": r.total_files, 
            "status": r.status, 
            "created_at": r.created_at
        } 
        for r in records
    ]

# Mount the frontend directory to serve the HTML/CSS/JS files
# This MUST be at the bottom so it doesn't accidentally intercept the /api/upload POST request!
app.mount("/", StaticFiles(directory=PROJECT_ROOT / "apps" / "web", html=True), name="frontend")
