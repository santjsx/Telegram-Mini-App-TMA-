"""
Telegram Bot client manager.
Handles incoming owner commands, strict authorization enforcement,
and bot-to-user interactions.
"""

from __future__ import annotations

import logging
from typing import Callable, Coroutine, Any, Optional
from pathlib import Path
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.custom.message import Message
from telethon.errors import AuthKeyDuplicatedError, SecurityError

from app.config import Config
from app.auth.manager import AccessManager

logger = logging.getLogger(__name__)


class BotManager:
    def __init__(self, config: Config, access_manager: Optional[AccessManager] = None) -> None:
        self.config = config
        self.access_manager = access_manager

        # Check for persistent bot session string:
        # 1. Config / env var BOT_SESSION
        # 2. Local file data/bot_session.txt
        initial_session = config.bot_session or ""
        session_file = Path("data/bot_session.txt")
        if not initial_session and session_file.exists():
            try:
                initial_session = session_file.read_text(encoding="utf-8").strip()
            except Exception:
                initial_session = ""

        self.session = StringSession(initial_session or None)
        self.client = TelegramClient(
            self.session,
            config.api_id,
            config.api_hash,
            auto_reconnect=True,
            connection_retries=5,
            retry_delay=2,
        )
        self._command_router: Optional[Callable[[Message], Coroutine[Any, Any, None]]] = None
        self._callback_router: Optional[Callable[[events.CallbackQuery.Event], Coroutine[Any, Any, None]]] = None
        self._channel_post_handler: Optional[Callable[[Message], Coroutine[Any, Any, None]]] = None
        self._unauthorized_handler: Optional[Callable[[Message], Coroutine[Any, Any, None]]] = None

    def set_routers(
        self,
        command_router: Callable[[Message], Coroutine[Any, Any, None]],
        callback_router: Optional[Callable[[events.CallbackQuery.Event], Coroutine[Any, Any, None]]] = None,
        channel_post_handler: Optional[Callable[[Message], Coroutine[Any, Any, None]]] = None,
        unauthorized_handler: Optional[Callable[[Message], Coroutine[Any, Any, None]]] = None,
    ) -> None:
        self._command_router = command_router
        self._callback_router = callback_router
        self._channel_post_handler = channel_post_handler
        self._unauthorized_handler = unauthorized_handler
        self._register_handlers()

    async def connect(self) -> None:
        """Authenticate and start the Bot using BOT_TOKEN with automatic self-healing on IP conflict."""
        try:
            await self._perform_connect()
        except (AuthKeyDuplicatedError, SecurityError, Exception) as e:
            err_msg = str(e).lower()
            if (
                isinstance(e, (AuthKeyDuplicatedError, SecurityError))
                or "two different ip addresses" in err_msg
                or "session file) was used" in err_msg
                or "authkeyduplicated" in err_msg
                or "authorization key" in err_msg
                or "auth_key" in err_msg
            ):
                logger.warning(
                    f"⚠️ Bot session authorization key invalidated by Telegram (two different IP addresses conflict): {e}. "
                    "Self-healing: purging poisoned session and establishing a clean fresh authorization..."
                )
                try:
                    await self.client.disconnect()
                except Exception:
                    pass

                session_file = Path("data/bot_session.txt")
                if session_file.exists():
                    try:
                        session_file.unlink()
                    except Exception:
                        pass

                try:
                    self.config.bot_session = None
                except Exception:
                    pass

                self.session = StringSession(None)
                self.client = TelegramClient(
                    self.session,
                    self.config.api_id,
                    self.config.api_hash,
                    auto_reconnect=True,
                    connection_retries=5,
                    retry_delay=2,
                )
                await self._perform_connect(force_sign_in=True)
            else:
                raise e

    async def _perform_connect(self, force_sign_in: bool = False) -> None:
        await self.client.connect()
        if force_sign_in or not await self.client.is_user_authorized():
            logger.info("Bot authorization not found in session; signing in via BOT_TOKEN...")
            await self.client.sign_in(bot_token=self.config.bot_token)

        # Persist session string to avoid ImportBotAuthorizationRequest flood waits on restarts
        try:
            saved_str = self.session.save()
            if saved_str:
                session_file = Path("data/bot_session.txt")
                session_file.parent.mkdir(parents=True, exist_ok=True)
                session_file.write_text(saved_str, encoding="utf-8")
                logger.info("Bot session key persisted to data/bot_session.txt")
        except Exception as e:
            logger.debug(f"Could not persist bot session: {e}")

        me = await self.client.get_me()
        logger.info(f"Telegram Bot online as: @{me.username} [ID: {me.id}]")
        self._register_handlers()
        await self._register_bot_commands()

    async def _register_bot_commands(self) -> None:
        try:
            from telethon.tl.functions.bots import SetBotCommandsRequest
            from telethon.tl.types import BotCommand, BotCommandScopeDefault

            commands = [
                BotCommand(command="player", description="Open Web App luxury music player"),
                BotCommand(command="start", description="Open main menu and controls"),
                BotCommand(command="library", description="Explore artists, albums & genres"),
                BotCommand(command="search", description="Search tracks with 1-tap delivery"),
                BotCommand(command="download", description="Batch download matching tracks"),
                BotCommand(command="download_all", description="Deliver entire music library"),
                BotCommand(command="status", description="Cloud health & index status"),
                BotCommand(command="reindex", description="Rescan channel for new music"),
                BotCommand(command="users", description="Manage approved users & access requests"),
                BotCommand(command="cancel", description="Stop active download job"),
                BotCommand(command="help", description="Tagging format & guide"),
            ]
            await self.client(
                SetBotCommandsRequest(
                    scope=BotCommandScopeDefault(),
                    lang_code="",
                    commands=commands,
                )
            )
            logger.info("Successfully registered native Telegram bot commands.")

            # If WebApp URL is configured and using HTTPS, configure the Telegram bot Menu button
            if self.config.webapp_url and self.config.webapp_url.startswith("https://"):
                try:
                    from telethon.tl.functions.bots import SetBotMenuButtonRequest
                    from telethon.tl.types import BotMenuButton, InputUserEmpty

                    await self.client(
                        SetBotMenuButtonRequest(
                            user_id=InputUserEmpty(),
                            button=BotMenuButton(text="🎵 Web Player", url=self.config.webapp_url),
                        )
                    )
                    logger.info(f"Successfully configured Telegram WebApp menu button -> {self.config.webapp_url}")
                except Exception as e:
                    logger.debug(f"Could not set native WebApp menu button: {e}")
        except Exception as e:
            logger.warning(f"Could not register Telegram bot commands: {e}")

    def _register_handlers(self) -> None:
        if getattr(self, "_handlers_registered", False):
            return
        self._handlers_registered = True

        @self.client.on(events.NewMessage())
        async def handle_message(event: events.NewMessage.Event) -> None:
            # 1. If message is posted in the music storage channel
            if event.chat_id == self.config.channel_id:
                if self._channel_post_handler:
                    try:
                        await self._channel_post_handler(event.message)
                    except Exception as e:
                        logger.error(f"Error handling channel post: {e}")
                return

            # 2. Silently ignore outgoing messages from the bot itself
            if event.out:
                return

            # 3. Silently ignore messages from any other group or channel
            if not event.is_private:
                return

            # 4. Access control check in DM
            is_auth = (
                self.access_manager.is_authorized(event.sender_id)
                if self.access_manager
                else event.sender_id == self.config.authorized_user_id
            )
            if not is_auth:
                logger.info(
                    f"DM from unauthorized user ID {event.sender_id}. Prompting access request."
                )
                if self._unauthorized_handler:
                    try:
                        await self._unauthorized_handler(event.message)
                    except Exception as e:
                        logger.error(f"Error handling unauthorized message: {e}")
                else:
                    await event.reply("Access denied.")
                return

            if self._command_router:
                try:
                    await self._command_router(event.message)
                except Exception as e:
                    logger.error(f"Error handling command '{event.message.text}': {e}", exc_info=True)
                    await event.reply(f"⚠️ An error occurred while processing your command: {e}")

        @self.client.on(events.CallbackQuery())
        async def handle_callback(event: events.CallbackQuery.Event) -> None:
            data = event.data.decode("utf-8") if event.data else ""
            is_auth = (
                self.access_manager.is_authorized(event.sender_id)
                if self.access_manager
                else event.sender_id == self.config.authorized_user_id
            )

            # Allow 'req:' callbacks for unauthorized users (e.g. req:access)
            if not is_auth and not data.startswith("req:"):
                await event.answer("Access denied.", alert=True)
                return

            if self._callback_router:
                try:
                    await self._callback_router(event)
                except Exception as e:
                    logger.error(f"Error handling callback: {e}", exc_info=True)
                    await event.answer("⚠️ Error processing request.", alert=True)

    async def send_message(self, chat_id: int, text: str, **kwargs) -> Message:
        """Send a message to the user."""
        return await self.client.send_message(chat_id, text, **kwargs)

    async def edit_message(self, message: Message, text: str, **kwargs) -> Message:
        """Edit an existing message (e.g. for throttled progress)."""
        return await self.client.edit_message(message, text, **kwargs)

    async def forward_media(
        self, to_peer: int, from_peer: int, message_ids: list[int]
    ) -> list[Message]:
        """
        Forward messages from a channel/peer directly to the target peer (user DM).
        """
        return await self.client.forward_messages(
            entity=to_peer,
            messages=message_ids,
            from_peer=from_peer,
        )

    async def disconnect(self) -> None:
        """Disconnect the bot client."""
        if self.client.is_connected():
            await self.client.disconnect()
