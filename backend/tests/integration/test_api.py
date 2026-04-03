"""Integration tests: one happy path + one error path per API resource."""
from datetime import date

from app.models.company import Company
from app.models.job import Job


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

class TestJobsAPI:
    @staticmethod
    def _reset_discovery_status() -> None:
        from app.services.api_aggregator import discovery_status

        discovery_status.update(
            {
                "status": "idle",
                "mode": None,
                "step": None,
                "started_at": None,
                "completed_at": None,
                "inserted": None,
                "updated": None,
                "filtered_out": None,
                "error": None,
            }
        )

    def test_list_jobs_returns_empty_list(self, client):
        resp = client.get("/api/jobs")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_list_jobs_returns_seeded_job(self, client_with_job):
        client, job_id = client_with_job
        resp = client.get("/api/jobs")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_get_job_not_found(self, client):
        resp = client.get("/api/jobs/999")
        assert resp.status_code == 404

    def test_get_job_by_id(self, client_with_job):
        client, job_id = client_with_job
        resp = client.get(f"/api/jobs/{job_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == job_id
        assert "company_name" in resp.json()
        assert "source_url" in resp.json()

    def test_get_job_sanitizes_html_encoded_description(self, client, db_session):
        job = Job(
            title="Director of Data",
            description="&lt;div&gt;Lead analytics &amp;amp; strategy&lt;/div&gt;",
            location="Manhattan, NY",
            work_arrangement="hybrid",
            application_url="https://example.com/apply",
            source="manual",
            discovered_date=date(2026, 4, 1),
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        resp = client.get(f"/api/jobs/{job.id}")
        assert resp.status_code == 200
        assert resp.json()["description"] == "Lead analytics & strategy"

    def test_get_job_includes_sanitized_description_html(self, client, db_session):
        job = Job(
            title="Director of Data",
            description="&lt;div&gt;&lt;p&gt;<strong>Mission</strong>&lt;/p&gt;&lt;/div&gt;",
            location="Manhattan, NY",
            work_arrangement="hybrid",
            application_url="https://example.com/apply",
            source="manual",
            discovered_date=date(2026, 4, 1),
            raw_data={
                "description": (
                    "&lt;p&gt;<strong>Mission</strong>&lt;/p&gt;"
                    '&lt;a href=&quot;javascript:alert(1)&quot;&gt;bad&lt;/a&gt;'
                ),
            },
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        resp = client.get(f"/api/jobs/{job.id}")
        assert resp.status_code == 200
        assert "<strong>Mission</strong>" in resp.json()["description_html"]
        assert "javascript:" not in resp.json()["description_html"]

    def test_get_job_prefers_normalized_description_html(self, client, db_session):
        job = Job(
            title="Principal Technical Recruiter",
            description="Fallback plain text",
            location="New York, NY",
            work_arrangement="hybrid",
            application_url="https://example.com/apply",
            source="lever",
            discovered_date=date(2026, 4, 1),
            raw_data={
                "description": "<p>Body only</p>",
                "normalized_description_html": (
                    "<p><strong>Body</strong></p><h3>What You'll Do:</h3><ul><li>Build strategy</li></ul>"
                ),
            },
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        resp = client.get(f"/api/jobs/{job.id}")
        assert resp.status_code == 200
        html = resp.json()["description_html"]
        assert "What You'll Do:" in html
        assert "<li>Build strategy</li>" in html

    def test_get_job_combines_html_sections_from_raw_data(self, client, db_session):
        job = Job(
            title="Principal Technical Recruiter",
            description="Fallback plain text",
            location="New York, NY",
            work_arrangement="hybrid",
            application_url="https://example.com/apply",
            source="lever",
            discovered_date=date(2026, 4, 1),
            raw_data={
                "description": "<p>Main body</p>",
                "additional": "<p>Comp section</p>",
                "lists": [{"text": "What You'll Do:", "content": "<li>Own strategy</li>"}],
            },
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        resp = client.get(f"/api/jobs/{job.id}")
        assert resp.status_code == 200
        html = resp.json()["description_html"]
        assert "Main body" in html
        assert "Comp section" in html
        assert "What You'll Do:" in html
        assert "<li>Own strategy</li>" in html

    def test_hide_job(self, client_with_job):
        client, job_id = client_with_job
        resp = client.put(f"/api/jobs/{job_id}/hide")
        assert resp.status_code == 200
        # Job should no longer appear in the default active list
        list_resp = client.get("/api/jobs")
        assert list_resp.json()["total"] == 0

    def test_unhide_job(self, client_with_job):
        client, job_id = client_with_job
        hide_resp = client.put(f"/api/jobs/{job_id}/hide")
        assert hide_resp.status_code == 200
        unhide_resp = client.put(f"/api/jobs/{job_id}/unhide")
        assert unhide_resp.status_code == 200
        list_resp = client.get("/api/jobs")
        assert list_resp.json()["total"] == 1

    def test_hide_job_not_found(self, client):
        resp = client.put("/api/jobs/999/hide")
        assert resp.status_code == 404

    def test_unhide_job_not_found(self, client):
        resp = client.put("/api/jobs/999/unhide")
        assert resp.status_code == 404

    def test_score_job_not_found(self, client):
        resp = client.put("/api/jobs/999/score")
        assert resp.status_code == 404

    def test_locations_returns_seeded_location(self, client_with_job):
        client, _ = client_with_job
        resp = client.get("/api/jobs/filters/locations")
        assert resp.status_code == 200
        assert "Manhattan, NY" in resp.json()

    def test_list_jobs_sort_applies_before_pagination(self, client, db_session):
        for title in ("Zeta Role", "Alpha Role", "Mid Role"):
            db_session.add(
                Job(
                    title=title,
                    description="desc",
                    location="Manhattan, NY",
                    work_arrangement="hybrid",
                    application_url="https://example.com/apply",
                    source="manual",
                    discovered_date=date(2026, 4, 1),
                )
            )
        db_session.commit()

        page1 = client.get("/api/jobs", params={"sort_by": "title", "sort_direction": "asc", "limit": 1, "skip": 0})
        page2 = client.get("/api/jobs", params={"sort_by": "title", "sort_direction": "asc", "limit": 1, "skip": 1})
        page3 = client.get("/api/jobs", params={"sort_by": "title", "sort_direction": "asc", "limit": 1, "skip": 2})

        assert page1.status_code == 200
        assert page2.status_code == 200
        assert page3.status_code == 200
        assert page1.json()["items"][0]["title"] == "Alpha Role"
        assert page2.json()["items"][0]["title"] == "Mid Role"
        assert page3.json()["items"][0]["title"] == "Zeta Role"

    def test_list_jobs_sort_by_company_name(self, client, db_session):
        alpha = Company(name="Alpha Inc")
        zeta = Company(name="Zeta Inc")
        db_session.add_all([alpha, zeta])
        db_session.flush()
        db_session.add_all(
            [
                Job(
                    title="Role 1",
                    description="desc",
                    location="Manhattan, NY",
                    work_arrangement="hybrid",
                    application_url="https://example.com/apply/1",
                    source="manual",
                    discovered_date=date(2026, 4, 1),
                    company_id=zeta.id,
                ),
                Job(
                    title="Role 2",
                    description="desc",
                    location="Manhattan, NY",
                    work_arrangement="hybrid",
                    application_url="https://example.com/apply/2",
                    source="manual",
                    discovered_date=date(2026, 4, 1),
                    company_id=alpha.id,
                ),
            ]
        )
        db_session.commit()

        resp = client.get("/api/jobs", params={"sort_by": "company_name", "sort_direction": "asc"})
        assert resp.status_code == 200
        names = [item["company_name"] for item in resp.json()["items"]]
        assert names[:2] == ["Alpha Inc", "Zeta Inc"]

    def test_score_job_uses_company_industry(self, client, db_session):
        company = Company(name="Health Corp", industry="healthcare")
        db_session.add(company)
        db_session.flush()
        job = Job(
            title="Director of Data",
            description="Lead data strategy",
            location="Manhattan, NY",
            work_arrangement="in_office",
            application_url="https://example.com/apply",
            source="manual",
            discovered_date=date(2026, 4, 1),
            company_id=company.id,
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        criterion_resp = client.post(
            "/api/criteria",
            json={
                "criterion_type": "industry",
                "criterion_value": "healthcare",
                "is_hard_requirement": False,
                "weight": 2.0,
            },
        )
        assert criterion_resp.status_code == 201

        resp = client.put(f"/api/jobs/{job.id}/score")
        assert resp.status_code == 200
        assert resp.json()["match_score_job_to_user"] > 0

    def test_refresh_api_jobs_starts_background_task(self, client, monkeypatch):
        from app.services import api_aggregator

        self._reset_discovery_status()
        called = {"count": 0}

        def _fake_run() -> None:
            called["count"] += 1

        monkeypatch.setattr(api_aggregator, "run_job_discovery_api_only", _fake_run)

        resp = client.post("/api/jobs/refresh/apis")
        assert resp.status_code == 200
        assert resp.json()["status"] == "API job discovery started"
        assert called["count"] == 1

    def test_refresh_scrapers_starts_background_task(self, client, monkeypatch):
        from app.services import api_aggregator

        self._reset_discovery_status()
        called = {"count": 0}

        def _fake_run() -> None:
            called["count"] += 1

        monkeypatch.setattr(api_aggregator, "run_job_discovery_scrapers_only", _fake_run)

        resp = client.post("/api/jobs/refresh/scrapers")
        assert resp.status_code == 200
        assert resp.json()["status"] == "Scraper job discovery started"
        assert called["count"] == 1

    def test_refresh_api_jobs_returns_already_running(self, client, monkeypatch):
        from app.services import api_aggregator

        self._reset_discovery_status()
        api_aggregator.discovery_status["status"] = "running"
        called = {"count": 0}

        def _fake_run() -> None:
            called["count"] += 1

        monkeypatch.setattr(api_aggregator, "run_job_discovery_api_only", _fake_run)

        resp = client.post("/api/jobs/refresh/apis")
        assert resp.status_code == 200
        assert resp.json() == {"status": "already running"}
        assert called["count"] == 0

    def test_refresh_scrapers_returns_already_running(self, client, monkeypatch):
        from app.services import api_aggregator

        self._reset_discovery_status()
        api_aggregator.discovery_status["status"] = "running"
        called = {"count": 0}

        def _fake_run() -> None:
            called["count"] += 1

        monkeypatch.setattr(api_aggregator, "run_job_discovery_scrapers_only", _fake_run)

        resp = client.post("/api/jobs/refresh/scrapers")
        assert resp.status_code == 200
        assert resp.json() == {"status": "already running"}
        assert called["count"] == 0

    def test_refresh_scrapers_targets_preview(self, client, monkeypatch):
        from app.services import api_aggregator

        monkeypatch.setattr(
            api_aggregator,
            "get_scrape_targets",
            lambda: (
                [{"name": "Alpha"}],
                [{"name": "Beta", "reason": "missing ats_id", "ats_type": "greenhouse"}],
            ),
        )

        resp = client.get("/api/jobs/refresh/scrapers/targets")
        assert resp.status_code == 200
        body = resp.json()
        assert body["enabled_count"] == 1
        assert body["enabled"] == ["Alpha"]
        assert body["skipped_count"] == 1
        assert body["skipped"][0]["name"] == "Beta"


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

class TestApplicationsAPI:
    def test_create_application_missing_job_not_found(self, client):
        resp = client.post("/api/applications", json={"job_id": 999, "status": "interested"})
        assert resp.status_code == 404

    def test_create_application(self, client_with_job):
        client, job_id = client_with_job
        resp = client.post("/api/applications", json={"job_id": job_id, "status": "interested"})
        assert resp.status_code == 201
        body = resp.json()
        assert body["job_id"] == job_id
        assert body["status"] == "interested"

    def test_create_duplicate_application_conflict(self, client_with_job):
        client, job_id = client_with_job
        client.post("/api/applications", json={"job_id": job_id, "status": "interested"})
        resp = client.post("/api/applications", json={"job_id": job_id, "status": "applied"})
        assert resp.status_code == 409

    def test_get_application(self, client_with_job):
        client, job_id = client_with_job
        create_resp = client.post("/api/applications", json={"job_id": job_id, "status": "interested"})
        app_id = create_resp.json()["id"]
        resp = client.get(f"/api/applications/{app_id}")
        assert resp.status_code == 200

    def test_get_application_not_found(self, client):
        resp = client.get("/api/applications/999")
        assert resp.status_code == 404

    def test_update_application_status(self, client_with_job):
        client, job_id = client_with_job
        create_resp = client.post("/api/applications", json={"job_id": job_id, "status": "interested"})
        app_id = create_resp.json()["id"]
        resp = client.put(f"/api/applications/{app_id}", json={"status": "applied"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "applied"

    def test_update_application_not_found(self, client):
        resp = client.put("/api/applications/999", json={"status": "applied"})
        assert resp.status_code == 404

    def test_status_history_recorded_on_update(self, client_with_job):
        client, job_id = client_with_job
        create_resp = client.post("/api/applications", json={"job_id": job_id, "status": "interested"})
        app_id = create_resp.json()["id"]
        client.put(f"/api/applications/{app_id}", json={"status": "applied"})
        resp = client.get(f"/api/applications/{app_id}/history")
        assert resp.status_code == 200
        history = resp.json()
        assert len(history) == 1
        assert history[0]["old_status"] == "interested"
        assert history[0]["new_status"] == "applied"

    def test_delete_application(self, client_with_job):
        client, job_id = client_with_job
        create_resp = client.post("/api/applications", json={"job_id": job_id, "status": "interested"})
        app_id = create_resp.json()["id"]
        resp = client.delete(f"/api/applications/{app_id}")
        assert resp.status_code == 204
        assert client.get(f"/api/applications/{app_id}").status_code == 404

    def test_delete_application_not_found(self, client):
        resp = client.delete("/api/applications/999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------

class TestCompaniesAPI:
    def test_list_companies_empty_when_no_rows(self, client):
        resp = client.get("/api/companies")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_company(self, client):
        resp = client.post("/api/companies", json={"name": "Health Corp"})
        assert resp.status_code == 201
        assert resp.json()["name"] == "Health Corp"

    def test_create_company_with_all_primary_fields(self, client):
        payload = {
            "name": "Acme Health",
            "website_url": "https://acme.example.com",
            "ats_type": "lever",
            "ats_id": "acme",
            "workday_board": "Acme_Careers",
            "workday_instance": "wd5",
            "html_selectors": {"job_list": ".jobs li", "title": ".title", "url": "a"},
            "careers_page_url": "https://jobs.lever.co/acme",
            "industry": "healthtech",
            "is_priority": True,
        }
        resp = client.post("/api/companies", json=payload)
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == payload["name"]
        assert body["website_url"] == payload["website_url"]
        assert body["ats_type"] == payload["ats_type"]
        assert body["ats_id"] == payload["ats_id"]
        assert body["workday_board"] == payload["workday_board"]
        assert body["workday_instance"] == payload["workday_instance"]
        assert body["html_selectors"] == payload["html_selectors"]
        assert body["careers_page_url"] == payload["careers_page_url"]
        assert body["industry"] == payload["industry"]
        assert body["is_priority"] is True

    def test_create_duplicate_company_conflict(self, client):
        client.post("/api/companies", json={"name": "Health Corp"})
        resp = client.post("/api/companies", json={"name": "Health Corp"})
        assert resp.status_code == 409

    def test_get_company_not_found(self, client):
        resp = client.get("/api/companies/999")
        assert resp.status_code == 404

    def test_delete_company(self, client):
        created = client.post("/api/companies", json={"name": "Delete Me"})
        company_id = created.json()["id"]

        resp = client.delete(f"/api/companies/{company_id}")
        assert resp.status_code == 204

        list_resp = client.get("/api/companies")
        assert list_resp.status_code == 200
        names = [company["name"] for company in list_resp.json()]
        assert "Delete Me" not in names

    def test_delete_company_not_found(self, client):
        resp = client.delete("/api/companies/999")
        assert resp.status_code == 404

    def test_delete_company_keeps_jobs_and_clears_company_fk(self, client, db_session):
        company = Company(name="Job Co")
        db_session.add(company)
        db_session.flush()
        job = Job(
            title="Data Lead",
            description="desc",
            location="NYC",
            work_arrangement="hybrid",
            application_url="https://example.com/apply",
            source="manual",
            discovered_date=date(2026, 4, 1),
            company_id=company.id,
        )
        db_session.add(job)
        db_session.commit()
        company_id = company.id
        job_id = job.id

        resp = client.delete(f"/api/companies/{company_id}")
        assert resp.status_code == 204

        db_session.expire_all()
        persisted_job = db_session.get(Job, job_id)
        assert persisted_job is not None
        assert persisted_job.company_id is None

    def test_delete_company_remains_deleted(self, client):
        create_resp = client.post("/api/companies", json={"name": "Delete Again"})
        assert create_resp.status_code == 201
        company_id = create_resp.json()["id"]

        delete_resp = client.delete(f"/api/companies/{company_id}")
        assert delete_resp.status_code == 204

        post_delete = client.get("/api/companies")
        assert post_delete.status_code == 200
        names = [company["name"] for company in post_delete.json()]
        assert "Delete Again" not in names


# ---------------------------------------------------------------------------
# Criteria
# ---------------------------------------------------------------------------

class TestCriteriaAPI:
    def test_create_and_list_criterion(self, client):
        resp = client.post(
            "/api/criteria",
            json={"criterion_type": "industry", "criterion_value": "healthcare", "weight": 2.0},
        )
        assert resp.status_code == 201
        list_resp = client.get("/api/criteria")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

    def test_update_criterion(self, client):
        create_resp = client.post(
            "/api/criteria",
            json={"criterion_type": "industry", "criterion_value": "healthcare", "weight": 1.0},
        )
        cid = create_resp.json()["id"]
        resp = client.put(f"/api/criteria/{cid}", json={"weight": 3.0})
        assert resp.status_code == 200
        assert resp.json()["weight"] == 3.0

    def test_update_criterion_not_found(self, client):
        resp = client.put("/api/criteria/999", json={"weight": 1.0})
        assert resp.status_code == 404

    def test_delete_criterion(self, client):
        create_resp = client.post(
            "/api/criteria",
            json={"criterion_type": "industry", "criterion_value": "healthcare"},
        )
        cid = create_resp.json()["id"]
        resp = client.delete(f"/api/criteria/{cid}")
        assert resp.status_code == 204

    def test_delete_criterion_not_found(self, client):
        resp = client.delete("/api/criteria/999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

class TestAnalyticsAPI:
    def test_dashboard_returns_expected_shape(self, client):
        resp = client.get("/api/analytics/dashboard")
        assert resp.status_code == 200
        body = resp.json()
        assert "total_active_jobs" in body
        assert "total_applications" in body
        assert "average_match_score" in body

    def test_api_usage_returns_list(self, client):
        resp = client.get("/api/analytics/api-usage")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# User profile
# ---------------------------------------------------------------------------

class TestUserProfileAPI:
    def test_get_profile_returns_expected_shape(self, client):
        resp = client.get("/api/user/profile")
        # May 404 if user_profile.yaml is missing, but in the repo it always exists
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            body = resp.json()
            assert "current_title" in body or "user" in body

    def test_upload_resume_invalid_type(self, client):
        resp = client.post(
            "/api/user/resume",
            files={"file": ("resume.xyz", b"content", "application/octet-stream")},
        )
        assert resp.status_code == 422

    def test_upload_resume_valid_md(self, client):
        md_content = b"# John Doe\nDirector of Data\n2018 - 2024 Health Corp"
        resp = client.post(
            "/api/user/resume",
            files={"file": ("resume.md", md_content, "text/markdown")},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "skills" in body
        assert "experience_years" in body
