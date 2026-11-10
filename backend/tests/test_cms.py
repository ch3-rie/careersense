from tests.conftest import auth_header, login


def _admin(client):
    data = login(client, "admin@auf.edu.ph", "Admin@AUF2026")
    return auth_header(data["access_token"])


def test_survey_manager_is_removed(client):
    headers = _admin(client)
    assert client.get("/api/admin/survey", headers=headers).status_code == 404
    assert client.put("/api/admin/survey/draft", headers=headers, json={"schema": {}, "auto": True}).status_code == 404
    assert client.post("/api/admin/survey/publish", headers=headers, json={"confirm_impact": True}).status_code == 404
    assert client.get("/api/admin/questions", headers=headers).status_code == 404


def test_alumni_cannot_manage_perks_or_users(client):
    data = login(client, "maria.reyes@gmail.com", "Alumni@2026")
    headers = auth_header(data["access_token"])
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
            "valid_until_further_notice": True,
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
            "employee_number": "012",
            "role": "Admin",
            "status": "Active",
            "confirm": True,
        },
    )
    assert created.status_code == 200, created.text
    temp = created.json()["temporary_password"]
    assert temp
    user_id = created.json()["item"]["id"]
    assert created.json()["item"]["employee_number"] == "012"
    assert created.json()["item"]["admin_privileges"] == "add_users"
    assert "password" not in created.json()["item"]

    duplicate = client.post(
        "/api/admin/users",
        headers=headers,
        json={
            "first_name": "Pat",
            "last_name": "Cruz",
            "email": "pat.admin@auf.edu.ph",
            "employee_number": "013",
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
    assert signed["user"]["employee_number"] == "012"
    assert signed["user"]["full_admin"] is False
    limited = auth_header(signed["access_token"])
    assert client.get("/api/admin/soc", headers=limited).status_code == 403
    assert client.get("/api/admin/perks", headers=limited).status_code == 403
    assert client.patch(f"/api/admin/users/{user_id}", headers=limited, json={"first_name": "Patricia"}).status_code == 403
    assert client.get("/api/admin/users", headers=headers).json()["items"][0]["privilege_label"]
