import hashlib
import secrets
from dataclasses import dataclass

from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import get_db, now
from .models import ApiToken, Membership, Project, SessionRecord, User

passwords = PasswordHasher()


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def token_value() -> str:
    return secrets.token_urlsafe(40)


def encrypt(value: str) -> str:
    if not settings().app_key:
        raise ValueError("APP_KEY must be configured externally to save credentials")
    return Fernet(settings().app_key.encode()).encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return Fernet(settings().app_key.encode()).decrypt(value.encode()).decode()


@dataclass
class Principal:
    user: User
    token: ApiToken | None = None


async def principal(request: Request, db: AsyncSession = Depends(get_db)) -> Principal:
    header = request.headers.get("authorization", "")
    record = None
    token = None
    if header.startswith("Bearer "):
        token = await db.scalar(
            select(ApiToken).where(
                ApiToken.digest == digest(header[7:]),
                ApiToken.revoked.is_(False),
                ApiToken.expires_at > now(),
            )
        )
        record = token
    else:
        raw = request.cookies.get("evaldock_session")
        if raw:
            record = await db.scalar(
                select(SessionRecord).where(
                    SessionRecord.digest == digest(raw), SessionRecord.expires_at > now()
                )
            )
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if (
                request.headers.get("origin") != settings().public_origin
                or request.headers.get("x-evaldock-csrf") != "1"
            ):
                raise HTTPException(403, "Same-origin CSRF header required")
    if record is None:
        raise HTTPException(401, "Authentication required")
    user = await db.get(User, record.user_id)
    if user is None:
        raise HTTPException(401, "Authentication required")
    return Principal(user, token)


async def workspace_access(
    db: AsyncSession, who: Principal, workspace_id: str, write: bool = False, owner: bool = False
) -> Membership:
    membership = await db.scalar(
        select(Membership).where(
            Membership.workspace_id == workspace_id, Membership.user_id == who.user.id
        )
    )
    if not membership or (who.token and who.token.workspace_id != workspace_id):
        raise HTTPException(404, "Workspace not found")
    if who.token and ("write" if write else "read") not in who.token.scopes:
        raise HTTPException(403, "API token scope does not allow this operation")
    if (write and membership.role == "viewer") or (owner and membership.role != "owner"):
        raise HTTPException(403, "Insufficient role")
    return membership


async def project_access(
    db: AsyncSession, who: Principal, project_id: str, write: bool = False, owner: bool = False
) -> Project:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    await workspace_access(db, who, project.workspace_id, write, owner)
    return project
