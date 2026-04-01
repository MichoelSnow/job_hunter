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
    # Sort by level descending so higher-seniority keywords win ties (e.g. "vp" beats "engineer"
    # in "VP of Engineering"). Use word-boundary matching to avoid "engineer" matching "engineering".
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

    def score(
        self, job: dict[str, Any], criteria: list[dict[str, Any]]
    ) -> tuple[float, float, float]:
        """
        Returns (user_to_job, job_to_user, overall) scores, each 0-100.
        job: normalized job dict (from aggregator or DB row as dict) — should include
             required_skills, experience_required, and title.
        criteria: list of UserCriteria dicts (soft criteria only)
        """
        user_to_job = self._score_user_to_job(job)
        job_to_user = self._score_job_to_user(job, criteria)
        overall = (
            user_to_job * self.settings.user_to_job_weight
            + job_to_user * self.settings.job_to_user_weight
        )
        return round(user_to_job, 1), round(job_to_user, 1), round(overall, 1)

    def _score_user_to_job(self, job: dict[str, Any]) -> float:
        """Skill overlap + experience + title alignment."""
        required = job.get("required_skills", [])

        if required:
            overlap = len(set(self._user_skills) & set(required))
            skill_score = min(overlap / len(required), 1.0) * 100
        else:
            skill_score = 50.0  # neutral when no requirements parsed

        score = skill_score * self.settings.skill_match_weight
        score += self._score_experience(job) * self.settings.experience_match_weight
        score += self._score_title(job) * self.settings.title_match_weight
        # education_match_weight slot kept at neutral (50) until education parsing is added
        score += 50.0 * self.settings.education_match_weight

        return min(score, 100.0)

    def _score_experience(self, job: dict[str, Any]) -> float:
        """Full score if user meets required years; proportional otherwise."""
        user_years = self.user_profile.get("experience_years")
        if user_years is None:
            return 50.0  # neutral — no data

        job_years = job.get("experience_required")
        if job_years is None:
            return 75.0  # neutral-positive when job doesn't specify

        if user_years >= job_years:
            return 100.0
        return min(user_years / job_years * 100, 100.0)

    def _score_title(self, job: dict[str, Any]) -> float:
        """Compare seniority level of user's current title vs the job title."""
        user_title = self.user_profile.get("current_title") or ""
        job_title = job.get("title") or ""

        user_level = _title_level(user_title)
        job_level = _title_level(job_title)

        if user_level is None or job_level is None:
            return 50.0  # neutral when level can't be determined

        diff = abs(user_level - job_level)
        if diff == 0:
            return 100.0
        elif diff == 1:
            return 75.0
        elif diff == 2:
            return 50.0
        else:
            return 25.0

    def _score_job_to_user(self, job: dict[str, Any], criteria: list[dict[str, Any]]) -> float:
        """Score how well the job satisfies the user's soft criteria."""
        score = 0.0
        for criterion in criteria:
            if criterion.get("is_hard_requirement"):
                continue
            weight = criterion.get("weight", 1.0)
            if self._criterion_matches(job, criterion):
                score += weight * 20  # scaled contribution

        return min(score, 100.0)

    def _criterion_matches(self, job: dict[str, Any], criterion: dict[str, Any]) -> bool:
        ctype = criterion.get("criterion_type", "")
        cvalue = (criterion.get("criterion_value") or "").lower()

        if ctype == "industry":
            company_industry = (job.get("company_industry") or "").lower()
            return any(v.strip() in company_industry for v in cvalue.split(","))

        if ctype == "min_salary":
            try:
                min_sal = int(cvalue)
                return (job.get("salary_min") or 0) >= min_sal
            except ValueError:
                return False

        return False

    def _flatten_skills(self, skills: dict | list) -> list[str]:
        if isinstance(skills, list):
            return [s.get("name", s) if isinstance(s, dict) else s for s in skills]
        flat: list[str] = []
        for value in skills.values():
            if isinstance(value, list):
                flat.extend(
                    s.get("name", s) if isinstance(s, dict) else s for s in value
                )
        return flat
