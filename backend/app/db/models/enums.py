import enum


class UserRole(str, enum.Enum):
    admin = "admin"
    reviewer = "reviewer"
    mechanic = "mechanic"


class ClaimStatus(str, enum.Enum):
    draft = "draft"
    queued = "queued"
    processing = "processing"
    ready_for_review = "ready_for_review"
    reviewed = "reviewed"
    needs_more_evidence = "needs_more_evidence"
    failed = "failed"


class MediaKind(str, enum.Enum):
    video = "video"
    image = "image"


class MediaStatus(str, enum.Enum):
    pending = "pending"      # presigned issued, not yet uploaded
    uploaded = "uploaded"    # upload confirmed (sha256 verified)
    processed = "processed"  # frames/AI extracted
    rejected = "rejected"


class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    skipped = "skipped"


class OcrFieldType(str, enum.Enum):
    vin = "vin"
    serial = "serial"
    label = "label"
    other = "other"


class PartEventType(str, enum.Enum):
    registered = "registered"       # part recorded as belonging to a VIN
    claimed_removed = "claimed_removed"  # part claimed defective & removed
    installed = "installed"         # replacement part installed
    flagged = "flagged"             # serial check raised a concern


class ReviewDecision(str, enum.Enum):
    """The HUMAN reviewer's decision. The system never writes this — it only
    produces evidence and advisory risk indicators."""

    approved = "approved"
    rejected = "rejected"
    needs_more_evidence = "needs_more_evidence"
    escalated = "escalated"
