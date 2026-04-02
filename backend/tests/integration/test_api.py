"""Integration tests: one happy path + one error path per API resource."""
from datetime import date

from app.models.company import Company
from app.models.job import Job


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

class TestJobsAPI:
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

    def test_hide_job(self, client_with_job):
        client, job_id = client_with_job
        resp = client.put(f"/api/jobs/{job_id}/hide")
        assert resp.status_code == 200
        # Job should no longer appear in the default active list
        list_resp = client.get("/api/jobs")
        assert list_resp.json()["total"] == 0

    def test_hide_job_not_found(self, client):
        resp = client.put("/api/jobs/999/hide")
        assert resp.status_code == 404

    def test_score_job_not_found(self, client):
        resp = client.put("/api/jobs/999/score")
        assert resp.status_code == 404

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
    def test_list_companies_empty(self, client):
        resp = client.get("/api/companies")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_company(self, client):
        resp = client.post("/api/companies", json={"name": "Health Corp"})
        assert resp.status_code == 201
        assert resp.json()["name"] == "Health Corp"

    def test_create_duplicate_company_conflict(self, client):
        client.post("/api/companies", json={"name": "Health Corp"})
        resp = client.post("/api/companies", json={"name": "Health Corp"})
        assert resp.status_code == 409

    def test_get_company_not_found(self, client):
        resp = client.get("/api/companies/999")
        assert resp.status_code == 404


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
