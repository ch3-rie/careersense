from tests.conftest import auth_header, login


def _admin(client):
    data = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    return auth_header(data["access_token"])


def _gts_payload(**overrides):
    payload = {
        "first_name": "Maria",
        "last_name": "Reyes",
        "degree": "Bachelor of Science in Information Technology",
        "year_graduated": "2022",
        "ever_employed": "Yes",
        "is_currently_employed": "Yes",
        "present_job_is_first": "No",
        "pres_occ": "Software Engineer",
        "first_occ": "Junior Software Developer",
        "first_emp": "Pampanga Digital Labs",
        "first_related": "Yes",
        "first_stat": "Regular/Permanent",
        "skills": ["Python", "SQL"],
    }
    payload.update(overrides)
    return payload


def _section(schema, key):
    return next(section for section in schema["sections"] if section.get("key") == key)


def _add_extra(schema, *, qid, label, section_key="feedback", **fields):
    question = {
        "id": qid,
        "extra_key": qid,
        "field_key": "",
        "label": label,
        "description": fields.get("description", ""),
        "type": fields.get("type", "short_answer"),
        "required": fields.get("required", False),
        "options": fields.get("options", []),
        "placeholder": "",
        "default_value": "",
        "system": False,
        "storage": "extra",
        "visibility": fields.get("visibility"),
        "validation": fields.get("validation") or {},
    }
    _section(schema, section_key)["subsections"][-1]["questions"].append(question)
    return question


def test_survey_draft_publish_and_options(client):
    headers = _admin(client)
    survey = client.get("/api/admin/survey", headers=headers)
    assert survey.status_code == 200, survey.text
    body = survey.json()
    assert body["draft"]["sections"]
    assert body["published_version"] >= 1
    labels = [q["label"] for section in body["draft"]["sections"] for sub in section["subsections"] for q in sub["questions"]]
    assert "Given name" in labels
    assert "Are you currently employed?" in labels

    draft = body["draft"]
    draft["sections"][0]["subsections"][0]["questions"][0]["label"] = "Given name (legal)"
    saved = client.put("/api/admin/survey/draft", headers=headers, json={"schema": draft, "auto": True})
    assert saved.status_code == 200, saved.text

    options = client.get("/api/auth/options")
    assert options.status_code == 200
    assert options.json()["survey"]["sections"][0]["subsections"][0]["questions"][0]["label"] == "Given name"

    published = client.post("/api/admin/survey/publish", headers=headers, json={"confirm_impact": True})
    assert published.status_code == 200, published.text
    live = client.get("/api/auth/options").json()["survey"]
    assert live["sections"][0]["subsections"][0]["questions"][0]["label"] == "Given name (legal)"
    assert client.get("/api/auth/options").json()["survey_version"] == published.json()["published_version"]


def test_survey_add_stays_draft_until_publish(client):
    headers = _admin(client)
    draft = client.get("/api/admin/survey", headers=headers).json()["draft"]
    _add_extra(draft, qid="q_campus_hours", label="Preferred campus visit hours", type="short_answer")
    saved = client.put("/api/admin/survey/draft", headers=headers, json={"schema": draft, "auto": False})
    assert saved.status_code == 200, saved.text
    assert saved.json()["dirty"] is True
    live_labels = [
        question["label"]
        for section in client.get("/api/auth/options").json()["survey"]["sections"]
        for sub in section["subsections"]
        for question in sub["questions"]
    ]
    assert "Preferred campus visit hours" not in live_labels

    published = client.post("/api/admin/survey/publish", headers=headers, json={"confirm_impact": True})
    assert published.status_code == 200, published.text
    live_labels = [
        question["label"]
        for section in client.get("/api/auth/options").json()["survey"]["sections"]
        for sub in section["subsections"]
        for question in sub["questions"]
    ]
    assert "Preferred campus visit hours" in live_labels


def test_survey_reorder_persists_after_publish(client):
    headers = _admin(client)
    draft = client.get("/api/admin/survey", headers=headers).json()["draft"]
    _add_extra(draft, qid="q_order_a", label="Order A")
    _add_extra(draft, qid="q_order_b", label="Order B")
    questions = _section(draft, "feedback")["subsections"][-1]["questions"]
    questions[:] = [item for item in questions if item["id"] not in {"q_order_a", "q_order_b"}] + [
        next(item for item in questions if item["id"] == "q_order_b"),
        next(item for item in questions if item["id"] == "q_order_a"),
    ]
    assert client.put("/api/admin/survey/draft", headers=headers, json={"schema": draft, "auto": False}).status_code == 200
    assert client.post("/api/admin/survey/publish", headers=headers, json={"confirm_impact": True}).status_code == 200
    live = [
        question["id"]
        for section in client.get("/api/auth/options").json()["survey"]["sections"]
        if section.get("key") == "feedback"
        for sub in section["subsections"]
        for question in sub["questions"]
    ]
    assert live.index("q_order_b") < live.index("q_order_a")


def test_survey_required_extra_enforced_on_gts(client):
    headers = _admin(client)
    draft = client.get("/api/admin/survey", headers=headers).json()["draft"]
    _add_extra(draft, qid="q_required_note", label="Required alumni note", required=True)
    assert client.put("/api/admin/survey/draft", headers=headers, json={"schema": draft, "auto": False}).status_code == 200
    assert client.post("/api/admin/survey/publish", headers=headers, json={"confirm_impact": True}).status_code == 200

    maria = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    alumni = auth_header(maria["access_token"])
    missing = client.post("/api/alumni/gts", headers=alumni, json=_gts_payload())
    assert missing.status_code == 400, missing.text
    assert "Required alumni note" in missing.json()["detail"]

    ok = client.post("/api/alumni/gts", headers=alumni, json=_gts_payload(extra_answers={"q_required_note": "Noted"}))
    assert ok.status_code == 200, ok.text
    assert ok.json()["submission_id"]

    draft = client.get("/api/admin/survey", headers=headers).json()["draft"]
    for section in draft["sections"]:
        for sub in section["subsections"]:
            sub["questions"] = [item for item in sub["questions"] if item["id"] != "q_required_note"]
    assert client.put("/api/admin/survey/draft", headers=headers, json={"schema": draft, "auto": False}).status_code == 200
    assert client.post("/api/admin/survey/publish", headers=headers, json={"confirm_impact": True}).status_code == 200


def test_survey_delete_keeps_historical_extra_answers(client):
    headers = _admin(client)
    draft = client.get("/api/admin/survey", headers=headers).json()["draft"]
    _add_extra(draft, qid="q_keep_history", label="Favorite campus event")
    assert client.put("/api/admin/survey/draft", headers=headers, json={"schema": draft, "auto": False}).status_code == 200
    assert client.post("/api/admin/survey/publish", headers=headers, json={"confirm_impact": True}).status_code == 200

    maria = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    alumni = auth_header(maria["access_token"])
    submitted = client.post(
        "/api/alumni/gts",
        headers=alumni,
        json=_gts_payload(extra_answers={"q_keep_history": "Foundation Day"}),
    )
    assert submitted.status_code == 200, submitted.text
    submission_id = submitted.json()["submission_id"]

    draft = client.get("/api/admin/survey", headers=headers).json()["draft"]
    for section in draft["sections"]:
        for sub in section["subsections"]:
            sub["questions"] = [item for item in sub["questions"] if item["id"] != "q_keep_history"]
    assert client.put("/api/admin/survey/draft", headers=headers, json={"schema": draft, "auto": False}).status_code == 200
    assert client.post("/api/admin/survey/publish", headers=headers, json={"confirm_impact": True}).status_code == 200

    live_ids = [
        question["id"]
        for section in client.get("/api/auth/options").json()["survey"]["sections"]
        for sub in section["subsections"]
        for question in sub["questions"]
    ]
    assert "q_keep_history" not in live_ids

    record = client.get(f"/api/admin/tracer/{submission_id}", headers=headers)
    assert record.status_code == 200, record.text
    assert record.json()["extra_answers"]["q_keep_history"] == "Foundation Day"
    assert record.json()["survey_version"]
    profile = client.get("/api/alumni/profile", headers=alumni)
    assert profile.json()["extra_answers"]["q_keep_history"] == "Foundation Day"


def test_survey_publish_unchanged_does_not_bump_version(client):
    headers = _admin(client)
    current = client.get("/api/admin/survey", headers=headers).json()
    version = current["published_version"]
    published = client.post("/api/admin/survey/publish", headers=headers, json={"confirm_impact": True})
    assert published.status_code == 200, published.text
    assert published.json()["published_version"] == version


def test_survey_settings_update_live_gts_without_publish(client):
    headers = _admin(client)
    saved = client.put(
        "/api/admin/survey/settings",
        headers=headers,
        json={"accepting_responses": False, "allow_alumni_edit": False},
    )
    assert saved.status_code == 200, saved.text
    options = client.get("/api/auth/options").json()
    assert options["survey_open"] is False
    assert options["allow_alumni_edit"] is False
    assert options["survey"]["accepting_responses"] is False

    restored = client.put(
        "/api/admin/survey/settings",
        headers=headers,
        json={"accepting_responses": True, "allow_alumni_edit": True},
    )
    assert restored.status_code == 200, restored.text
    options = client.get("/api/auth/options").json()
    assert options["survey_open"] is True
    assert options["allow_alumni_edit"] is True


def test_survey_delete_parent_scrubs_visibility_and_saves(client):
    headers = _admin(client)
    draft = client.get("/api/admin/survey", headers=headers).json()["draft"]
    _add_extra(draft, qid="q_parent_vis", label="Parent visibility question", type="yes_no")
    _add_extra(
        draft,
        qid="q_child_vis",
        label="Child visibility question",
        visibility={"logic": "and", "rules": [{"field_id": "q_parent_vis", "op": "eq", "value": "Yes"}]},
    )
    assert client.put("/api/admin/survey/draft", headers=headers, json={"schema": draft, "auto": True}).status_code == 200
    draft = client.get("/api/admin/survey", headers=headers).json()["draft"]
    for section in draft["sections"]:
        for sub in section["subsections"]:
            sub["questions"] = [item for item in sub["questions"] if item["id"] != "q_parent_vis"]
    saved = client.put("/api/admin/survey/draft", headers=headers, json={"schema": draft, "auto": True})
    assert saved.status_code == 200, saved.text
    child = next(
        question
        for section in saved.json()["draft"]["sections"]
        for sub in section["subsections"]
        for question in sub["questions"]
        if question["id"] == "q_child_vis"
    )
    assert not child.get("visibility")


def test_survey_choice_validation_blocks_explicit_save(client):
    headers = _admin(client)
    draft = client.get("/api/admin/survey", headers=headers).json()["draft"]
    _add_extra(draft, qid="q_bad_choices", label="Broken multiple choice", type="multiple_choice", options=["Only one"])
    blocked = client.put("/api/admin/survey/draft", headers=headers, json={"schema": draft, "auto": False})
    assert blocked.status_code == 400, blocked.text
    autosaved = client.put("/api/admin/survey/draft", headers=headers, json={"schema": draft, "auto": True})
    assert autosaved.status_code == 200, autosaved.text
    cleaned = client.get("/api/admin/survey", headers=headers).json()["draft"]
    for section in cleaned["sections"]:
        for sub in section["subsections"]:
            sub["questions"] = [item for item in sub["questions"] if item["id"] != "q_bad_choices"]
    assert client.put("/api/admin/survey/draft", headers=headers, json={"schema": cleaned, "auto": True}).status_code == 200


def test_alumni_cannot_manage_survey_or_perks(client):
    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
    assert client.get("/api/admin/survey", headers=headers).status_code == 403
    assert client.get("/api/admin/perks", headers=headers).status_code == 403
    assert client.get("/api/admin/users", headers=headers).status_code == 403


def test_alumni_cannot_manage_survey_or_perks(client):
    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
    assert client.get("/api/admin/survey", headers=headers).status_code == 403
    assert client.get("/api/admin/perks", headers=headers).status_code == 403
    assert client.get("/api/admin/users", headers=headers).status_code == 403


def test_admin_perk_crud_updates_alumni_list(client):
    admin = _admin(client)
    created = client.post(
        "/api/admin/perks",
        headers=admin,
        json={
            "name": "Campus bookstore voucher",
            "partner": "AUF Bookstore",
            "category": "Campus",
            "description": "Alumni bookstore discount.",
            "discount": "10% off",
            "how_to_claim": "Show your AAC at checkout.",
            "eligibility": "Active alumni",
            "active": True,
        },
    )
    assert created.status_code == 200, created.text
    perk_id = created.json()["item"]["id"]

    maria = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    perks = client.get("/api/alumni/perks", headers=auth_header(maria["access_token"])).json()["perks"]
    assert any(row["name"] == "Campus bookstore voucher" for row in perks)

    client.post(f"/api/admin/perks/{perk_id}/toggle", headers=admin)
    perks = client.get("/api/alumni/perks", headers=auth_header(maria["access_token"])).json()["perks"]
    assert all(row["name"] != "Campus bookstore voucher" for row in perks)


def test_admin_user_create_and_guards(client):
    headers = _admin(client)
    listing = client.get("/api/admin/users", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["active"] >= 1

    blocked = client.post(
        "/api/admin/users",
        headers=headers,
        json={"first_name": "Pat", "last_name": "Cruz", "email": "pat.admin@auf.edu.ph", "confirm": False},
    )
    assert blocked.status_code == 400

    created = client.post(
        "/api/admin/users",
        headers=headers,
        json={
            "first_name": "Pat",
            "last_name": "Cruz",
            "email": "pat.admin@auf.edu.ph",
            "role": "Admin",
            "status": "Active",
            "confirm": True,
        },
    )
    assert created.status_code == 200, created.text
    temp = created.json()["temporary_password"]
    assert temp
    user_id = created.json()["item"]["id"]
    assert "password" not in created.json()["item"]

    duplicate = client.post(
        "/api/admin/users",
        headers=headers,
        json={
            "first_name": "Pat",
            "last_name": "Cruz",
            "email": "pat.admin@auf.edu.ph",
            "confirm": True,
        },
    )
    assert duplicate.status_code == 400

    self_id = login(client, "admin@auf.edu.ph", "Admin@AUF2026")["user"]["id"]
    self_block = client.post(f"/api/admin/users/{self_id}/deactivate", headers=headers)
    assert self_block.status_code == 400

    signed = login(client, "pat.admin@auf.edu.ph", temp)
    assert signed["user"]["must_change_password"] is True
    assert signed["user"]["role"] == "Admin"
