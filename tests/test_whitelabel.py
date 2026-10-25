"""White-label branding feature."""

from httpx import AsyncClient

from tests.conftest import register


async def test_whitelabel_requires_auth(client: AsyncClient):
    assert (await client.get("/api/whitelabel")).status_code == 401


async def test_whitelabel_defaults_then_update(client: AsyncClient):
    headers = await register(client, "wl-owner@example.com")

    got = await client.get("/api/whitelabel", headers=headers)
    assert got.status_code == 200
    assert got.json()["accent_color"] == "#3B82F6"  # created with defaults

    upd = await client.put(
        "/api/whitelabel",
        json={"platform_name": "My Panel", "accent_color": "#101828", "domain": "panel.example.com"},
        headers=headers,
    )
    assert upd.status_code == 200
    body = upd.json()
    assert body["platform_name"] == "My Panel"
    assert body["domain"] == "panel.example.com"
    assert body["dns_status"] == "pending"  # a new domain is unverified until checked


async def test_whitelabel_rejects_unknown_field_and_long_blurb(client: AsyncClient):
    headers = await register(client, "wl-valid@example.com")
    assert (await client.put("/api/whitelabel", json={"is_admin": True}, headers=headers)).status_code == 422
    assert (await client.put("/api/whitelabel", json={"description_md": "x" * 701}, headers=headers)).status_code == 422


async def test_whitelabel_rejects_javascript_website_url(client: AsyncClient):
    headers = await register(client, "wl-url@example.com")
    r = await client.put("/api/whitelabel", json={"website_url": "javascript:alert(1)"}, headers=headers)
    assert r.status_code == 422


async def test_public_branding_only_when_verified(client: AsyncClient):
    headers = await register(client, "wl-pub@example.com")
    await client.put("/api/whitelabel", json={"domain": "brand.example.com", "platform_name": "Brand"}, headers=headers)

    # Not verified yet → not public.
    assert (await client.get("/api/whitelabel/public/brand.example.com")).status_code == 404


async def test_check_dns_requires_a_domain(client: AsyncClient):
    headers = await register(client, "wl-dns@example.com")
    # No domain configured yet.
    assert (await client.post("/api/whitelabel/check-dns", headers=headers)).status_code == 422
