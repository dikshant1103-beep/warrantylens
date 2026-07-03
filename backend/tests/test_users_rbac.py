from httpx import AsyncClient

from app.db.models.enums import UserRole
from tests.conftest import login


async def test_mechanic_cannot_list_users(client: AsyncClient, make_user):
    await make_user("mech@test.io", role=UserRole.mechanic)
    token = await login(client, "mech@test.io")
    resp = await client.get(
        "/api/v1/users", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403


async def test_admin_can_create_and_list_users(client: AsyncClient, make_user):
    await make_user("admin@test.io", role=UserRole.admin)
    token = await login(client, "admin@test.io")
    headers = {"Authorization": f"Bearer {token}"}

    create = await client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "reviewer@test.io",
            "full_name": "Rev One",
            "role": "reviewer",
            "password": "Password123!",
        },
    )
    assert create.status_code == 201, create.text
    assert create.json()["role"] == "reviewer"

    listing = await client.get("/api/v1/users", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 2  # admin + reviewer


async def test_admin_cannot_delete_self(client: AsyncClient, make_user):
    admin = await make_user("admin@test.io", role=UserRole.admin)
    token = await login(client, "admin@test.io")
    resp = await client.delete(
        f"/api/v1/users/{admin.id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 409


async def test_duplicate_email_conflict(client: AsyncClient, make_user):
    await make_user("admin@test.io", role=UserRole.admin)
    token = await login(client, "admin@test.io")
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "email": "dup@test.io",
        "full_name": "Dup",
        "role": "mechanic",
        "password": "Password123!",
    }
    first = await client.post("/api/v1/users", headers=headers, json=payload)
    assert first.status_code == 201
    second = await client.post("/api/v1/users", headers=headers, json=payload)
    assert second.status_code == 409
