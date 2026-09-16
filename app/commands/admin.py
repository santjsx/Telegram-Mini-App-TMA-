"""
Administrative command handlers (/reindex, /users, /revoke)
and in-app access request & approval workflows.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional
from telethon import Button, events
from telethon.tl.custom.message import Message

from app.commands.start import get_main_menu_keyboard

if TYPE_CHECKING:
    from app.index.indexer import MusicIndexer
    from app.telegram.user_client import UserClientManager
    from app.telegram.bot import BotManager
    from app.config import Config
    from app.auth.manager import AccessManager

logger = logging.getLogger(__name__)


class AdminCommandHandler:
    def __init__(
        self,
        indexer: MusicIndexer,
        user_client: UserClientManager,
        config: Config,
        access_manager: Optional[AccessManager] = None,
        bot_manager: Optional[BotManager] = None,
    ) -> None:
        self.indexer = indexer
        self.user_client = user_client
        self.config = config
        self.access_manager = access_manager
        self.bot_manager = bot_manager

    async def handle_reindex(self, message: Message) -> None:
        """Rescan music storage channel to refresh metadata index."""
        text = message.text.strip()
        parts = text.split()
        is_confirmed = len(parts) > 1 and parts[1].lower() == "confirm"

        if not is_confirmed:
            await message.reply(
                "⚠️ **Re-index Confirmation Required**\n\n"
                "This will rescan your private Telegram channel to rebuild your music index.\n\n"
                "To confirm and begin, send:\n"
                "`/reindex confirm`"
            )
            return

        await self.indexer.start_indexing(
            user_client=self.user_client,
            channel_id=self.config.channel_id,
            reset=True,
        )
        await message.reply(
            "🔄 **Full Library Re-index Started!**\n\n"
            "The channel scan is now running in the background.\n"
            "Use `/status` to track progress."
        )

    async def handle_users(self, message: Message) -> None:
        """List all currently authorized users with one-tap revoke buttons."""
        if not self.access_manager:
            await message.reply("Access manager is not initialized.")
            return

        approved = self.access_manager.get_all_approved()
        pending = self.access_manager.get_all_pending()

        lines = [
            f"👥 **Access Control & Users ({len(approved) + 1})**\n",
            f"👑 **Owner & Super Admin:**\n• ID: `{self.config.authorized_user_id}`\n",
        ]

        buttons = []

        if approved:
            lines.append(f"**Approved Members ({len(approved)}):**")
            for idx, u in enumerate(approved, 1):
                date_str = u.approved_at[:10] if u.approved_at else "Active"
                lines.append(f"{idx}. **{u.display_name}** ({u.mention}) — `{u.user_id}` (_{date_str}_)")
                # Revoke button
                btn_label = f"🚫 Revoke {u.first_name or u.user_id}"[:25]
                buttons.append([Button.inline(btn_label, data=f"auth:rev:{u.user_id}".encode("utf-8"))])
            lines.append("")
        else:
            lines.append("ℹ️ *No additional users have been approved yet.*")
            lines.append("*When friends message the bot, their access requests will appear here!*\n")

        if pending:
            lines.append(f"⏳ **Pending Requests ({len(pending)}):**")
            for req in pending:
                lines.append(f"• **{req.display_name}** ({req.mention}) — `{req.user_id}`")
                buttons.append([
                    Button.inline(f"✅ Approve {req.first_name or req.user_id}"[:20], data=f"auth:app:{req.user_id}".encode("utf-8")),
                    Button.inline(f"❌ Deny", data=f"auth:den:{req.user_id}".encode("utf-8")),
                ])
            lines.append("")

        await message.reply("\n".join(lines), buttons=buttons if buttons else None)

    async def handle_revoke(self, message: Message) -> None:
        """Handle /revoke <user_id> command."""
        if not self.access_manager:
            return

        parts = (message.text or "").strip().split()
        if len(parts) < 2:
            await message.reply("Usage: `/revoke <user_id>`\nOr use `/users` to manage with buttons.")
            return

        try:
            target_id = int(parts[1])
        except ValueError:
            await message.reply("Invalid user ID. Must be an integer.")
            return

        if target_id == self.config.authorized_user_id:
            await message.reply("⚠️ Cannot revoke Super Admin.")
            return

        success = await self.access_manager.revoke_user(target_id)
        if success:
            await message.reply(f"🚫 Revoked access for user `{target_id}`.")
            if self.bot_manager:
                try:
                    await self.bot_manager.send_message(
                        target_id,
                        "🔒 **Access Revoked**\n\n"
                        "Your access to this music cloud has been revoked by the administrator."
                    )
                except Exception as e:
                    logger.warning(f"Could not send revocation notice to {target_id}: {e}")
        else:
            await message.reply(f"User `{target_id}` is not in the approved list.")

    async def handle_unauthorized_message(self, message: Message) -> None:
        """Prompt unauthorized users to request access."""
        if not self.access_manager:
            await message.reply("Access denied.")
            return

        sender_id = message.sender_id
        if self.access_manager.is_pending(sender_id):
            await message.reply(
                "⏳ **Access Request Pending**\n\n"
                "Your request has already been submitted to the administrator and is waiting for review.\n\n"
                "You will automatically receive a message here the moment your access is approved!"
            )
            return

        buttons = [[Button.inline("🙋 Request Access", data=b"req:access")]]
        await message.reply(
            "🔒 **Private Music Cloud**\n\n"
            "Welcome! This music library is private and invite-only.\n\n"
            "Tap the button below to request access from the owner to stream and download music.",
            buttons=buttons,
        )

    async def handle_request_access_callback(self, event: events.CallbackQuery.Event) -> None:
        """Handle unauthorized user tapping 'Request Access'."""
        if not self.access_manager:
            await event.answer("Access control unavailable.", alert=True)
            return

        sender_id = event.sender_id

        if self.access_manager.is_authorized(sender_id):
            await event.answer("You already have access! Tap /start to begin.", alert=True)
            return

        if self.access_manager.is_pending(sender_id):
            await event.answer("Your request is already pending review by the admin.", alert=True)
            return

        sender = await event.get_sender()
        first_name = getattr(sender, "first_name", "") or ""
        last_name = getattr(sender, "last_name", "") or ""
        username = getattr(sender, "username", None)

        is_new, req = await self.access_manager.add_request(
            user_id=sender_id,
            first_name=first_name,
            last_name=last_name,
            username=username,
        )

        await event.edit(
            "⏳ **Access Request Submitted!**\n\n"
            "Your request has been forwarded to the administrator.\n"
            "You will be notified here as soon as your access is approved. Thank you for your patience!"
        )
        await event.answer("Request submitted successfully!")

        # Alert the Super Admin
        if self.bot_manager:
            full_name = f"{first_name} {last_name}".strip() or f"User {sender_id}"
            username_str = f"@{username}" if username else "*None*"

            admin_card = (
                "🔔 **New Access Request**\n\n"
                f"• **User:** {full_name}\n"
                f"• **Username:** {username_str}\n"
                f"• **User ID:** `{sender_id}`\n\n"
                "Grant this user access to search, stream, and play music?"
            )
            admin_buttons = [
                [
                    Button.inline("✅ Approve Access", data=f"auth:app:{sender_id}".encode("utf-8")),
                    Button.inline("❌ Deny", data=f"auth:den:{sender_id}".encode("utf-8")),
                ]
            ]
            try:
                await self.bot_manager.send_message(
                    self.config.authorized_user_id, admin_card, buttons=admin_buttons
                )
            except Exception as e:
                logger.error(f"Failed to notify admin of access request: {e}")

    async def handle_auth_callback(self, event: events.CallbackQuery.Event) -> None:
        """Handle admin approval, denial, or revocation callbacks (auth:app, auth:den, auth:rev)."""
        if not self.access_manager:
            await event.answer("Access control unavailable.", alert=True)
            return

        # Strictly enforce admin-only callback execution
        if event.sender_id != self.config.authorized_user_id:
            await event.answer("Unauthorized action.", alert=True)
            return

        data = event.data.decode("utf-8")
        parts = data.split(":")
        if len(parts) < 3:
            await event.answer("Invalid action.", alert=True)
            return

        action, target_id_str = parts[1], parts[2]
        try:
            target_id = int(target_id_str)
        except ValueError:
            await event.answer("Invalid user ID.", alert=True)
            return

        if action == "app":
            # Approve User
            user = await self.access_manager.approve_user(target_id, approved_by=event.sender_id)
            if user:
                await event.edit(
                    f"✅ **Access Granted**\n\n"
                    f"• **User:** {user.display_name} ({user.mention})\n"
                    f"• **User ID:** `{user.user_id}`\n"
                    f"• **Status:** Approved by Admin\n\n"
                    f"💡 *User has been notified and can now search and stream music.*",
                    buttons=[[Button.inline("🚫 Revoke Access", data=f"auth:rev:{user.user_id}".encode("utf-8"))]],
                )
                await event.answer("User approved!")

                # Send welcome onboarding message to the approved user
                if self.bot_manager:
                    welcome_msg = (
                        "🎉 **Access Granted!**\n\n"
                        "The administrator has approved your access to **Telegram Personal Music Cloud (TPMC)**.\n\n"
                        "You can now search, browse albums and artists, and stream high-quality music directly in this chat!\n\n"
                        "Tap **[ 🔍 Search Music ]** or type any song title below to start listening!"
                    )
                    try:
                        await self.bot_manager.send_message(
                            target_id, welcome_msg, buttons=get_main_menu_keyboard()
                        )
                    except Exception as e:
                        logger.warning(f"Could not send welcome message to newly approved user {target_id}: {e}")
            else:
                await event.answer("User already approved or not found.", alert=True)

        elif action == "den":
            # Deny Request
            req = await self.access_manager.deny_user(target_id)
            await event.edit(
                f"❌ **Request Denied**\n\n"
                f"• **User ID:** `{target_id}`\n"
                f"• **Status:** Denied by Admin",
                buttons=[[Button.inline("✅ Approve Instead", data=f"auth:app:{target_id}".encode("utf-8"))]],
            )
            await event.answer("Request denied.")

            # Notify user politely
            if self.bot_manager:
                try:
                    await self.bot_manager.send_message(
                        target_id,
                        "🚫 **Access Request Declined**\n\n"
                        "Sorry, your request to access this private music cloud was declined by the administrator."
                    )
                except Exception as e:
                    logger.warning(f"Could not notify denied user {target_id}: {e}")

        elif action == "rev":
            # Revoke User
            if target_id == self.config.authorized_user_id:
                await event.answer("Cannot revoke Super Admin.", alert=True)
                return

            success = await self.access_manager.revoke_user(target_id)
            if success:
                await event.edit(
                    f"🚫 **Access Revoked**\n\n"
                    f"User `{target_id}` has been removed from authorized users.",
                    buttons=[[Button.inline("✅ Re-Approve", data=f"auth:app:{target_id}".encode("utf-8"))]],
                )
                await event.answer("User access revoked.")

                # Notify user
                if self.bot_manager:
                    try:
                        await self.bot_manager.send_message(
                            target_id,
                            "🔒 **Access Revoked**\n\n"
                            "Your access to this music library has been revoked by the administrator."
                        )
                    except Exception as e:
                        logger.warning(f"Could not notify revoked user {target_id}: {e}")
            else:
                await event.answer("User was not in approved list.", alert=True)
