"""
Telegram Bot Artwork Delivery & View Helper.
Formats and dispatches album cover artwork photo cards with captions and interactive inline buttons.
"""

from __future__ import annotations

import inspect
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional
from telethon import events
from telethon.tl.custom.message import Message

logger = logging.getLogger(__name__)

# Telegram limits media captions to 1024 characters
MAX_CAPTION_LENGTH = 1024


async def _maybe_await(val: Any) -> Any:
    """Helper to safely await an object only if it is awaitable (supports coroutines, tasks, and AsyncMocks)."""
    if inspect.isawaitable(val):
        return await val
    return val


async def send_or_edit_artwork(
    target: Any,
    text: str,
    buttons: Any = None,
    artwork_path: Optional[Path] = None,
) -> None:
    """
    Sends or edits a Telegram message with album artwork attached as a photo if available.
    Ensures captions respect Telegram's 1024-character media limit and falls back gracefully
    to text-only display if artwork is not found or media dispatch fails.
    """
    caption = text
    if artwork_path and artwork_path.exists():
        if len(caption) > MAX_CAPTION_LENGTH:
            caption = caption[: MAX_CAPTION_LENGTH - 4] + "..."

    # 1. Callback Query Event handling (Telethon CallbackQuery or test mock event with byte data)
    is_callback = isinstance(target, events.CallbackQuery.Event) or isinstance(getattr(target, "data", None), (bytes, bytearray))
    if is_callback:
        if artwork_path and artwork_path.exists():
            msg = getattr(target, "message", None)
            has_media = bool(msg and getattr(msg, "media", None))
            if has_media:
                # Existing message already has media, edit media in-place
                try:
                    res = target.edit(caption, file=str(artwork_path), buttons=buttons)
                    await _maybe_await(res)
                    if hasattr(target, "answer"):
                        await _maybe_await(target.answer())
                    return
                except Exception as e:
                    logger.debug(f"Media edit failed, attempting respond fallback: {e}")

            # If original message was text-only or edit failed, send new photo message and clean up prompt
            if hasattr(target, "respond"):
                try:
                    res = target.respond(caption, file=str(artwork_path), buttons=buttons)
                    await _maybe_await(res)
                    if hasattr(target, "delete"):
                        try:
                            await _maybe_await(target.delete())
                        except Exception:
                            pass
                    if hasattr(target, "answer"):
                        await _maybe_await(target.answer())
                    return
                except Exception as e:
                    logger.debug(f"Media respond failed, falling back to text edit: {e}")

        # Fallback to standard text edit
        try:
            res = target.edit(text, buttons=buttons)
            await _maybe_await(res)
        except Exception as e:
            logger.debug(f"Callback text edit failed: {e}")
        if hasattr(target, "answer"):
            try:
                await _maybe_await(target.answer())
            except Exception:
                pass
        return

    # 2. Message object handling (e.g. from slash command or typed query)
    if hasattr(target, "reply"):
        if artwork_path and artwork_path.exists():
            try:
                res = target.reply(caption, file=str(artwork_path), buttons=buttons)
                await _maybe_await(res)
                return
            except Exception as e:
                logger.debug(f"Media reply failed, falling back to text reply: {e}")

        res = target.reply(text, buttons=buttons)
        await _maybe_await(res)
