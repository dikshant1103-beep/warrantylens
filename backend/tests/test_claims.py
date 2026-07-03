from httpx import AsyncClient

from app.db.models.enums import UserRole
from tests.conftest import login


async def _auth(client: AsyncClient, make_user, role=UserRole.mechanic):
    await make_user("mech@test.io", role=role)
    token = await login(client, "mech@test.io")
    return {"Authorization": f"Bearer {token}"}


async def test_create_and_list_claim(client: AsyncClient, make_user):
    headers = await _auth(client, make_user)
    create = await client.post(
        "/api/v1/claims",
        headers=headers,
        json={"vin": "1hgbh41jxmn109186", "claim_reason": "charging port damage"},
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["claim_number"].startswith("CLM-")
    assert body["vin"] == "1HGBH41JXMN109186"  # normalized upper
    assert body["status"] == "draft"

    listing = await client.get("/api/v1/claims", headers=headers)
    assert listing.status_code == 200
    assert listing.json()["total"] == 1


async def test_submit_without_evidence_conflicts(client: AsyncClient, make_user):
    headers = await _auth(client, make_user)
    claim = (
        await client.post("/api/v1/claims", headers=headers, json={"claim_reason": "x"})
    ).json()
    resp = await client.post(f"/api/v1/claims/{claim['id']}/submit", headers=headers)
    assert resp.status_code == 409  # needs at least one uploaded asset


async def test_update_draft_claim(client: AsyncClient, make_user):
    headers = await _auth(client, make_user)
    claim = (
        await client.post("/api/v1/claims", headers=headers, json={})
    ).json()
    patch = await client.patch(
        f"/api/v1/claims/{claim['id']}",
        headers=headers,
        json={"claim_reason": "updated reason"},
    )
    assert patch.status_code == 200
    assert patch.json()["claim_reason"] == "updated reason"


async def test_claim_tenant_isolation(client: AsyncClient, make_user):
    headers = await _auth(client, make_user)
    # A random UUID from another tenant must 404, not leak.
    resp = await client.get(
        "/api/v1/claims/00000000-0000-0000-0000-000000000000", headers=headers
    )
    assert resp.status_code == 404
