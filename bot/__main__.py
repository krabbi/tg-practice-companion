"""Bot entry point — python -m bot."""

import asyncio
import logging

from aiogram.types import BotCommand

from bot.bot import create_bot, create_dispatcher
from bot.config import get_config
from bot.db import build_session_factory, create_tables
from bot.scheduler import start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Initialise the database, wire the bot, start the scheduler, and begin polling."""
    config = get_config()

    # Ensure all tables exist (idempotent; real migrations run via Alembic in prod)
    await create_tables(config.database_url)

    session_factory = build_session_factory(config.database_url)
    bot = create_bot(config)
    dp = create_dispatcher(config, session_factory=session_factory)

    # Start the APScheduler (60s tick + daily housekeeping)
    scheduler = start_scheduler(bot, session_factory, config)

    # Register commands visible in the Telegram menu
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Начать / Start"),
            BotCommand(command="help", description="Помощь / Help"),
            BotCommand(command="skip_day", description="Пропустить сегодня / Skip today"),
        ]
    )

    logger.info("Starting polling …")
    try:
        await dp.start_polling(bot, session_factory=session_factory)
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
