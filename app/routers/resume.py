from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.resume import Resume
from app.utils.file_storage import storage
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resume", tags=["Resume"])

ALLOWED_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/octet-stream",  # some browsers send this for .pdf
}


@router.get("/", summary="List all resumes for current user")
async def list_resumes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all resumes uploaded by the current user."""
    result = await db.execute(
        select(Resume).where(Resume.user_id == current_user.id)
    )
    resumes = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "filename": r.filename,
            "parsed_data": r.parsed_data,
            "uploaded_at": r.uploaded_at.isoformat() if r.uploaded_at else None,
        }
        for r in resumes
    ]


@router.post("/upload", summary="Upload and parse a PDF or DOCX resume")
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload resume — extracts text and stores in DB + ChromaDB."""
    # Be lenient with content type check (browser inconsistencies)
    filename_lower = (file.filename or "").lower()
    is_pdf = filename_lower.endswith(".pdf")
    is_docx = filename_lower.endswith(".docx")
    if not (is_pdf or is_docx or file.content_type in ALLOWED_TYPES):
        raise HTTPException(400, "Only PDF and DOCX files are supported")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(400, "Uploaded file is empty")

    # 1. Save raw file (local or MinIO)
    s3_key = f"resumes/{current_user.id}/{uuid.uuid4()}_{file.filename}"
    try:
        await storage.upload(file_bytes, s3_key, content_type=file.content_type or "application/octet-stream")
    except Exception as e:
        logger.warning(f"File storage failed (continuing): {e}")

    # 2. Extract raw text
    raw_text = ""
    parsed_data = {}
    try:
        from app.services.resume_parser import resume_parser
        raw_text = resume_parser.extract_text(file_bytes, file.filename)
    except Exception as e:
        logger.warning(f"Text extraction failed: {e}")
        raw_text = f"[Could not extract text from {file.filename}]"

    # 3. LLM structured parse (best-effort — don't fail if LLM is unavailable)
    try:
        from app.services.resume_parser import resume_parser
        parsed_data = await resume_parser.parse_structured(raw_text)
    except Exception as e:
        logger.warning(f"LLM parse failed (storing raw text only): {e}")
        # Build basic parsed_data from filename
        parsed_data = {
            "full_name": current_user.full_name,
            "email": current_user.email,
            "skills": [],
            "experience": [],
            "education": [],
            "raw_text_preview": raw_text[:500],
        }

    # 4. ChromaDB indexing (best-effort)
    doc_ids = []
    try:
        from app.services.resume_parser import resume_parser
        from app.vector_store.chroma_client import chroma_client
        chunks = resume_parser.chunk_resume(raw_text, parsed_data)
        doc_ids = chroma_client.add_resume_chunks(chunks, str(current_user.id), str(uuid.uuid4()))
    except Exception as e:
        logger.warning(f"ChromaDB indexing failed: {e}")

    # 5. Save to PostgreSQL
    resume = Resume(
        user_id=current_user.id,
        filename=file.filename,
        s3_key=s3_key,
        raw_text=raw_text,
        parsed_data=parsed_data,
        chroma_doc_ids=doc_ids,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)

    return {
        "id": str(resume.id),
        "filename": resume.filename,
        "parsed_data": resume.parsed_data,
        "chunks_indexed": len(doc_ids),
        "text_length": len(raw_text),
    }


@router.get("/{resume_id}", summary="Get a specific resume")
async def get_resume(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == current_user.id)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(404, "Resume not found")
    return {
        "id": str(resume.id),
        "filename": resume.filename,
        "parsed_data": resume.parsed_data,
        "uploaded_at": resume.uploaded_at.isoformat() if resume.uploaded_at else None,
    }


@router.delete("/{resume_id}", summary="Delete a resume")
async def delete_resume(
    resume_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).where(Resume.id == resume_id, Resume.user_id == current_user.id)
    )
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(404, "Resume not found")

    try:
        from app.vector_store.chroma_client import chroma_client
        chroma_client.delete_resume_chunks(resume_id)
    except Exception:
        pass
    try:
        await storage.delete(resume.s3_key)
    except Exception:
        pass

    await db.delete(resume)
    await db.commit()
    return {"message": "Resume deleted successfully"}
