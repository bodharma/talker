"""Authentication service — password hashing, user CRUD, OAuth helpers."""

import logging
import secrets

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from talker.models.db import User

log = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        return bcrypt.checkpw(password.encode(), hashed.encode())

    @staticmethod
    def generate_token() -> str:
        return secrets.token_urlsafe(32)

    async def get_user_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> User | None:
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_oauth(self, provider: str, oauth_id: str) -> User | None:
        stmt = select(User).where(
            User.oauth_provider == provider, User.oauth_id == oauth_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(
        self,
        email: str,
        name: str,
        password: str | None = None,
        role: str = "patient",
        oauth_provider: str | None = None,
        oauth_id: str | None = None,
    ) -> User:
        user = User(
            email=email,
            name=name,
            password_hash=self.hash_password(password) if password else None,
            role=role,
            oauth_provider=oauth_provider,
            oauth_id=oauth_id,
            email_verified=bool(oauth_provider),
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def authenticate(self, email: str, password: str) -> User | None:
        user = await self.get_user_by_email(email)
        if not user or not user.password_hash:
            return None
        if not self.verify_password(password, user.password_hash):
            return None
        if not user.is_active:
            return None
        return user

    async def ensure_admin(self, email: str, password: str) -> User | None:
        """Bootstrap: create admin if no admin exists. Returns admin user or None."""
        if not email or not password:
            return None
        stmt = select(User).where(User.role == "admin")
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            return None

        user = await self.get_user_by_email(email)
        if user:
            user.role = "admin"
            user.password_hash = self.hash_password(password)
        else:
            user = await self.create_user(
                email=email, name="Admin", password=password, role="admin"
            )
        await self.db.commit()
        log.info("Bootstrapped admin user: %s", email)
        return user
