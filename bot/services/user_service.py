"""Business logic for User provisioning."""

from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.user import User
from bot.repositories.user_repository import UserRepository


class UserService:
    """Provision and retrieve User rows."""

    def __init__(self, session: AsyncSession, repo: UserRepository) -> None:
        self._session = session
        self._repo = repo

    async def get_or_create(self, telegram_id: int, language: str) -> User:
        """Return the User, creating it on first contact; owns the commit."""
        user = await self._repo.get_or_create(telegram_id, language=language)
        await self._session.commit()
        return user
