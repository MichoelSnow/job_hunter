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


class TestResumeMatchScoring:
    def test_skill_overlap_increases_score(self):
        engine = _engine()
        high = _job(required_skills=["Python", "SQL"], experience_required=8, title="Director")
        low = _job(required_skills=["Java", "Kubernetes"], experience_required=8, title="Director")
        high_score = engine.score(high)[0]
        low_score = engine.score(low)[0]
        assert high_score > low_score

    def test_experience_gap_lowers_score(self):
        engine = _engine(experience_years=5)
        easy = _job(required_skills=["Python"], experience_required=3, title="Director")
        hard = _job(required_skills=["Python"], experience_required=12, title="Director")
        assert engine.score(easy)[0] > engine.score(hard)[0]

    def test_title_alignment_affects_score(self):
        aligned = _engine(current_title="Director of Data")
        misaligned = _engine(current_title="Data Analyst")
        job = _job(required_skills=["Python"], experience_required=8, title="Director of Analytics")
        assert aligned.score(job)[0] > misaligned.score(job)[0]

    def test_missing_all_match_inputs_returns_zero(self):
        engine = _engine(experience_years=None, current_title=None, skills=[])
        score = engine.score(
            _job(required_skills=[], experience_required=None, title="Unknown Role")
        )[0]
        assert score == 0.0

    def test_all_score_fields_are_equal(self):
        engine = _engine()
        job = _job(required_skills=["Python"], experience_required=8, title="Director")
        u2j, j2u, overall = engine.score(job)
        assert u2j == j2u == overall
