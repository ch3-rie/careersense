from tests.conftest import auth_header, login


def test_pending_alumni_blocked_from_jobs(client):
    data = login(client, "juan.delacruz@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
    assert client.get("/api/alumni/jobs", headers=headers).status_code == 403
    assert client.post(
        "/api/alumni/jobs",
        headers=headers,
        json={"job_title": "Analyst", "company": "AUF", "is_current": True},
    ).status_code == 403


def test_maria_dashboard_includes_seeded_jobs(client):
    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    response = client.get("/api/alumni/dashboard", headers=auth_header(data["access_token"]))
    assert response.status_code == 200
    jobs = response.json()["jobs"]
    assert len(jobs) >= 2
    titles = [row["job_title"] for row in jobs]
    assert "Junior Software Developer" in titles
    assert "Software Engineer" in titles
    current = next(row for row in jobs if row["job_title"] == "Software Engineer")
    assert current["company"] == "North Luzon Systems Corp."
    assert current["is_current"] is True
    assert current["end_date"] is None
    body = response.json()
    assert "Python" in body["skills"]
    assert body["profile"]["country_residence"] == "Philippines"
    assert body["profile"]["degree"].startswith("Bachelor")
    assert body["further_studies"] == []


def test_job_timeline_crud(client):
    data = login(client, "liza.torres@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])

    created = client.post(
        "/api/alumni/jobs",
        headers=headers,
        json={
            "job_title": "Tax Associate",
            "company": "Pampanga Tax Advisors",
            "start_date": "2019-06-01",
            "end_date": "2020-07-31",
            "is_current": False,
            "description": "Prepared individual and small-business tax filings.",
        },
    )
    assert created.status_code == 200, created.text
    jobs = created.json()["jobs"]
    added = next(row for row in jobs if row["job_title"] == "Tax Associate")
    assert added["company"] == "Pampanga Tax Advisors"
    assert added["start_date"] == "2019-06-01"
    assert added["end_date"] == "2020-07-31"
    assert added["description"] == "Prepared individual and small-business tax filings."

    updated = client.put(
        f"/api/alumni/jobs/{added['id']}",
        headers=headers,
        json={
            "job_title": "Senior Tax Associate",
            "company": "Pampanga Tax Advisors",
            "start_date": "2019-06-01",
            "end_date": None,
            "is_current": True,
        },
    )
    assert updated.status_code == 200
    edited = next(row for row in updated.json()["jobs"] if row["id"] == added["id"])
    assert edited["job_title"] == "Senior Tax Associate"
    assert edited["is_current"] is True
    assert edited["end_date"] is None

    deleted = client.delete(f"/api/alumni/jobs/{added['id']}", headers=headers)
    assert deleted.status_code == 200
    remaining_ids = [row["id"] for row in deleted.json()["jobs"]]
    assert added["id"] not in remaining_ids


def test_job_validation(client):
    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])

    empty = client.post(
        "/api/alumni/jobs",
        headers=headers,
        json={"job_title": "", "company": "AUF", "is_current": False},
    )
    assert empty.status_code == 422

    inverted = client.post(
        "/api/alumni/jobs",
        headers=headers,
        json={
            "job_title": "Intern",
            "company": "AUF",
            "start_date": "2024-06-01",
            "end_date": "2023-01-01",
            "is_current": False,
        },
    )
    assert inverted.status_code == 400
    assert "End date" in inverted.json()["detail"]

    missing = client.put("/api/alumni/jobs/999999", headers=headers, json={"job_title": "Ghost", "company": "Nowhere"})
    assert missing.status_code == 404


def test_cleared_timeline_does_not_reimport(client):
    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
    jobs = client.get("/api/alumni/jobs", headers=headers).json()["jobs"]
    snapshot = [
        {
            "job_title": row["job_title"],
            "company": row["company"],
            "start_date": row["start_date"],
            "end_date": row["end_date"],
            "is_current": row["is_current"],
            "industry": row.get("industry") or "",
            "location": row.get("location") or "",
        }
        for row in jobs
    ]
    assert jobs
    for row in jobs:
        client.delete(f"/api/alumni/jobs/{row['id']}", headers=headers)
    again = client.get("/api/alumni/jobs", headers=headers)
    assert again.status_code == 200
    assert again.json()["jobs"] == []
    dashboard = client.get("/api/alumni/dashboard", headers=headers)
    assert dashboard.json()["jobs"] == []
    for row in snapshot:
        restored = client.post("/api/alumni/jobs", headers=headers, json=row)
        assert restored.status_code == 200
