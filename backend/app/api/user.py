import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/user", tags=["user"])

_REPO_ROOT = Path(__file__).parents[3]
_DATA_DIR = _REPO_ROOT / "data"
_ALLOWED_SUFFIXES = {".md", ".txt", ".pdf", ".docx"}


@router.get("/profile")
def get_user_profile() -> dict:
    """Return the contents of user_profile.yaml plus parsed resume skills if available."""
    from app.services.text_parser import ResumeParser, load_user_profile

    profile = load_user_profile()
    if not profile:
        raise HTTPException(status_code=404, detail="user_profile.yaml not found or empty")

    resume_path_rel = (profile.get("user") or {}).get("resume_file_path")
    parsed_resume = None
    if resume_path_rel:
        resume_path = _REPO_ROOT / resume_path_rel
        if resume_path.exists():
            try:
                parsed_resume = ResumeParser().parse_file(str(resume_path))
            except Exception as exc:
                logger.warning("Failed to parse resume at %s: %s", resume_path, exc)

    return {**profile, "parsed_resume": parsed_resume}


@router.post("/resume")
async def upload_resume(file: UploadFile) -> dict:
    """
    Upload a resume file (.md, .txt, .pdf, .docx).
    Saves to data/resume.<ext> and returns parsed skills and experience.
    """
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{suffix}'. Allowed: {sorted(_ALLOWED_SUFFIXES)}",
        )

    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    dest = _DATA_DIR / f"resume{suffix}"

    content = await file.read()
    dest.write_bytes(content)
    logger.info("Resume saved to %s (%d bytes)", dest, len(content))

    from app.services.text_parser import ResumeParser

    parsed = ResumeParser().parse_file(str(dest))
    return {
        "saved_to": str(dest.relative_to(_REPO_ROOT)),
        "skills": parsed["skills"],
        "experience_years": parsed["experience_years"],
        "titles": parsed["titles"],
    }
