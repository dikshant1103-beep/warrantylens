import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import client_ip, get_current_user, get_db, require_role
from app.db.models.ai import Detection, OcrResult, Transcript, VlmAnalysis
from app.db.models.enums import ClaimStatus, UserRole
from app.db.models.processing_job import ProcessingJob
from app.db.models.scoring import CompletenessCheck, Report, RiskAssessment
from app.db.models.user import User
from app.schemas.ai import (
    DetectionRead,
    OcrResultRead,
    TranscriptRead,
    VlmAnalysisRead,
)
from app.schemas.claim import (
    ClaimAssign,
    ClaimCreate,
    ClaimList,
    ClaimRead,
    ClaimStatusResponse,
    ClaimUpdate,
    StageStatus,
)
from app.schemas.media import (
    EvidenceResponse,
    FrameRead,
    MediaAssetWithUrl,
    UploadComplete,
    UploadRequest,
    UploadResponse,
    UploadSlot,
)
from app.schemas.review import ReviewCreate, ReviewRead
from app.schemas.scoring import CompletenessRead, ReportRead, RiskRead
from app.services import (
    audit_service,
    claim_service,
    evidence_service,
    report_service,
    review_service,
)

router = APIRouter()


@router.post("", response_model=ClaimRead, status_code=status.HTTP_201_CREATED)
async def create_claim(
    body: ClaimCreate,
    request: Request,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClaimRead:
    claim = await claim_service.create_claim(db, current, body)
    await audit_service.record(
        db, action="claim.create", entity_type="claim", entity_id=claim.id,
        actor_user_id=current.id, tenant_id=current.tenant_id, ip=client_ip(request),
    )
    await db.commit()
    return ClaimRead.model_validate(claim)


@router.get("", response_model=ClaimList)
async def list_claims(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status_filter: ClaimStatus | None = Query(None, alias="status"),
    vin: str | None = None,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClaimList:
    items, total = await claim_service.list_claims(
        db, current.tenant_id, page=page, size=size, status=status_filter, vin=vin
    )
    return ClaimList(
        items=[ClaimRead.model_validate(c) for c in items],
        page=page, size=size, total=total,
    )


@router.get("/{claim_id}", response_model=ClaimRead)
async def get_claim(
    claim_id: uuid.UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClaimRead:
    claim = await claim_service.get_claim(db, current.tenant_id, claim_id)
    return ClaimRead.model_validate(claim)


@router.patch("/{claim_id}", response_model=ClaimRead)
async def update_claim(
    claim_id: uuid.UUID,
    body: ClaimUpdate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClaimRead:
    claim = await claim_service.get_claim(db, current.tenant_id, claim_id)
    claim = await claim_service.update_claim(db, claim, body)
    await db.commit()
    return ClaimRead.model_validate(claim)


@router.post("/{claim_id}/assign", response_model=ClaimRead)
async def assign_claim(
    claim_id: uuid.UUID,
    body: ClaimAssign,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClaimRead:
    claim = await claim_service.get_claim(db, current.tenant_id, claim_id)
    claim = await claim_service.assign_reviewer(db, claim, body.reviewer_id)
    await db.commit()
    return ClaimRead.model_validate(claim)


@router.post("/{claim_id}/submit", response_model=ClaimRead)
async def submit_claim(
    claim_id: uuid.UUID,
    request: Request,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClaimRead:
    claim = await claim_service.get_claim(db, current.tenant_id, claim_id)
    claim = await claim_service.submit_claim(db, claim)
    await audit_service.record(
        db, action="claim.submit", entity_type="claim", entity_id=claim.id,
        actor_user_id=current.id, tenant_id=current.tenant_id, ip=client_ip(request),
    )
    await db.commit()
    return ClaimRead.model_validate(claim)


# --- Evidence / uploads ------------------------------------------------------
@router.post("/{claim_id}/uploads", response_model=UploadResponse)
async def request_uploads(
    claim_id: uuid.UUID,
    body: UploadRequest,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    claim = await claim_service.get_claim(db, current.tenant_id, claim_id)
    slots = await evidence_service.create_upload_slots(
        db, claim, body.files, uploaded_by=current.id
    )
    await db.commit()
    return UploadResponse(
        uploads=[
            UploadSlot(asset_id=a.id, upload_url=url, s3_key=a.s3_key)
            for a, url in slots
        ]
    )


@router.post("/{claim_id}/uploads/{asset_id}/complete", response_model=MediaAssetWithUrl)
async def complete_upload(
    claim_id: uuid.UUID,
    asset_id: uuid.UUID,
    body: UploadComplete,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MediaAssetWithUrl:
    claim = await claim_service.get_claim(db, current.tenant_id, claim_id)
    asset = await evidence_service.get_asset(db, claim, asset_id)
    asset = await evidence_service.complete_upload(db, asset, sha256=body.sha256)
    await db.commit()
    out = MediaAssetWithUrl.model_validate(asset)
    out.url = evidence_service.with_url(asset.s3_key)
    return out


@router.get("/{claim_id}/evidence", response_model=EvidenceResponse)
async def get_evidence(
    claim_id: uuid.UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvidenceResponse:
    claim = await claim_service.get_claim(db, current.tenant_id, claim_id)
    assets, frames = await evidence_service.list_evidence(db, claim)

    media_out = []
    for a in assets:
        m = MediaAssetWithUrl.model_validate(a)
        m.url = evidence_service.with_url(a.s3_key)
        media_out.append(m)

    frame_out = []
    for f in frames:
        fr = FrameRead.model_validate(f)
        fr.url = evidence_service.with_url(f.s3_key)
        frame_out.append(fr)

    return EvidenceResponse(media=media_out, frames=frame_out)


@router.get("/{claim_id}/status", response_model=ClaimStatusResponse)
async def claim_status(
    claim_id: uuid.UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ClaimStatusResponse:
    claim = await claim_service.get_claim(db, current.tenant_id, claim_id)
    jobs = list(
        await db.scalars(
            select(ProcessingJob)
            .where(ProcessingJob.claim_id == claim.id)
            .order_by(ProcessingJob.created_at)
        )
    )
    return ClaimStatusResponse(
        claim_id=claim.id,
        status=claim.status,
        processing_error=claim.processing_error,
        stages=[
            StageStatus(stage=j.stage, status=j.status.value, error=j.error)
            for j in jobs
        ],
    )


# --- AI results (Sprint 3) ---------------------------------------------------
@router.get("/{claim_id}/transcript", response_model=list[TranscriptRead])
async def get_transcript(
    claim_id: uuid.UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    claim = await claim_service.get_claim(db, current.tenant_id, claim_id)
    rows = await db.scalars(select(Transcript).where(Transcript.claim_id == claim.id))
    return list(rows)


@router.get("/{claim_id}/detections", response_model=list[DetectionRead])
async def get_detections(
    claim_id: uuid.UUID,
    defects_only: bool = False,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    claim = await claim_service.get_claim(db, current.tenant_id, claim_id)
    stmt = select(Detection).where(Detection.claim_id == claim.id)
    if defects_only:
        stmt = stmt.where(Detection.defect_label.is_not(None))
    rows = await db.scalars(stmt.order_by(Detection.confidence.desc()))
    return list(rows)


@router.get("/{claim_id}/ocr", response_model=list[OcrResultRead])
async def get_ocr(
    claim_id: uuid.UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    claim = await claim_service.get_claim(db, current.tenant_id, claim_id)
    rows = await db.scalars(select(OcrResult).where(OcrResult.claim_id == claim.id))
    return list(rows)


@router.get("/{claim_id}/vlm", response_model=list[VlmAnalysisRead])
async def get_vlm(
    claim_id: uuid.UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    claim = await claim_service.get_claim(db, current.tenant_id, claim_id)
    rows = await db.scalars(select(VlmAnalysis).where(VlmAnalysis.claim_id == claim.id))
    return list(rows)


# --- Scoring + report (Sprint 4) ---------------------------------------------
@router.get("/{claim_id}/completeness", response_model=CompletenessRead | None)
async def get_completeness(
    claim_id: uuid.UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    claim = await claim_service.get_claim(db, current.tenant_id, claim_id)
    return await db.scalar(
        select(CompletenessCheck)
        .where(CompletenessCheck.claim_id == claim.id)
        .order_by(CompletenessCheck.created_at.desc())
    )


@router.get("/{claim_id}/risk", response_model=RiskRead | None)
async def get_risk(
    claim_id: uuid.UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    claim = await claim_service.get_claim(db, current.tenant_id, claim_id)
    return await db.scalar(
        select(RiskAssessment)
        .where(RiskAssessment.claim_id == claim.id)
        .order_by(RiskAssessment.created_at.desc())
    )


@router.get("/{claim_id}/report", response_model=ReportRead | None)
async def get_report(
    claim_id: uuid.UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    claim = await claim_service.get_claim(db, current.tenant_id, claim_id)
    report = await db.scalar(
        select(Report).where(Report.claim_id == claim.id).order_by(Report.version.desc())
    )
    if report is None:
        return None
    out = ReportRead.model_validate(report)
    if report.s3_key_pdf:
        out.pdf_url = evidence_service.with_url(report.s3_key_pdf)
    if report.s3_key_html:
        out.html_url = evidence_service.with_url(report.s3_key_html)
    return out


@router.post("/{claim_id}/report/regenerate", response_model=ReportRead)
async def regenerate_report(
    claim_id: uuid.UUID,
    current: User = Depends(require_role(UserRole.admin, UserRole.reviewer)),
    db: AsyncSession = Depends(get_db),
):
    claim = await claim_service.get_claim(db, current.tenant_id, claim_id)
    report = await report_service.generate(db, claim)
    await db.commit()
    out = ReportRead.model_validate(report)
    if report.s3_key_pdf:
        out.pdf_url = evidence_service.with_url(report.s3_key_pdf)
    if report.s3_key_html:
        out.html_url = evidence_service.with_url(report.s3_key_html)
    return out


# --- Human review (Sprint 4) -------------------------------------------------
@router.post("/{claim_id}/review", response_model=ReviewRead, status_code=status.HTTP_201_CREATED)
async def create_review(
    claim_id: uuid.UUID,
    body: ReviewCreate,
    request: Request,
    current: User = Depends(require_role(UserRole.reviewer, UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> ReviewRead:
    claim = await claim_service.get_claim(db, current.tenant_id, claim_id)
    review = await review_service.create_review(
        db, claim, current,
        decision=body.decision, notes=body.notes, overrides=body.overrides,
    )
    await audit_service.record(
        db, action="claim.review", entity_type="claim", entity_id=claim.id,
        actor_user_id=current.id, tenant_id=current.tenant_id,
        after={"decision": body.decision.value}, ip=client_ip(request),
    )
    await db.commit()
    return ReviewRead.model_validate(review)


@router.get("/{claim_id}/reviews", response_model=list[ReviewRead])
async def list_reviews(
    claim_id: uuid.UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    claim = await claim_service.get_claim(db, current.tenant_id, claim_id)
    return await review_service.list_reviews(db, claim.id)
