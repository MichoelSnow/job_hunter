"""Resume and job description parsing using spaCy NER and keyword matching."""
import json
import logging
import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

TAXONOMY_PATH = Path(__file__).parents[3] / "config" / "skill_taxonomy.json"
USER_PROFILE_PATH = Path(__file__).parents[3] / "config" / "user_profile.yaml"

_TITLE_KEYWORD_RE = re.compile(
    r"\b(director|vp|vice\s+president|head\s+of|chief|manager|principal|"
    r"lead|senior|staff|data\s+scientist|analytics\s+engineer|"
    r"data\s+engineer|machine\s+learning\s+engineer|data\s+analyst)\b",
    re.IGNORECASE,
)

_YEAR_RANGE_RE = re.compile(
    r"(\d{4})\s*[-–—]\s*(present|current|\d{4})",
    re.IGNORECASE,
)

_REQUIRED_SIGNALS = [
    "required", "must have", "must-have", "mandatory", "essential", "necessary",
]
_PREFERRED_SIGNALS = [
    "preferred", "nice to have", "nice-to-have", "bonus", "a plus", "desired",
    "ideally", "a bonus", "would be a plus",
]


def load_user_profile() -> dict[str, Any]:
    """Load config/user_profile.yaml from the repo root."""
    if not USER_PROFILE_PATH.exists():
        logger.warning("user_profile.yaml not found at %s", USER_PROFILE_PATH)
        return {}
    with USER_PROFILE_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


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
        """Estimate total years of experience by summing year ranges found in text."""
        current_year = date.today().year
        total_months = 0

        for match in _YEAR_RANGE_RE.finditer(text):
            start_year = int(match.group(1))
            end_raw = match.group(2).lower()
            end_year = current_year if end_raw in ("present", "current") else int(end_raw)

            if 1970 <= start_year <= current_year and start_year <= end_year <= current_year + 1:
                total_months += (end_year - start_year) * 12

        if total_months == 0:
            return None
        return max(1, round(total_months / 12))

    def _extract_titles(self, text: str) -> list[str]:
        """Extract job titles using spaCy Matcher, falling back to regex."""
        try:
            return self._extract_titles_spacy(text)
        except Exception:
            logger.debug("spaCy title extraction failed, using regex fallback", exc_info=True)
            return self._extract_titles_regex(text)

    def _extract_titles_spacy(self, text: str) -> list[str]:
        import spacy
        from spacy.matcher import Matcher

        nlp = spacy.load("en_core_web_sm")
        matcher = Matcher(nlp.vocab)

        title_keywords = [
            "director", "vp", "head", "chief", "manager",
            "principal", "lead", "president",
        ]
        matcher.add("TITLE_KW", [[{"LOWER": kw}] for kw in title_keywords])
        matcher.add("VICE_PRES", [[{"LOWER": "vice"}, {"LOWER": "president"}]])

        doc = nlp(text[:8000])  # cap for performance
        matches = matcher(doc)

        titles: list[str] = []
        seen: set[str] = set()
        for _, start, end in matches:
            # Expand window by a few tokens to capture "Director of Data"
            tok_start = max(0, start - 1)
            tok_end = min(len(doc), end + 4)
            span_text = doc[tok_start:tok_end].text.strip()
            lower = span_text.lower()
            if 5 < len(span_text) < 80 and lower not in seen:
                seen.add(lower)
                titles.append(span_text)
        return titles

    def _extract_titles_regex(self, text: str) -> list[str]:
        titles: list[str] = []
        seen: set[str] = set()
        for line in text.splitlines():
            stripped = line.strip()
            if _TITLE_KEYWORD_RE.search(stripped) and 5 <= len(stripped) <= 100:
                lower = stripped.lower()
                if lower not in seen:
                    seen.add(lower)
                    titles.append(stripped)
        return titles[:10]


class JobDescriptionParser:
    """Extracts structured requirements from a job description string."""

    def parse(self, description: str) -> dict[str, Any]:
        taxonomy = _load_taxonomy()
        text_lower = description.lower()
        required: list[str] = []
        preferred: list[str] = []

        for skill in taxonomy:
            pattern = rf"\b{re.escape(skill.lower())}\b"
            match = re.search(pattern, text_lower)
            if match is None:
                continue
            # Examine a window of 300 chars around the skill mention for context signals
            start = max(0, match.start() - 300)
            end = min(len(text_lower), match.end() + 300)
            context = text_lower[start:end]

            if any(sig in context for sig in _PREFERRED_SIGNALS):
                preferred.append(skill)
            else:
                required.append(skill)

        return {
            "required_skills": required,
            "preferred_skills": preferred,
            "experience_required": _extract_years_required(description),
        }


_taxonomy_cache: list[str] | None = None


def _load_taxonomy() -> list[str]:
    """Flatten all skills from the taxonomy JSON into a single list. Result is cached."""
    global _taxonomy_cache
    if _taxonomy_cache is not None:
        return _taxonomy_cache
    if not TAXONOMY_PATH.exists():
        logger.warning("Skill taxonomy not found at %s", TAXONOMY_PATH)
        _taxonomy_cache = []
        return _taxonomy_cache
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
    _taxonomy_cache = list(set(skills))
    return _taxonomy_cache


def _extract_years_required(text: str) -> int | None:
    match = re.search(r"(\d+)\+?\s*years?\s+(?:of\s+)?experience", text, re.IGNORECASE)
    return int(match.group(1)) if match else None
