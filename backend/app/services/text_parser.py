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
_MARKDOWN_HEADER_RE = re.compile(r"^\s{0,3}#{1,6}\s*(.+?)\s*$")
_WORK_SECTION_HINTS = ("experience", "employment", "work history", "professional history", "career")
_EDU_SECTION_HINTS = ("education", "certification", "certifications")
_TITLE_CLEANUP_PARENS_RE = re.compile(
    r"\([^)]*\)",
)
_TITLE_PREFIX_RE = re.compile(r"^\s*[-*#\d\.\)\s]+")

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
        titles = self._extract_titles(text)
        return {
            "skills": self._extract_skills(text),
            "experience_years": self._estimate_experience_years(text),
            "titles": titles,
            "current_title": titles[0] if titles else None,
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
        taxonomy_map = _load_taxonomy_map()
        found: list[str] = []
        seen: set[str] = set()
        text_lower = text.lower()
        for normalized_skill, canonical in taxonomy_map.items():
            if re.search(rf"\b{re.escape(normalized_skill)}\b", text_lower):
                lowered = canonical.lower()
                if lowered not in seen:
                    seen.add(lowered)
                    found.append(canonical)
        return found

    def _estimate_experience_years(self, text: str) -> int | None:
        """Estimate years from work-history ranges, excluding education sections."""
        work_text = self._work_history_text(text)
        current_year = date.today().year
        intervals: list[tuple[int, int]] = []

        for match in _YEAR_RANGE_RE.finditer(work_text):
            start_year = int(match.group(1))
            end_raw = match.group(2).lower()
            end_year = current_year if end_raw in ("present", "current") else int(end_raw)

            if 1970 <= start_year <= current_year and start_year <= end_year <= current_year + 1:
                intervals.append((start_year, min(end_year, current_year)))

        if not intervals:
            return None

        merged = _merge_year_intervals(intervals)
        total_years = sum((end - start) for start, end in merged if end > start)
        if total_years <= 0:
            return None
        return min(total_years, 40)

    def _extract_titles(self, text: str) -> list[str]:
        """Extract cleaned role titles from work-history lines."""
        experience_text = self._work_history_text(text)
        titles: list[str] = []
        seen: set[str] = set()

        for line in experience_text.splitlines():
            candidate = _clean_title_candidate(line)
            if not candidate or not _TITLE_KEYWORD_RE.search(candidate):
                continue
            lower = candidate.lower()
            if lower not in seen:
                seen.add(lower)
                titles.append(candidate)

        if titles:
            return titles[:10]

        for line in text.splitlines():
            candidate = _clean_title_candidate(line)
            if not candidate or not _TITLE_KEYWORD_RE.search(candidate):
                continue
            lower = candidate.lower()
            if lower not in seen:
                seen.add(lower)
                titles.append(candidate)
        return titles[:10]

    def _work_history_text(self, text: str) -> str:
        lines = text.splitlines()
        work_lines: list[str] = []
        in_work_section = False
        saw_work_section = False

        for raw_line in lines:
            header_match = _MARKDOWN_HEADER_RE.match(raw_line)
            if header_match:
                header_text = header_match.group(1).strip()
                header_lower = header_text.lower()
                if any(hint in header_lower for hint in _WORK_SECTION_HINTS):
                    in_work_section = True
                    saw_work_section = True
                    continue
                if any(hint in header_lower for hint in _EDU_SECTION_HINTS):
                    in_work_section = False
                    continue

                if in_work_section and _TITLE_KEYWORD_RE.search(header_text):
                    work_lines.append(header_text)
                    continue

                if in_work_section:
                    in_work_section = False
                continue

            if in_work_section:
                work_lines.append(raw_line)

        if saw_work_section and work_lines:
            return "\n".join(work_lines)

        # Fallback: remove education block heuristically, then parse remaining lines.
        cleaned_lines: list[str] = []
        in_edu_section = False
        for raw_line in lines:
            header_match = _MARKDOWN_HEADER_RE.match(raw_line)
            if header_match:
                header_lower = header_match.group(1).strip().lower()
                if any(hint in header_lower for hint in _EDU_SECTION_HINTS):
                    in_edu_section = True
                    continue
                in_edu_section = False
            if not in_edu_section:
                cleaned_lines.append(raw_line)
        return "\n".join(cleaned_lines)


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
_taxonomy_map_cache: dict[str, str] | None = None


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
    _taxonomy_cache = sorted(set(skills), key=lambda s: (len(s), s.lower()), reverse=True)
    return _taxonomy_cache


def _load_taxonomy_map() -> dict[str, str]:
    global _taxonomy_map_cache
    if _taxonomy_map_cache is not None:
        return _taxonomy_map_cache

    mapping: dict[str, str] = {}
    for skill in _load_taxonomy():
        normalized = " ".join(skill.lower().split())
        if normalized not in mapping:
            mapping[normalized] = skill
    _taxonomy_map_cache = mapping
    return _taxonomy_map_cache


def _extract_years_required(text: str) -> int | None:
    match = re.search(r"(\d+)\+?\s*years?\s+(?:of\s+)?experience", text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _merge_year_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervals:
        return []
    ordered = sorted(intervals)
    merged: list[tuple[int, int]] = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _clean_title_candidate(line: str) -> str | None:
    if not line.strip():
        return None

    candidate = _TITLE_PREFIX_RE.sub("", line.strip())
    candidate = _TITLE_CLEANUP_PARENS_RE.sub("", candidate).strip(" -|,:")
    # Common resume pattern: "<Title>, <Company>"
    if "," in candidate:
        candidate = candidate.split(",", 1)[0].strip()
    # Alternate pattern: "<Title> at <Company>"
    if re.search(r"\bat\b", candidate, re.IGNORECASE):
        candidate = re.split(r"\bat\b", candidate, maxsplit=1, flags=re.IGNORECASE)[0].strip()

    candidate = re.sub(r"\s+", " ", candidate).strip()
    if len(candidate) < 5 or len(candidate) > 90:
        return None
    return candidate
