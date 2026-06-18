"""Repository for User records."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.user import User


class UserRepository:
    """CRUD access for User records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """Return the User with the given telegram_id, or None if not found."""
        result = await self._session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()

    async def get_first(self) -> User | None:
        """Return the first (and in practice only) user row, or None."""
        result = await self._session.execute(select(User).limit(1))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[User]:
        """Return all User rows ordered by telegram_id."""
        result = await self._session.execute(select(User).order_by(User.telegram_id))
        return list(result.scalars().all())

    async def get_or_create(self, telegram_id: int, language: str) -> User:
        """Return the User with the given telegram_id, creating it if absent; caller commits."""
        user = await self.get_by_telegram_id(telegram_id)
        if user is None:
            user = User(telegram_id=telegram_id, language=language)
            self._session.add(user)
            await self._session.flush()
            await self._session.refresh(user)
        return user

    async def save(self, user: User) -> User:
        """Flush and refresh the user row; caller is responsible for commit."""
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user
