from httpx import AsyncClient

from app.db.models.enums import UserRole


async def test_health(client: AsyncClient):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_login_success_and_me(client: AsyncClient, make_user):
    await make_user("mech@test.io", role=UserRole.mechanic)
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "mech@test.io", "password": "Password123!"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "mech@test.io"

    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["role"] == "mechanic"


async def test_login_wrong_password(client: AsyncClient, make_user):
    await make_user("a@test.io")
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "a@test.io", "password": "wrong"}
    )
    assert resp.status_code == 401


async def test_refresh_rotation(client: AsyncClient, make_user):
    await make_user("r@test.io")
    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": "r@test.io", "password": "Password123!"}
    )
    refresh = login_resp.json()["refresh_token"]

    r1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r1.status_code == 200
    assert "access_token" in r1.json()

    # Old token was rotated/revoked -> reuse must fail.
    r2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r2.status_code == 401


async def test_logout_revokes(client: AsyncClient, make_user):
    await make_user("l@test.io")
    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": "l@test.io", "password": "Password123!"}
    )
    refresh = login_resp.json()["refresh_token"]
    await client.post("/api/v1/auth/logout", json={"refresh_token": refresh})
    after = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert after.status_code == 401


async def test_me_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
