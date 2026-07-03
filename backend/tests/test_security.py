from httpx import AsyncClient


async def test_security_headers_present(client: AsyncClient):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "no-referrer"
    assert resp.headers.get("X-Request-ID")  # request id echoed back


async def test_request_id_roundtrip(client: AsyncClient):
    resp = await client.get("/api/v1/health", headers={"X-Request-ID": "abc123"})
    assert resp.headers.get("X-Request-ID") == "abc123"


async def test_metrics_endpoint(client: AsyncClient):
    await client.get("/api/v1/health")  # generate at least one sample
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "wl_http_requests_total" in resp.text


async def test_upload_spec_rejects_bad_type(client: AsyncClient, make_user):
    from tests.conftest import login

    await make_user("m@test.io")
    token = await login(client, "m@test.io")
    headers = {"Authorization": f"Bearer {token}"}
    claim = (await client.post("/api/v1/claims", headers=headers, json={})).json()
    # disallowed content type -> 422 validation error
    resp = await client.post(
        f"/api/v1/claims/{claim['id']}/uploads",
        headers=headers,
        json={
            "files": [
                {"filename": "x.exe", "content_type": "application/x-msdownload", "kind": "image"}
            ]
        },
    )
    assert resp.status_code == 422
