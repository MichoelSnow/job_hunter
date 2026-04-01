"""Bidirectional match scoring between user profile and job listings."""
import logging
from typing import Any

from app.config.settings import Settings

logger = logging.getLogger(__name__)


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
        job: normalized job dict (from aggregator or DB row as dict)
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
        score = 0.0
        required = job.get("required_skills", [])

        if required:
            overlap = len(set(self._user_skills) & set(required))
            skill_score = min(overlap / len(required), 1.0) * 100
        else:
            skill_score = 50.0  # neutral when no requirements parsed

        score += skill_score * self.settings.skill_match_weight

        # TODO: experience match (Phase 1)
        # TODO: title match (Phase 1)
        # TODO: education match (Phase 1)

        return min(score, 100.0)

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
        cvalue = criterion.get("criterion_value", "").lower()

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
