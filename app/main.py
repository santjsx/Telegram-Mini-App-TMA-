"""
Main application entry point for Telegram Personal Music Cloud (TPMC).
Orchestrates lifecycle, startup validation, dual Telegram connection,
background indexing, health server, and graceful shutdown.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from telethon.tl.custom.message import Message
from app.config import Config
from app.logging_config import setup_logging
from app.telegram.connection import TelegramConnectionManager
from app.telegram.bot import BotManager
from app.telegram.user_client import UserClientManager
from app.index.indexer import MusicIndexer
from app.index.parser import MetadataParser
from app.jobs.delivery import DeliveryEngine
from app.jobs.manager import JobManager
from app.commands.status import StatusCommandHandler
from app.commands.search import SearchCommandHandler
from app.commands.download import DownloadCommandHandler
from app.commands.admin import AdminCommandHandler
from app.commands.router import CommandRouter
from app.auth.manager import AccessManager
from app.health.server import HealthServer

logger = logging.getLogger("tpmc.main")


class TPMCApp:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.stop_event = asyncio.Event()

        # Core subsystems
        self.access_manager = AccessManager(
            admin_id=config.authorized_user_id,
            initial_approved_ids=config.approved_user_ids,
        )
        self.connection_manager = TelegramConnectionManager(config)
        self.bot_manager = BotManager(config, access_manager=self.access_manager)
        self.user_manager = UserClientManager(config)
        self.indexer = MusicIndexer()
        self.delivery_engine = DeliveryEngine(
            user_client=self.user_manager,
            bot_manager=self.bot_manager,
            flood_wait_max=config.flood_wait_max,
        )
        self.job_manager = JobManager(self.delivery_engine)

        # Command handlers
        self.status_handler = StatusCommandHandler(
            connection_manager=self.connection_manager,
            indexer=self.indexer,
            job_manager=self.job_manager,
        )
        self.search_handler = SearchCommandHandler(
            indexer=self.indexer,
            job_manager=self.job_manager,
        )
        self.download_handler = DownloadCommandHandler(
            indexer=self.indexer,
            job_manager=self.job_manager,
            bot_manager=self.bot_manager,
        )
        self.admin_handler = AdminCommandHandler(
            indexer=self.indexer,
            user_client=self.user_manager,
            config=self.config,
            access_manager=self.access_manager,
            bot_manager=self.bot_manager,
        )

        self.router = CommandRouter(
            status_handler=self.status_handler,
            search_handler=self.search_handler,
            download_handler=self.download_handler,
            admin_handler=self.admin_handler,
            access_manager=self.access_manager,
            webapp_url=config.webapp_url,
        )

        # Health & WebApp Streaming HTTP Server
        self.health_server = HealthServer(
            host=config.host,
            port=config.port,
            status_provider=self._get_health_status,
            indexer=self.indexer,
            user_client=self.user_manager,
            access_manager=self.access_manager,
            bot_manager=self.bot_manager,
            config=self.config,
        )

    def _get_health_status(self) -> dict:
        conn = self.connection_manager.get_status_summary()
        stats = self.indexer.get_stats()
        return {
            "status": "ok" if self.connection_manager.is_connected else "degraded",
            "telegram": conn.get("user", "unknown"),
            "bot": conn.get("bot", "unknown"),
            "index": stats.get("state", "unknown").lower(),
            "tracks": stats.get("total_tracks", 0),
            "users": len(self.access_manager.get_all_approved()) + 1,
            "pending_requests": len(self.access_manager.get_all_pending()),
        }

    async def start(self) -> None:
        logger.info("=" * 60)
        logger.info("Starting Telegram Personal Music Cloud (TPMC) v2.0...")
        logger.info("=" * 60)

        # 1. Start HTTP Health Server first (for Render health checks)
        await self.health_server.start()

        # 2. Connect Telegram clients
        try:
            await self.connection_manager.connect_all(
                bot_manager=self.bot_manager,
                user_manager=self.user_manager,
            )
        except Exception as e:
            logger.critical(f"Failed to authenticate Telegram clients: {e}. Exiting.")
            await self.shutdown()
            sys.exit(1)

        # 3. Validate channel access
        try:
            await self.user_manager.validate_channel()
        except Exception as e:
            logger.critical(f"Failed to validate storage channel: {e}. Exiting.")
            await self.shutdown()
            sys.exit(1)

        # 4. Attach command & callback routers + real-time channel post indexer
        async def handle_new_channel_post(message: Message) -> None:
            track = MetadataParser.extract_track(message, self.config.channel_id)
            if track:
                self.indexer.add_track(track)
                logger.info(f"Real-time indexed new channel track: '{track.display_title}'")

        self.bot_manager.set_routers(
            command_router=self.router.route_message,
            callback_router=self.router.route_callback,
            channel_post_handler=handle_new_channel_post,
            unauthorized_handler=self.admin_handler.handle_unauthorized_message,
        )

        # 5. Start non-blocking background indexing (Fast Boot)
        logger.info("Launching background library indexing...")
        await self.indexer.start_indexing(
            user_client=self.user_manager,
            channel_id=self.config.channel_id,
            reset=False,
        )

        logger.info("TPMC is fully initialized and operational!")

        # Keep running until stop_event is triggered
        await self.stop_event.wait()

    async def shutdown(self) -> None:
        """Gracefully shut down all components on SIGTERM / SIGINT."""
        logger.info("Initiating graceful shutdown sequence...")

        # 1. Cancel running delivery jobs
        if self.job_manager:
            await self.job_manager.cancel_active_job()

        # 2. Disconnect Telegram clients
        if self.connection_manager:
            await self.connection_manager.disconnect_all()

        # 3. Stop Health HTTP Server
        if self.health_server:
            await self.health_server.stop()

        self.stop_event.set()
        logger.info("Graceful shutdown completed. Exiting cleanly.")


async def main() -> None:
    try:
        config = Config.load_from_env()
    except ValueError as e:
        print(f"\n[FATAL CONFIGURATION ERROR]\n{e}\n", file=sys.stderr)
        sys.exit(1)

    # Setup sanitized logging
    secrets = [
        config.bot_token,
        config.api_hash,
        config.telegram_session,
    ]
    setup_logging(level_name=config.log_level, secrets=secrets)

    app = TPMCApp(config)
    loop = asyncio.get_running_loop()

    def _handle_signal() -> None:
        logger.info("Received termination signal.")
        asyncio.create_task(app.shutdown())

    # Register signals on Unix / Render
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            # Windows does not support loop.add_signal_handler
            signal.signal(sig, lambda *_: asyncio.create_task(app.shutdown()))

    try:
        await app.start()
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
