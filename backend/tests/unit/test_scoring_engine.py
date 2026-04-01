import pytest

from app.config.settings import Settings
from app.services.scoring_engine import ScoringEngine, _title_level


def _settings(**overrides):
    defaults = dict(
        jsearchapi_key="",
        serplyapi_key="",
        skill_match_weight=0.50,
        experience_match_weight=0.25,
        title_match_weight=0.15,
        education_match_weight=0.10,
        user_to_job_weight=0.6,
        job_to_user_weight=0.4,
    )
    defaults.update(overrides)
    return Settings(**defaults)


def _profile(**overrides):
    base = {
        "experience_years": 10,
        "current_title": "Director of Data",
        "skills": {
            "technical": [{"name": "Python"}, {"name": "SQL"}],
            "leadership": ["team management"],
        },
    }
    base.update(overrides)
    return base


def _engine(**profile_overrides):
    return ScoringEngine(_settings(), _profile(**profile_overrides))


def _job(**kwargs):
    base = {"title": "Director of Data", "required_skills": []}
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# _title_level helper
# ---------------------------------------------------------------------------

class TestTitleLevel:
    def test_director(self):
        assert _title_level("Director of Data") == 4

    def test_vp(self):
        assert _title_level("VP of Engineering") == 5

    def test_vice_president(self):
        assert _title_level("Vice President of Analytics") == 5

    def test_chief(self):
        assert _title_level("Chief Data Officer") == 6

    def test_manager(self):
        assert _title_level("Analytics Manager") == 3

    def test_unknown(self):
        assert _title_level("Underwater Basket Weaver") is None


# ---------------------------------------------------------------------------
# Skill scoring
# ---------------------------------------------------------------------------

class TestSkillScoring:
    def test_full_overlap_raises_score(self):
        engine = _engine()
        job = _job(required_skills=["Python", "SQL"])
        u2j, _, _ = engine.score(job, [])
        # With 2/2 skills matched, skill_score=100 * 0.5 = 50
        # plus experience and title contributions → well above 50
        assert u2j > 60

    def test_no_overlap_lowers_score(self):
        engine = _engine()
        job = _job(required_skills=["Java", "Kubernetes"])
        u2j_no_match, _, _ = engine.score(job, [])
        job_match = _job(required_skills=["Python", "SQL"])
        u2j_match, _, _ = engine.score(job_match, [])
        assert u2j_no_match < u2j_match

    def test_empty_requirements_gives_neutral_skill_score(self):
        engine = _engine()
        job = _job(required_skills=[])
        u2j, _, _ = engine.score(job, [])
        # skill_score neutral (50 * 0.5 = 25), but experience and title add more
        assert u2j > 0


# ---------------------------------------------------------------------------
# Experience scoring
# ---------------------------------------------------------------------------

class TestExperienceScoring:
    def test_exceeds_requirement_gets_full_score(self):
        engine_high = _engine(experience_years=12)
        engine_low = _engine(experience_years=5)
        job = _job(experience_required=10)
        u2j_high, _, _ = engine_high.score(job, [])
        u2j_low, _, _ = engine_low.score(job, [])
        assert u2j_high > u2j_low

    def test_meets_requirement_exactly(self):
        engine = _engine(experience_years=10)
        job = _job(experience_required=10)
        u2j_exact, _, _ = engine.score(job, [])
        engine_under = _engine(experience_years=8)
        u2j_under, _, _ = engine_under.score(job, [])
        assert u2j_exact > u2j_under

    def test_no_experience_data_neutral(self):
        engine = _engine(experience_years=None)
        job = _job()  # no experience_required either
        u2j, _, _ = engine.score(job, [])
        assert u2j > 0  # should still produce a score

    def test_no_job_requirement_gives_neutral_positive(self):
        # When job doesn't specify experience, we give a neutral-positive 75
        engine = _engine(experience_years=5)
        job_no_req = _job(experience_required=None)
        job_high_req = _job(experience_required=20)
        u2j_no_req, _, _ = engine.score(job_no_req, [])
        u2j_high_req, _, _ = engine.score(job_high_req, [])
        assert u2j_no_req > u2j_high_req


# ---------------------------------------------------------------------------
# Title / level scoring
# ---------------------------------------------------------------------------

class TestTitleScoring:
    def test_same_level_beats_different_level(self):
        engine_dir = _engine(current_title="Director of Data")
        engine_analyst = _engine(current_title="Data Analyst")
        job = _job(title="Director of Analytics")
        u2j_same, _, _ = engine_dir.score(job, [])
        u2j_diff, _, _ = engine_analyst.score(job, [])
        assert u2j_same > u2j_diff

    def test_one_level_apart_intermediate_score(self):
        engine = _engine(current_title="Manager")  # level 3
        job = _job(title="Director")               # level 4, diff=1
        u2j, _, _ = engine.score(job, [])
        # title sub-score should be 75; combined should be positive
        assert u2j > 0

    def test_unrecognised_title_neutral(self):
        engine = _engine(current_title="Grand Poobah")
        job = _job(title="Supreme Overlord")
        u2j, _, _ = engine.score(job, [])
        assert u2j > 0  # neutral, not zero


# ---------------------------------------------------------------------------
# Job-to-user scoring
# ---------------------------------------------------------------------------

class TestJobToUserScoring:
    def test_industry_match_adds_score(self):
        engine = _engine()
        job = _job(company_industry="healthcare")
        criteria = [
            {
                "criterion_type": "industry",
                "criterion_value": "healthcare",
                "weight": 2.0,
                "is_hard_requirement": False,
            }
        ]
        _, j2u, _ = engine.score(job, criteria)
        assert j2u > 0

    def test_salary_match_adds_score(self):
        engine = _engine()
        job = _job(salary_min=200_000)
        criteria = [
            {
                "criterion_type": "min_salary",
                "criterion_value": "150000",
                "weight": 1.0,
                "is_hard_requirement": False,
            }
        ]
        _, j2u, _ = engine.score(job, criteria)
        assert j2u > 0

    def test_salary_below_minimum_no_score(self):
        engine = _engine()
        job = _job(salary_min=80_000)
        criteria = [
            {
                "criterion_type": "min_salary",
                "criterion_value": "150000",
                "weight": 1.0,
                "is_hard_requirement": False,
            }
        ]
        _, j2u, _ = engine.score(job, criteria)
        assert j2u == 0

    def test_hard_requirement_ignored_in_j2u(self):
        engine = _engine()
        job = _job(company_industry="healthcare")
        criteria = [
            {
                "criterion_type": "industry",
                "criterion_value": "healthcare",
                "weight": 5.0,
                "is_hard_requirement": True,  # hard requirements excluded from j2u scoring
            }
        ]
        _, j2u, _ = engine.score(job, criteria)
        assert j2u == 0

    def test_j2u_capped_at_100(self):
        engine = _engine()
        job = _job(company_industry="healthcare", salary_min=300_000)
        # Many heavy criteria — should cap at 100
        criteria = [
            {"criterion_type": "industry", "criterion_value": "healthcare", "weight": 5.0, "is_hard_requirement": False},
            {"criterion_type": "min_salary", "criterion_value": "100000", "weight": 5.0, "is_hard_requirement": False},
            {"criterion_type": "industry", "criterion_value": "health", "weight": 5.0, "is_hard_requirement": False},
        ]
        _, j2u, _ = engine.score(job, criteria)
        assert j2u <= 100.0


# ---------------------------------------------------------------------------
# Overall score
# ---------------------------------------------------------------------------

class TestOverallScore:
    def test_overall_is_weighted_combination(self):
        engine = _engine()
        job = _job(required_skills=["Python", "SQL"])
        u2j, j2u, overall = engine.score(job, [])
        # overall is computed from unrounded intermediates before being rounded,
        # so allow up to 0.1 difference from the rounded-value calculation
        assert abs(overall - (u2j * 0.6 + j2u * 0.4)) <= 0.1
