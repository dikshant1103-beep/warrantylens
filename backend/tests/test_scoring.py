"""Risk + completeness engine tests (need Postgres; run in CI)."""
from httpx import AsyncClient

from app.db.models.claim import Claim
from app.db.models.component import FraudIndicatorDef
from app.db.models.enums import ClaimStatus, OcrFieldType, UserRole
from app.services import completeness_service, risk_service
from tests.conftest import TestSession, login


async def _make_claim(tenant_id, user_id, vin=None, status=ClaimStatus.processing):
    async with TestSession() as s:
        c = Claim(
            tenant_id=tenant_id, claim_number=f"CLM-T-{user_id.hex[:6]}",
            created_by_user_id=user_id, status=status, vin=vin,
        )
        s.add(c)
        await s.commit()
        await s.refresh(c)
        return c


async def test_completeness_with_no_template(make_user):
    user = await make_user("m@test.io")
    claim = await _make_claim(user.tenant_id, user.id)
    async with TestSession() as s:
        claim = await s.get(Claim, claim.id)
        check = await completeness_service.compute(s, claim)
        await s.commit()
        # only baseline check (media_present) -> claim has no media -> score 0
        assert check.score == 0.0
        assert "At least one piece of evidence" in check.missing


async def test_risk_zero_when_no_signals(make_user):
    user = await make_user("m@test.io")
    claim = await _make_claim(user.tenant_id, user.id)
    async with TestSession() as s:
        claim = await s.get(Claim, claim.id)
        comp = await completeness_service.compute(s, claim)
        risk = await risk_service.compute(s, claim, comp)
        await s.commit()
        # No detections; incomplete inspection (score 0) is the only contributor.
        assert risk.score >= 0
        assert any(f["indicator"] == "incomplete_inspection" for f in risk.factors)
        # advisory framing must be present; never a bare fraud claim
        assert "reviewer makes the final decision" in (risk.rationale or "")


async def test_vin_mismatch_factor(make_user):
    user = await make_user("m@test.io")
    claim = await _make_claim(user.tenant_id, user.id, vin="1HGBH41JXMN109186")
    async with TestSession() as s:
        from app.db.models.ai import OcrResult
        s.add(OcrResult(
            tenant_id=user.tenant_id, claim_id=claim.id, field_type=OcrFieldType.vin,
            raw_text="1HGBH41JXMN109999", normalized_value="1HGBH41JXMN109999", confidence=1.0,
        ))
        s.add(FraudIndicatorDef(
            tenant_id=user.tenant_id, code="vin_mismatch", label="VIN mismatch",
            default_weight=3.0, severity="high",
        ))
        await s.commit()
        claim = await s.get(Claim, claim.id)
        comp = await completeness_service.compute(s, claim)
        risk = await risk_service.compute(s, claim, comp)
        await s.commit()
        assert any(f["indicator"] == "vin_mismatch" for f in risk.factors)


async def test_review_requires_reviewer_role(client: AsyncClient, make_user):
    await make_user("mech@test.io", role=UserRole.mechanic)
    token = await login(client, "mech@test.io")
    # mechanic cannot review (404 claim is fine too, but role gate is 403 before lookup)
    resp = await client.post(
        "/api/v1/claims/00000000-0000-0000-0000-000000000000/review",
        headers={"Authorization": f"Bearer {token}"},
        json={"decision": "approved"},
    )
    assert resp.status_code == 403
