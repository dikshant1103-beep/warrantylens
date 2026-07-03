"""Test fixtures. Requires a reachable Postgres (TEST DB).

Set DATABASE_URL to a disposable test database before running, e.g.:
  DATABASE_URL=postgresql+asyncpg://warrantylens:warrantylens@localhost:5432/warrantylens_test
"""
from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.models.enums import UserRole
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.main import app

engine = create_async_engine(settings.database_url, poolclass=NullPool)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean():
    yield
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())


async def _override_get_db():
    async with TestSession() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def tenant() -> Tenant:
    async with TestSession() as session:
        t = Tenant(name="Test Tenant", slug="test")
        session.add(t)
        await session.commit()
        await session.refresh(t)
        return t


@pytest_asyncio.fixture
async def make_user(tenant: Tenant):
    async def _make(
        email: str, password: str = "Password123!", role: UserRole = UserRole.mechanic
    ) -> User:
        async with TestSession() as session:
            u = User(
                tenant_id=tenant.id,
                email=email.lower(),
                full_name=email.split("@")[0],
                role=role,
                password_hash=hash_password(password),
            )
            session.add(u)
            await session.commit()
            await session.refresh(u)
            return u

    return _make


async def login(client: AsyncClient, email: str, password: str = "Password123!") -> str:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]
