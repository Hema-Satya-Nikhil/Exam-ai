from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core import security
from app.core.config import settings
from app.models.academic import RefreshSession, User
from app.schemas.auth import TokenPair, UserContext


def _as_aware_utc(value: datetime | None) -> datetime | None:
    """Return ``value`` as a timezone-aware UTC ``datetime``.

    ``DateTime(timezone=True)`` columns store UTC-aware values on PostgreSQL,
    but SQLite returns the naive value (it does not persist timezone info).
    Normalize naive values to UTC so they can be compared consistently against
    ``datetime.now(timezone.utc)`` without weakening expiry validation.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class AuthService:
    """Business logic for user authentication and session management."""

    # ------------------------------------------------------------------
    # Password helpers
    # ------------------------------------------------------------------

    @staticmethod
    def hash_password(password: str) -> str:
        return security.hash_password(password)

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        return security.verify_password(plain, hashed)

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    async def register_faculty(self, session: AsyncSession, email: str, full_name: str, password: str,
                               role: str = "faculty", request_admin: bool = False) -> User:
        """Self-register a new faculty member.

        The account is created **inactive** (``is_active=False``) so an
        administrator must approve it before the user can sign in. To prevent
        privilege escalation the only accepted role is ``faculty`` — any other
        value is coerced to ``faculty``. The faculty role is created on demand.

        ``request_admin=True`` additionally creates a PENDING admin-access
        request in the SAME transaction. It never grants ADMIN directly and
        never sets the protected primary-admin flag.
        """
        from app.services.admin_service import get_or_create_role  # local import avoids cycle

        safe_role = role if role == "faculty" else "faculty"
        role_obj = await get_or_create_role(session, safe_role, "Faculty member")

        existing = await self.get_user_by_email(session, email)
        if existing is not None:
            return existing

        user = User(
            email=email,
            full_name=full_name,
            password_hash=self.hash_password(password),
            is_active=False,  # pending admin approval
            is_primary_admin=False,  # a registration can NEVER create the Main Admin
            roles=[role_obj],
        )
        session.add(user)
        await session.flush()

        if request_admin:
            from app.models.admin_access import AdminAccessRequest

            session.add(
                AdminAccessRequest(
                    user_id=user.id,
                    requested_role="admin",
                    status="pending",
                )
            )
            await session.flush()
        return user

    # ------------------------------------------------------------------
    # User lookup
    # ------------------------------------------------------------------

    @staticmethod
    async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
        # Emails are case-insensitive by convention; match ignoring case and
        # surrounding whitespace so login/refresh never spuriously fail on
        # different casing than the stored value. Roles are eager-loaded in a
        # single round-trip: they are always needed for token issuance, and a
        # lazy load costs an extra database round-trip on every login.
        result = await session.execute(
            select(User)
            .options(selectinload(User.roles))
            .where(func.lower(User.email) == email.strip().lower())
        )
        return result.scalars().first()

    @staticmethod
    async def get_user_by_id(session: AsyncSession, user_id: str) -> User | None:
        result = await session.execute(
            select(User).options(selectinload(User.roles)).where(User.id == user_id)
        )
        return result.scalars().first()

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    async def authenticate_user(
        self, session: AsyncSession, email: str, password: str
    ) -> User | None:
        """Return the User if credentials are valid and account active, else None."""
        user, _reason = await self.authenticate_user_with_reason(session, email, password)
        return user

    async def authenticate_user_with_reason(
        self, session: AsyncSession, email: str, password: str
    ) -> tuple[User | None, str | None]:
        """Authenticate and explain *why* login failed.

        Returns ``(user, None)`` on success. On failure returns ``(None, reason)``
        where reason is one of:

        - ``"invalid_credentials"`` — unknown email or wrong password
        - ``"pending_approval"``   — registered but not yet approved by an admin
        - ``"account_rejected"``   — explicitly rejected by an administrator
        - ``"account_disabled"``   — previously active, disabled by an administrator

        The distinction between pending / rejected / disabled is derived from the
        most recent admin audit action for the account, so no extra user column
        is introduced and the existing audit infrastructure stays authoritative.
        """
        user = await self.get_user_by_email(session, email)
        if user is None:
            return None, "invalid_credentials"
        if not self.verify_password(password, user.password_hash):
            return None, "invalid_credentials"
        if user.is_active:
            return user, None

        from app.models.audit import AuditLog  # local import avoids cycles

        latest = (
            await session.execute(
                select(AuditLog)
                .where(AuditLog.entity_type == "user", AuditLog.entity_id == user.id)
                .order_by(AuditLog.created_at.desc())
                .limit(1)
            )
        ).scalars().first()
        if latest is not None and latest.action == "disable_user":
            return None, "account_disabled"
        if latest is not None and latest.action == "reject_faculty":
            return None, "account_rejected"
        return None, "pending_approval"

    # ------------------------------------------------------------------
    # Token issuance
    # ------------------------------------------------------------------

    def _role_names(self, user: User) -> list[str]:
        return [role.name for role in user.roles]

    async def issue_token_pair(self, session: AsyncSession, user: User) -> TokenPair:
        """Issue an access + refresh token pair and persist the refresh session."""
        roles = self._role_names(user)
        access_token = security.create_access_token(user.id, roles)

        jti = str(uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.jwt_refresh_expire)
        refresh_session = RefreshSession(
            jti=jti,
            user_id=user.id,
            expires_at=expires_at,
        )
        session.add(refresh_session)
        await session.commit()

        refresh_token = security.create_refresh_token(user.id, jti)
        return TokenPair(access_token=access_token, refresh_token=refresh_token)

    async def refresh_tokens(
        self, session: AsyncSession, refresh_token_str: str
    ) -> TokenPair | None:
        """Validate, rotate, and reissue a token pair from a refresh token string."""
        payload = security.decode_refresh_token(refresh_token_str)
        if payload is None:
            return None

        jti: str | None = payload.get("jti")
        user_id: str | None = payload.get("sub")
        if not jti or not user_id:
            return None

        # Look up the session record
        result = await session.execute(
            select(RefreshSession).where(RefreshSession.jti == jti)
        )
        db_session = result.scalars().first()
        if db_session is None:
            return None  # Unknown / already rotated away
        if db_session.revoked:
            return None  # Explicitly revoked (logout)
        if db_session.user_id != user_id:
            return None
        db_expires = _as_aware_utc(db_session.expires_at)
        if db_expires is not None and db_expires <= datetime.now(timezone.utc):
            return None  # Expired

        # Revoke old session (rotation — prevents replay)
        db_session.revoked = True
        await session.flush()

        # Fetch user with roles
        user = await self.get_user_by_id(session, user_id)
        if user is None or not user.is_active:
            await session.commit()
            return None

        return await self.issue_token_pair(session, user)

    async def revoke_refresh_token(
        self, session: AsyncSession, refresh_token_str: str
    ) -> bool:
        """Revoke a refresh session by JTI (logout). Returns True if found."""
        payload = security.decode_refresh_token(refresh_token_str)
        if payload is None:
            return False
        jti = payload.get("jti")
        if not jti:
            return False

        result = await session.execute(
            select(RefreshSession).where(RefreshSession.jti == jti)
        )
        db_session = result.scalars().first()
        if db_session is None:
            return False
        db_session.revoked = True
        await session.commit()
        return True

    # ------------------------------------------------------------------
    # Legacy shim — keeps existing code that calls create_access_token
    # ------------------------------------------------------------------

    def create_access_token(self, user: UserContext, **_: object) -> str:  # noqa: ARG002
        return security.create_access_token(
            user.user_id,
            list(user.roles),
            email=str(user.email),
            full_name=user.full_name,
        )

    def verify_access_token(self, token: str) -> UserContext | None:
        payload = security.decode_access_token(token)
        if payload is None:
            return None
        email = payload.get("email")
        full_name = payload.get("full_name")
        if not email or not full_name:
            return None
        return UserContext(
            user_id=str(payload["sub"]),
            email=str(email),
            full_name=str(full_name),
            roles=list(payload.get("roles", [])),
            is_active=True,
        )
