"""User settings persist across requests: messenger, external services, stop words, password."""

from httpx import AsyncClient, codes

from tests.conftest import PASSWORD


async def test_messenger_settings_persist(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/users/settings/messenger",
        json={"telegram_webhook_url": "https://t.me/hook"},
        headers=auth_headers,
    )
    assert resp.status_code == codes.OK, resp.text

    got = await client.get("/api/users/settings/messenger", headers=auth_headers)
    assert got.json()["telegram_webhook_url"] == "https://t.me/hook"


async def test_external_services_persist(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/users/settings/external-services",
        json={"xml_river": {"user": "u1", "key": "k1"}},
        headers=auth_headers,
    )
    assert resp.status_code == codes.OK, resp.text

    got = await client.get("/api/users/settings/external-services", headers=auth_headers)
    assert got.json()["xml_river"] == {"user": "u1", "key": "k1"}


async def test_stop_words_replace_add_remove_persist(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/users/settings/stop-words", json={"stop_words": ["Казино", "ставки"]}, headers=auth_headers
    )
    assert resp.status_code == codes.OK, resp.text

    resp = await client.post("/api/users/settings/stop-words/add", json={"word": "Кредит"}, headers=auth_headers)
    assert resp.status_code == codes.OK, resp.text

    resp = await client.delete("/api/users/settings/stop-words/ставки", headers=auth_headers)
    assert resp.status_code == codes.OK, resp.text

    got = await client.get("/api/users/settings/stop-words", headers=auth_headers)
    assert sorted(got.json()["stop_words"]) == ["казино", "кредит"]


async def test_stop_words_do_not_clobber_messenger_settings(client: AsyncClient, auth_headers):
    await client.post(
        "/api/users/settings/messenger", json={"telegram_webhook_url": "https://t.me/keep"}, headers=auth_headers
    )
    await client.post("/api/users/settings/stop-words/add", json={"word": "спам"}, headers=auth_headers)

    got = await client.get("/api/users/settings/messenger", headers=auth_headers)
    assert got.json()["telegram_webhook_url"] == "https://t.me/keep"


async def test_change_password_then_login_with_new_one(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/users/password",
        json={"current_password": PASSWORD, "new_password": "brand-new-pass-1"},
        headers=auth_headers,
    )
    assert resp.status_code == codes.OK, resp.text

    login = await client.post("/api/auth/login", json={"email": "owner@example.com", "password": "brand-new-pass-1"})
    assert login.status_code == codes.OK, login.text


async def test_change_password_rejects_wrong_current(client: AsyncClient, auth_headers):
    resp = await client.post(
        "/api/users/password",
        json={"current_password": "not-my-password", "new_password": "brand-new-pass-1"},
        headers=auth_headers,
    )
    assert resp.status_code == codes.BAD_REQUEST


async def test_profile_balance_sums_own_projects(client, auth_headers):
    for domain, amount in (("bal-a.example.com", 150), ("bal-b.example.com", 50)):
        pid = (await client.post("/api/projects/", json={"name": domain, "domain": domain}, headers=auth_headers)).json()["id"]
        resp = await client.post(f"/api/projects/{pid}/balance/add", json={"amount": amount}, headers=auth_headers)
        assert resp.status_code == 200, resp.text
    profile = (await client.get("/api/users/profile", headers=auth_headers)).json()
    assert profile["balance"] == 200
    assert "plan" not in profile  # there is no billing plan behind it
