"""Seed a demo tenant + admin user. Idempotent.

Run: python -m app.scripts.seed
"""
import asyncio

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.db.models.component import Component, FraudIndicatorDef
from app.db.models.enums import UserRole
from app.db.models.inspection_template import InspectionTemplate
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.db.session import SessionLocal
from app.services import audit_service

log = get_logger(__name__)

COMPONENTS = [
    ("charging_port", "Charging Port"),
    ("charging_connector", "Charging Connector"),
    ("wiring_harness", "Wiring Harness"),
    ("motor_housing", "Motor Housing"),
    ("controller_housing", "Controller Housing"),
    ("battery_enclosure", "Battery Enclosure Exterior"),
    ("side_panel", "Side Panel"),
    ("body_panel", "Body Panel"),
    ("footboard", "Footboard"),
    ("headlight", "Headlight"),
    ("tail_light", "Tail Light"),
    ("mirror", "Mirror"),
    ("mudguard", "Mudguard"),
    ("protective_cover", "Protective Cover"),
    ("seal", "Seal"),
    ("fastener", "Fastener"),
]

INDICATORS = [
    ("impact_damage", "Impact damage", 2.0, "high"),
    ("crack", "Crack", 1.5, "medium"),
    ("scratch", "Scratch", 0.5, "low"),
    ("broken", "Broken component", 2.0, "high"),
    ("missing_part", "Missing part", 2.0, "high"),
    ("corrosion", "Corrosion", 1.0, "medium"),
    ("rust", "Rust", 1.0, "medium"),
    ("water_ingress", "Water ingress indicator", 2.5, "high"),
    ("tamper_mark", "Tampering mark", 3.0, "high"),
    ("missing_seal", "Missing seal", 2.0, "high"),
    ("opened_enclosure", "Opened enclosure", 3.0, "high"),
    ("non_standard_mod", "Non-standard modification", 2.5, "high"),
    ("incomplete_inspection", "Incomplete inspection", 1.0, "medium"),
    # Serial-number lifecycle (anti swap-and-sell)
    ("serial_not_registered", "Serial not registered to any vehicle", 3.0, "high"),
    ("serial_not_on_vin", "Serial belongs to a different VIN", 3.5, "high"),
    ("serial_reused", "Serial already claimed/removed before", 3.5, "high"),
    ("serial_no_photo_proof", "Claimed serial not visible in photos", 2.0, "high"),
    ("replacement_equals_removed", "Replacement serial equals removed", 3.0, "high"),
    ("replacement_serial_duplicate", "Replacement serial active elsewhere", 2.5, "high"),
    ("removed_serial_missing", "No serial recorded for claimed part", 1.0, "medium"),
]

# Demo: parts registered to demo VINs (so serial checks have something to verify).
DEMO_PARTS = [
    ("1HGBH41JXMN109186", "charging_port", "CP-1HG-0098"),
    ("1HGBH41JXMN109186", "motor_housing", "MH-1HG-5521"),
    ("1HGBH41JXMN109186", "controller_housing", "CH-1HG-7732"),
    ("5YJ3E1EA7KF000316", "charging_port", "CP-5YJ-3310"),
    ("5YJ3E1EA7KF000316", "battery_enclosure", "BE-5YJ-9001"),
]

TEMPLATES = [
    (
        "2-Wheeler Standard Inspection",
        ["front_34", "rear_34", "left_side", "right_side", "charging_port",
         "vin_plate", "battery_enclosure", "motor", "footboard", "lights"],
        {"vin": True, "audio_narration": True, "min_images": 4},
    ),
    (
        "4-Wheeler Standard Inspection",
        ["front_left_34", "front_right_34", "rear_left_34", "rear_right_34",
         "charging_port", "vin_windshield", "vin_doorjamb", "underbody",
         "battery_enclosure", "lights"],
        {"vin": True, "audio_narration": True, "min_images": 6},
    ),
]


async def seed() -> None:
    configure_logging()
    async with SessionLocal() as session:
        tenant = await session.scalar(
            select(Tenant).where(Tenant.slug == settings.seed_tenant_slug)
        )
        if tenant is None:
            tenant = Tenant(
                name=settings.seed_tenant_name, slug=settings.seed_tenant_slug
            )
            session.add(tenant)
            await session.flush()
            log.info("created tenant", slug=tenant.slug)

        admin = await session.scalar(
            select(User).where(
                User.tenant_id == tenant.id,
                User.email == settings.seed_admin_email.lower(),
            )
        )
        if admin is None:
            admin = User(
                tenant_id=tenant.id,
                email=settings.seed_admin_email.lower(),
                full_name="Demo Admin",
                role=UserRole.admin,
                password_hash=hash_password(settings.seed_admin_password),
            )
            session.add(admin)
            await session.flush()
            await audit_service.record(
                session,
                action="user.seed",
                entity_type="user",
                entity_id=admin.id,
                tenant_id=tenant.id,
            )
            log.info("created admin", email=admin.email)
        else:
            log.info("admin already exists", email=admin.email)

        # Catalog: components
        existing_codes = set(
            await session.scalars(
                select(Component.code).where(Component.tenant_id == tenant.id)
            )
        )
        for code, name in COMPONENTS:
            if code not in existing_codes:
                session.add(Component(tenant_id=tenant.id, code=code, name=name))

        # Catalog: risk indicators
        existing_ind = set(
            await session.scalars(
                select(FraudIndicatorDef.code).where(
                    FraudIndicatorDef.tenant_id == tenant.id
                )
            )
        )
        for code, label, weight, sev in INDICATORS:
            if code not in existing_ind:
                session.add(
                    FraudIndicatorDef(
                        tenant_id=tenant.id, code=code, label=label,
                        default_weight=weight, severity=sev,
                    )
                )

        # Catalog: templates
        existing_tpl = set(
            await session.scalars(
                select(InspectionTemplate.name).where(
                    InspectionTemplate.tenant_id == tenant.id
                )
            )
        )
        for name, views, evidence in TEMPLATES:
            if name not in existing_tpl:
                session.add(
                    InspectionTemplate(
                        tenant_id=tenant.id, name=name,
                        required_views=views, required_evidence=evidence,
                    )
                )

        # Demo vehicle-parts registry
        from app.db.models.parts import VehiclePart

        existing_serials = set(
            await session.scalars(
                select(VehiclePart.serial).where(VehiclePart.tenant_id == tenant.id)
            )
        )
        for vin, comp_code, serial in DEMO_PARTS:
            if serial not in existing_serials:
                session.add(
                    VehiclePart(
                        tenant_id=tenant.id, vin=vin, component_code=comp_code,
                        serial=serial, is_active=True,
                    )
                )

        # Demo telemetry histories (different ground-truth profiles per VIN)
        from app.services import telemetry_service

        demo_telemetry = [
            ("1HGBH41JXMN109186", "abuse"),
            ("5YJ3E1EA7KF000316", "latent_defect"),
        ]
        for vin, profile in demo_telemetry:
            if not await telemetry_service.has_telemetry(session, tenant.id, vin):
                await telemetry_service.simulate(
                    session, tenant.id, vin, profile=profile, days=180
                )

        await session.commit()
        log.info(
            "seed complete",
            tenant=settings.seed_tenant_slug,
            admin=settings.seed_admin_email,
            components=len(COMPONENTS),
            indicators=len(INDICATORS),
            templates=len(TEMPLATES),
        )


if __name__ == "__main__":
    asyncio.run(seed())
