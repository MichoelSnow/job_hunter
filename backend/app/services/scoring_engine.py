"""Bidirectional match scoring between user profile and job listings."""

import logging
import re
from typing import Any

from app.config.settings import Settings

logger = logging.getLogger(__name__)

# Seniority level map: keyword → numeric level (higher = more senior)
_LEVEL_MAP: dict[str, int] = {
    "analyst": 0,
    "engineer": 0,
    "scientist": 0,
    "developer": 0,
    "associate": 0,
    "senior": 1,
    "staff": 1,
    "lead": 2,
    "principal": 2,
    "manager": 3,
    "director": 4,
    "head": 5,
    "vp": 5,
    "vice president": 5,
    "chief": 6,
    "cto": 6,
    "cdo": 6,
    "cio": 6,
}


def _title_level(title: str) -> int | None:
    """Return a numeric seniority level for a title string, or None if unrecognised."""
    title_lower = title.lower()
    # Sort by level descending so higher-seniority keywords win ties (e.g. "vp" beats
    # "engineer" in "VP of Engineering"). Use word-boundary matching to avoid
    # "engineer" matching "engineering".
    for keyword in sorted(_LEVEL_MAP, key=lambda k: (_LEVEL_MAP[k], len(k)), reverse=True):
        if re.search(rf"\b{re.escape(keyword)}\b", title_lower):
            return _LEVEL_MAP[keyword]
    return None


class ScoringEngine:
    """
    Calculates two match scores per job:
      - user_to_job: how well the user meets the job's requirements (0-100)
      - job_to_user: how well the job meets the user's soft preferences (0-100)
      - overall: weighted combination of both
    """

    def __init__(self, settings: Settings, user_profile: dict[str, Any]) -> None:
        self.settings = settings
        self.user_profile = user_profile
        self._user_skills: list[str] = self._flatten_skills(user_profile.get("skills", {}))

    def score(self, job: dict[str, Any]) -> tuple[float, float, float]:
        """
        Returns (user_to_job, job_to_user, overall) scores, each 0-100.
        job: normalized job dict (from aggregator or DB row as dict) — should include
             required_skills, experience_required, and title.
        """
        resume_match = self._score_resume_match(job)
        return round(resume_match, 1), round(resume_match, 1), round(resume_match, 1)

    def explain(self, job: dict[str, Any]) -> dict[str, Any]:
        """Return detailed score components and skills overlap for UI explanations."""
        required = [str(s) for s in (job.get("required_skills") or []) if s]
        user_skills = [str(s) for s in self._user_skills if s]
        required_set = {s.lower(): s for s in required}
        user_set = {s.lower(): s for s in user_skills}

        matched_keys = sorted(set(required_set) & set(user_set))
        missing_keys = sorted(set(required_set) - set(user_set))
        matched_skills = [required_set[k] for k in matched_keys]
        missing_skills = [required_set[k] for k in missing_keys]

        skill_score = self._score_skills(job)
        experience_score = self._score_experience(job)
        title_score = self._score_title(job)
        overall = self._score_resume_match(job)

        return {
            "score_breakdown": {
                "skills": None if skill_score is None else round(skill_score, 1),
                "experience": None if experience_score is None else round(experience_score, 1),
                "title": None if title_score is None else round(title_score, 1),
                "overall": round(overall, 1),
            },
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
        }

    def _score_resume_match(self, job: dict[str, Any]) -> float:
        """Resume/profile-to-job match using only extracted profile signals."""
        components: list[float] = []

        skill_score = self._score_skills(job)
        if skill_score is not None:
            components.append(skill_score)

        experience_score = self._score_experience(job)
        if experience_score is not None:
            components.append(experience_score)

        title_score = self._score_title(job)
        if title_score is not None:
            components.append(title_score)

        if not components:
            return 0.0

        return min(sum(components) / len(components), 100.0)

    def _score_skills(self, job: dict[str, Any]) -> float | None:
        required = job.get("required_skills", [])
        if not required:
            return None

        overlap = len(set(self._user_skills) & set(required))
        return min(overlap / len(required), 1.0) * 100

    def _score_experience(self, job: dict[str, Any]) -> float | None:
        """Full score if user meets required years; proportional otherwise."""
        user_years = self.user_profile.get("experience_years")
        if user_years is None:
            return None

        job_years = job.get("experience_required")
        if job_years is None:
            return None

        if user_years >= job_years:
            return 100.0
        return min(user_years / job_years * 100, 100.0)

    def _score_title(self, job: dict[str, Any]) -> float | None:
        """Compare seniority level of user's current title vs the job title."""
        user_title = self.user_profile.get("current_title") or ""
        job_title = job.get("title") or ""

        user_level = _title_level(user_title)
        job_level = _title_level(job_title)

        if user_level is None or job_level is None:
            return None

        diff = abs(user_level - job_level)
        if diff == 0:
            return 100.0
        elif diff == 1:
            return 75.0
        elif diff == 2:
            return 50.0
        else:
            return 25.0

    def _flatten_skills(self, skills: dict | list) -> list[str]:
        if isinstance(skills, list):
            return [s.get("name", s) if isinstance(s, dict) else s for s in skills]
        flat: list[str] = []
        for value in skills.values():
            if isinstance(value, list):
                flat.extend(s.get("name", s) if isinstance(s, dict) else s for s in value)
        return flat
