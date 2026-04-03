import pytest

from app.services.job_filter import JobFilter


@pytest.fixture
def job_filter() -> JobFilter:
    return JobFilter(
        allowed_locations=["New York, NY"],
        title_keywords=[
            "director",
            "vp",
            "vice president",
            "head of",
            "chief",
            "lead",
            "manager",
            "principal",
        ],
    )


def _make_job(**kwargs) -> dict:
    defaults = {
        "title": "Director of Data",
        "description": "Join our team in Manhattan.",
        "location": "Manhattan, NY",
        "work_arrangement": "in_office",
    }
    defaults.update(kwargs)
    return defaults


class TestLocationFilter:
    def test_passes_manhattan(self, job_filter):
        assert job_filter._passes_location(_make_job(location="Manhattan, NY"))

    def test_passes_brooklyn(self, job_filter):
        assert job_filter._passes_location(_make_job(location="Brooklyn, NY"))

    def test_rejects_san_francisco(self, job_filter):
        assert not job_filter._passes_location(_make_job(location="San Francisco, CA"))

    def test_rejects_empty_location(self, job_filter):
        assert not job_filter._passes_location(_make_job(location=""))

    def test_passes_when_no_location_filters_configured(self):
        filter_no_location = JobFilter(allowed_locations=[])
        assert filter_no_location._passes_location(_make_job(location="San Francisco, CA"))


class TestWorkArrangementFilter:
    def test_passes_in_office(self, job_filter):
        assert job_filter._passes_work_arrangement(_make_job(work_arrangement="in_office"))

    def test_passes_hybrid(self, job_filter):
        assert job_filter._passes_work_arrangement(_make_job(work_arrangement="hybrid"))

    def test_rejects_remote_arrangement(self, job_filter):
        assert not job_filter._passes_work_arrangement(_make_job(work_arrangement="remote"))

    def test_rejects_fully_remote_in_description(self, job_filter):
        job = _make_job(
            work_arrangement="unknown",
            description="This is a fully remote position.",
        )
        assert not job_filter._passes_work_arrangement(job)

    def test_remote_allowed_when_toggle_disabled(self):
        filter_with_remote = JobFilter(allowed_locations=["New York, NY"], exclude_remote=False)
        assert filter_with_remote._passes_work_arrangement(_make_job(work_arrangement="remote"))


class TestRoleLevelFilter:
    def test_passes_director(self, job_filter):
        assert job_filter._passes_role_level(_make_job(title="Director of Data Engineering"))

    def test_passes_vp(self, job_filter):
        assert job_filter._passes_role_level(_make_job(title="VP of Analytics"))

    def test_passes_head_of(self, job_filter):
        assert job_filter._passes_role_level(_make_job(title="Head of Data"))

    def test_rejects_junior(self, job_filter):
        assert not job_filter._passes_role_level(_make_job(title="Junior Data Analyst"))

    def test_rejects_analyst(self, job_filter):
        assert not job_filter._passes_role_level(_make_job(title="Data Analyst"))

    def test_role_filter_can_be_disabled(self):
        role_disabled = JobFilter(allowed_locations=["New York, NY"], title_keywords=[])
        assert role_disabled._passes_role_level(_make_job(title="Data Analyst"))


class TestApplyAll:
    def test_filters_out_failing_jobs(self, job_filter):
        jobs = [
            _make_job(location="Manhattan, NY", title="Director of Data"),
            _make_job(location="San Francisco, CA", title="Director of Data"),
            _make_job(location="Manhattan, NY", title="Junior Analyst"),
        ]
        result = job_filter.apply_all(jobs)
        assert len(result) == 1
        assert result[0]["title"] == "Director of Data"


class TestSalaryFilter:
    def test_passes_when_minimum_salary_in_range(self):
        filt = JobFilter(target_salary=190000)
        assert filt._passes_salary(_make_job(salary_min=170000, salary_max=200000))

    def test_passes_when_range_starts_above_minimum_salary(self):
        filt = JobFilter(target_salary=190000)
        assert filt._passes_salary(_make_job(salary_min=210000, salary_max=230000))

    def test_rejects_when_range_cannot_meet_minimum_salary(self):
        filt = JobFilter(target_salary=190000)
        assert not filt._passes_salary(_make_job(salary_min=120000, salary_max=150000))

    def test_missing_salary_respects_checkbox(self):
        include_missing = JobFilter(target_salary=180000, include_missing_salary=True)
        exclude_missing = JobFilter(target_salary=180000, include_missing_salary=False)
        job = _make_job(salary_min=None, salary_max=None)
        assert include_missing._passes_salary(job)
        assert not exclude_missing._passes_salary(job)
