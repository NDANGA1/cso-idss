# routers/timetable.py
# Upload timetable PDFs and trigger parsing.

import os
import tempfile
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.user import User
from app.core.deps import require_timetabler_or_admin

router = APIRouter(prefix="/timetable", tags=["timetable"])

ALLOWED_EXTENSIONS = {".pdf"}
MAX_FILE_SIZE = 20 * 1024 * 1024   # 20 MB

@router.post("/upload")
async def upload_timetable(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_timetabler_or_admin),
):
    try:
        from app.services.timetable_parser import parse_timetable_pdf
    except ImportError:
        raise HTTPException(500, "PDF parsing library (pdfplumber) not installed. Run: pip install pdfplumber")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Only PDF files are accepted")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large. Maximum size is {MAX_FILE_SIZE // 1024 // 1024} MB")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = parse_timetable_pdf(tmp_path, db, filename=file.filename or "unknown.pdf")
    finally:
        os.unlink(tmp_path)

    return {
        "message": "Timetable processed successfully",
        "uploaded_by": current_user.name,
        **result,
    }

@router.post("/parse-local")
async def parse_local_folder(
    folder_path: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_timetabler_or_admin),
):
    """
    Parse all PDFs in a local folder path (server-side).
    Useful for bulk import during setup.
    """
    try:
        from app.services.timetable_parser import parse_timetable_pdf
    except ImportError:
        raise HTTPException(500, "pdfplumber not installed")

    if not os.path.isdir(folder_path):
        raise HTTPException(400, f"Folder not found: {folder_path}")

    pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".pdf") or not os.path.splitext(f)[1]]
    if not pdf_files:
        raise HTTPException(400, "No PDF files found in folder")

    all_results = []
    for fname in sorted(pdf_files):
        fpath = os.path.join(folder_path, fname)
        try:
            result = parse_timetable_pdf(fpath, db, filename=fname)
            all_results.append(result)
        except Exception as e:
            all_results.append({"filename": fname, "error": str(e)})

    total_created = sum(r.get("bookings_created", 0) for r in all_results)
    total_skipped = sum(r.get("bookings_skipped", 0) for r in all_results)

    return {
        "message": f"Processed {len(all_results)} files",
        "total_bookings_created": total_created,
        "total_bookings_skipped": total_skipped,
        "files": all_results,
    }
