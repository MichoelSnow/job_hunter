from datetime import date
from types import SimpleNamespace

from scripts.cleanup_duplicate_jobs import find_duplicate_groups


def _job(
    job_id: int,
    discovered_date: date,
    url: str,
    description: str,
    *,
    company_name: str = "Arlo",
    title: str = "Head of Data & Machine Learning",
    source: str = "jsearch_api",
):
    return SimpleNamespace(
        id=job_id,
        discovered_date=discovered_date,
        application_url=url,
        description=description,
        company_name=company_name,
        title=title,
        source=source,
    )


def test_groups_exact_snapshots_and_orders_earliest_first():
    jobs = [
        _job(3, date(2026, 4, 3), "https://example.com/apply/", "same description"),
        _job(1, date(2026, 4, 1), "https://example.com/apply", "same description"),
        _job(2, date(2026, 4, 2), "https://example.com/apply", "changed description"),
    ]

    groups = find_duplicate_groups(jobs)

    assert [[job.id for job in group] for group in groups] == [[1, 3]]


def test_groups_cross_source_jobs_with_different_urls_when_content_matches():
    jobs = [
        _job(
            1,
            date(2026, 8, 23),
            "https://www.linkedin.com/jobs/view/123",
            "The same\njob description.",
        ),
        _job(
            2,
            date(2026, 8, 23),
            "https://jobs.ashbyhq.com/arlo/456",
            "The same job description.",
            source="ashby",
        ),
    ]

    groups = find_duplicate_groups(jobs)

    assert [[job.id for job in group] for group in groups] == [[2, 1]]


def test_groups_high_similarity_descriptions_after_normalizing_bullets():
    base_description = "Build the platform and lead the team. " * 100
    jobs = [
        _job(
            1,
            date(2026, 8, 23),
            "https://www.linkedin.com/jobs/view/123",
            f"Responsibilities • {base_description}",
        ),
        _job(
            2,
            date(2026, 8, 23),
            "https://jobs.ashbyhq.com/arlo/456",
            f"Responsibilities - {base_description}with care",
        ),
    ]

    groups = find_duplicate_groups(jobs)

    assert [[job.id for job in group] for group in groups] == [[1, 2]]


def test_does_not_group_descriptions_below_similarity_threshold():
    jobs = [
        _job(
            1,
            date(2026, 8, 23),
            "https://www.linkedin.com/jobs/view/123",
            "We are hiring a data leader to build our platform and lead the team.",
        ),
        _job(
            2,
            date(2026, 8, 23),
            "https://jobs.ashbyhq.com/arlo/456",
            "We are hiring a data leader to build our platform and manage a team.",
        ),
    ]

    groups = find_duplicate_groups(jobs)

    assert groups == []
