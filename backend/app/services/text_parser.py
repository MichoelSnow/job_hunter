"""Resume and job description parsing using spaCy NER and keyword matching."""
import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TAXONOMY_PATH = Path(__file__).parents[4] / "config" / "skill_taxonomy.json"


class ResumeParser:
    """Parses a resume file or text into a structured skill/experience dict."""

    def parse_file(self, file_path: str) -> dict[str, Any]:
        path = Path(file_path)
        if path.suffix == ".docx":
            text = self._read_docx(path)
        elif path.suffix == ".pdf":
            text = self._read_pdf(path)
        elif path.suffix in (".md", ".txt"):
            text = path.read_text(encoding="utf-8")
        else:
            raise ValueError(f"Unsupported resume format: {path.suffix}")
        return self.parse_text(text)

    def parse_text(self, text: str) -> dict[str, Any]:
        return {
            "skills": self._extract_skills(text),
            "experience_years": self._estimate_experience_years(text),
            "titles": self._extract_titles(text),
        }

    def _read_docx(self, path: Path) -> str:
        from docx import Document

        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)

    def _read_pdf(self, path: Path) -> str:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    def _extract_skills(self, text: str) -> list[str]:
        taxonomy = _load_taxonomy()
        found: list[str] = []
        text_lower = text.lower()
        for skill in taxonomy:
            if re.search(rf"\b{re.escape(skill.lower())}\b", text_lower):
                found.append(skill)
        return found

    def _estimate_experience_years(self, text: str) -> int | None:
        # TODO: parse date ranges from work history sections
        return None

    def _extract_titles(self, text: str) -> list[str]:
        # TODO: NER with spaCy
        return []


class JobDescriptionParser:
    """Extracts structured requirements from a job description string."""

    def parse(self, description: str) -> dict[str, Any]:
        taxonomy = _load_taxonomy()
        text_lower = description.lower()
        required: list[str] = []
        preferred: list[str] = []

        for skill in taxonomy:
            if re.search(rf"\b{re.escape(skill.lower())}\b", text_lower):
                # Heuristic: skills near "required" → required, near "preferred" → preferred
                required.append(skill)

        return {
            "required_skills": required,
            "preferred_skills": preferred,
            "experience_required": _extract_years_required(description),
        }


def _load_taxonomy() -> list[str]:
    """Flatten all skills from the taxonomy JSON into a single list."""
    if not TAXONOMY_PATH.exists():
        logger.warning("Skill taxonomy not found at %s", TAXONOMY_PATH)
        return []
    with TAXONOMY_PATH.open() as f:
        data = json.load(f)
    skills: list[str] = []
    for category in data.values():
        if isinstance(category, list):
            skills.extend(category)
        elif isinstance(category, dict):
            for subcategory in category.values():
                if isinstance(subcategory, list):
                    skills.extend(subcategory)
    return list(set(skills))


def _extract_years_required(text: str) -> int | None:
    match = re.search(r"(\d+)\+?\s*years?\s+(?:of\s+)?experience", text, re.IGNORECASE)
    return int(match.group(1)) if match else None
