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


def test_job_salary_range_is_optional(client):
    data = login(client, "liza.torres@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
    created = client.post(
        "/api/alumni/jobs",
        headers=headers,
        json={
            "job_title": "Salary Optional Analyst",
            "company": "North Luzon Systems Corp.",
            "is_current": True,
        },
    )
    assert created.status_code == 200, created.text
    added = next(row for row in created.json()["jobs"] if row["job_title"] == "Salary Optional Analyst")
    assert added["salary_range"] == ""

    band = "₱13,800 to ₱27,599"
    updated = client.put(
        f"/api/alumni/jobs/{added['id']}",
        headers=headers,
        json={
            "job_title": "Salary Optional Analyst",
            "company": "North Luzon Systems Corp.",
            "is_current": True,
            "salary_range": band,
        },
    )
    assert updated.status_code == 200, updated.text
    edited = next(row for row in updated.json()["jobs"] if row["id"] == added["id"])
    assert edited["salary_range"] == band

    cleared = client.put(
        f"/api/alumni/jobs/{added['id']}",
        headers=headers,
        json={
            "job_title": "Salary Optional Analyst",
            "company": "North Luzon Systems Corp.",
            "is_current": True,
            "salary_range": "",
        },
    )
    assert cleared.status_code == 200, cleared.text
    blank = next(row for row in cleared.json()["jobs"] if row["id"] == added["id"])
    assert blank["salary_range"] == ""

    invalid = client.post(
        "/api/alumni/jobs",
        headers=headers,
        json={
            "job_title": "Salary Optional Analyst",
            "company": "North Luzon Systems Corp.",
            "is_current": True,
            "salary_range": "One million",
        },
    )
    assert invalid.status_code == 422

    deleted = client.delete(f"/api/alumni/jobs/{added['id']}", headers=headers)
    assert deleted.status_code == 200
    assert added["id"] not in [row["id"] for row in deleted.json()["jobs"]]


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


def _add_job(client, headers, **extra):
    payload = {"job_title": "Role", "company": "Co", "is_current": False}
    payload.update(extra)
    response = client.post("/api/alumni/jobs", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    return response.json()["jobs"]


def test_first_job_follows_the_earliest_unique_start_date(client):
    headers = auth_header(login(client, "liza.torres@gmail.com", "Alumni@2026")["access_token"])
    created = []
    try:
        baseline = client.get("/api/alumni/jobs", headers=headers).json()["jobs"]
        assert baseline and all(row["start_date"] for row in baseline)
        earliest = min(row["start_date"] for row in baseline)
        marked = [row for row in baseline if row["is_first_job"]]
        assert len(marked) == 1
        assert marked[0]["start_date"] == earliest
        assert marked[0]["job_title"] != next(row["job_title"] for row in baseline if row["is_current"])

        early = _add_job(
            client, headers,
            job_title="Campus Aide", company="AUF",
            start_date="2010-01-15", end_date="2011-01-15",
        )
        aide = next(row for row in early if row["job_title"] == "Campus Aide")
        created.append(aide["id"])
        assert aide["is_first_job"] is True
        assert aide["is_current"] is False
        assert sum(row["is_first_job"] for row in early) == 1

        tied = _add_job(
            client, headers,
            job_title="Campus Aide II", company="AUF",
            start_date="2010-01-15", end_date="2011-06-01",
        )
        second = next(row for row in tied if row["job_title"] == "Campus Aide II")
        created.append(second["id"])
        assert all(row["is_first_job"] is False for row in tied)

        removed = client.delete(f"/api/alumni/jobs/{second['id']}", headers=headers)
        assert removed.status_code == 200
        created.remove(second["id"])
        after_tie = removed.json()["jobs"]
        assert next(row for row in after_tie if row["id"] == aide["id"])["is_first_job"] is True

        moved = client.put(
            f"/api/alumni/jobs/{aide['id']}",
            headers=headers,
            json={"job_title": "Campus Aide", "company": "AUF", "start_date": "2030-01-01", "is_current": False},
        )
        assert moved.status_code == 200, moved.text
        shifted = moved.json()["jobs"]
        assert next(row for row in shifted if row["id"] == aide["id"])["is_first_job"] is False
        assert sum(row["is_first_job"] for row in shifted) == 1
        assert next(row for row in shifted if row["is_first_job"])["start_date"] == earliest

        undated = _add_job(client, headers, job_title="Undated Role", company="AUF")
        blank = next(row for row in undated if row["job_title"] == "Undated Role")
        created.append(blank["id"])
        assert blank["start_date"] is None
        assert all(row["is_first_job"] is False for row in undated)
    finally:
        for job_id in created:
            client.delete(f"/api/alumni/jobs/{job_id}", headers=headers)


def test_participation_interests_belong_to_the_signed_in_alumnus(client):
    maria = auth_header(login(client, "maria.reyes@gmail.com", "Alumni@2026")["access_token"])
    liza = auth_header(login(client, "liza.torres@gmail.com", "Alumni@2026")["access_token"])
    empty = {"speaker": False, "mentor": False, "sponsor": False}
    try:
        saved = client.put("/api/alumni/participation", headers=maria, json={"roles": ["speaker", "sponsor", "speaker"]})
        assert saved.status_code == 200, saved.text
        assert saved.json()["profile"]["participation"] == {"speaker": True, "mentor": False, "sponsor": True}
        assert client.get("/api/alumni/dashboard", headers=maria).json()["profile"]["participation"]["speaker"] is True

        other = client.put("/api/alumni/participation", headers=liza, json={"roles": ["mentor"]})
        assert other.status_code == 200, other.text
        assert other.json()["profile"]["participation"] == {"speaker": False, "mentor": True, "sponsor": False}
        assert client.get("/api/alumni/dashboard", headers=maria).json()["profile"]["participation"] == {
            "speaker": True,
            "mentor": False,
            "sponsor": True,
        }

        cleared = client.put("/api/alumni/participation", headers=maria, json={"roles": []})
        assert cleared.status_code == 200
        assert cleared.json()["profile"]["participation"] == empty

        rejected = client.put("/api/alumni/participation", headers=liza, json={"roles": ["dean"]})
        assert rejected.status_code == 400
        assert rejected.json()["detail"] == "Choose Speaker, Mentor, or Sponsor."
        assert client.get("/api/alumni/dashboard", headers=liza).json()["profile"]["participation"]["mentor"] is True

        assert client.put("/api/alumni/participation", json={"roles": ["mentor"]}).status_code in (401, 403)
        pending = auth_header(login(client, "juan.delacruz@gmail.com", "Alumni@2026")["access_token"])
        assert client.put("/api/alumni/participation", headers=pending, json={"roles": ["mentor"]}).status_code == 403
    finally:
        client.put("/api/alumni/participation", headers=maria, json={"roles": []})
        client.put("/api/alumni/participation", headers=liza, json={"roles": []})
