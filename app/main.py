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
        status_payload = {
            "status": "ok" if self.connection_manager.is_connected else "degraded",
            "version": "2.2.0",
            "telegram": conn.get("user", "unknown"),
            "bot": conn.get("bot", "unknown"),
            "index": stats.get("state", "unknown").lower(),
            "tracks": stats.get("total_tracks", 0),
            "users": len(self.access_manager.get_all_approved()) + 1,
            "pending_requests": len(self.access_manager.get_all_pending()),
        }
        if self.connection_manager.user_error:
            status_payload["user_error"] = self.connection_manager.user_error
        return status_payload

    async def start(self) -> None:
        logger.info("=" * 60)
        logger.info("Starting Telegram Personal Music Cloud (TPMC) v2.0...")
        logger.info("=" * 60)

        # 1. Start HTTP Health Server first (for Render health checks)
        await self.health_server.start()

        # 2. Connect Telegram clients (fault-tolerant: never crashes the web server)
        await self.connection_manager.connect_all(
            bot_manager=self.bot_manager,
            user_manager=self.user_manager,
        )

        from app.telegram.connection import ConnectionState

        # 3. Validate channel access (only if user client is connected)
        if self.connection_manager.user_state == ConnectionState.CONNECTED:
            try:
                await self.user_manager.validate_channel()
            except Exception as e:
                logger.error(f"Failed to validate storage channel: {e}. WebApp remains online.")
        else:
            logger.warning(
                "Telegram User client is not connected (%s). "
                "Channel validation and library indexing will begin once a valid TELEGRAM_SESSION is provided.",
                self.connection_manager.user_state.value,
            )

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

        # 5. Start non-blocking background indexing (Fast Boot) if user client is connected
        if self.connection_manager.user_state == ConnectionState.CONNECTED:
            logger.info("Launching background library indexing...")
            await self.indexer.start_indexing(
                user_client=self.user_manager,
                channel_id=self.config.channel_id,
                reset=False,
            )
        else:
            logger.info(
                "Health & WebApp server is running at http://%s:%s",
                self.config.host,
                self.config.port,
            )

        # 6. Start keep-alive loop to prevent Render Free tier from sleeping
        if self.config.webapp_url and self.config.webapp_url.startswith("https://"):
            self._keep_alive_task = asyncio.create_task(self._keep_alive_loop())

        logger.info("TPMC is fully initialized and operational!")

        # Keep running until stop_event is triggered
        await self.stop_event.wait()

    async def _keep_alive_loop(self) -> None:
        """Ping public endpoint every 10 minutes to prevent Render Free tier from sleeping."""
        import aiohttp
        ping_url = f"{self.config.webapp_url}/health"
        logger.info(f"Keep-alive self-ping worker active for {ping_url}")
        # Wait 3 minutes after startup before initial ping
        await asyncio.sleep(180)
        async with aiohttp.ClientSession() as session:
            while not self.stop_event.is_set():
                try:
                    async with session.get(ping_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        logger.debug(f"Keep-alive ping to {ping_url} status: {resp.status}")
                except Exception as e:
                    logger.debug(f"Keep-alive ping notice: {e}")

                # Regularly reclaim unused memory to strictly stay under Render 512MB RAM
                import gc
                gc.collect()

                try:
                    await asyncio.wait_for(self.stop_event.wait(), timeout=600)
                    break
                except asyncio.TimeoutError:
                    pass

    async def shutdown(self) -> None:
        """Gracefully shut down all components on SIGTERM / SIGINT."""
        logger.info("Initiating graceful shutdown sequence...")

        # 0. Cancel keep-alive task
        if hasattr(self, "_keep_alive_task") and self._keep_alive_task and not self._keep_alive_task.done():
            self._keep_alive_task.cancel()

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
