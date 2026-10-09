"""
Administrative command handlers (/reindex, /users, /revoke)
and in-app access request & approval workflows.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional
from telethon import Button, events
from telethon.tl.custom.message import Message

from app.commands.start import get_main_menu_keyboard, get_webapp_button

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
                "⚠️ **Re-index Confirmation Required** 🔄\n\n"
                "This action will rescan your private Telegram channel and rebuild your music cloud metadata index from scratch.\n\n"
                "To confirm and begin, send:\n"
                "`/reindex confirm` ⚡"
            )
            return

        await self.indexer.start_indexing(
            user_client=self.user_client,
            channel_id=self.config.channel_id,
            reset=True,
        )
        await message.reply(
            "🔄 **Full Library Re-index Started!** 🚀\n\n"
            "The channel catalog scan is now actively running in the background!\n\n"
            "📊 *Track live progress anytime using* `/status`"
        )

    async def handle_users(self, message: Message) -> None:
        """List all currently authorized users with one-tap revoke buttons."""
        if not self.access_manager:
            await message.reply("Access manager is not initialized.")
            return

        admin_name = getattr(self.config, "admin_name", "Santhosh Reddy")
        approved = self.access_manager.get_all_approved()
        pending = self.access_manager.get_all_pending()
        total_members = len(approved) + 1

        lines = [
            f"👥 **Access Control & Users** 🛡️ ({total_members} Members)\n",
            "👑 **Owner & Super Admin:**",
            f"- **Curator:** {admin_name}",
            f"- **Telegram ID:** `{self.config.authorized_user_id}`\n",
        ]

        buttons = []

        if approved:
            lines.append(f"🟢 **Approved VIP Members ({len(approved)}):**")
            for idx, u in enumerate(approved, 1):
                date_str = u.approved_at[:10] if u.approved_at else "Active"
                lines.append(f"{idx}. **{u.display_name}** ({u.mention}) — `{u.user_id}` (_{date_str}_)")
                btn_label = f"🚫 Revoke {u.first_name or u.user_id}"[:25]
                buttons.append([Button.inline(btn_label, data=f"auth:rev:{u.user_id}".encode("utf-8"))])
            lines.append("")
        else:
            lines.append("ℹ️ *No external VIP members approved yet.*")
            lines.append("💡 *When visitors request access, approval alerts will appear here!*\n")

        if pending:
            lines.append(f"⏳ **Pending Review Queue ({len(pending)}):**")
            for req in pending:
                lines.append(f"• **{req.display_name}** ({req.mention}) — `{req.user_id}`")
                buttons.append([
                    Button.inline(f"✅ Grant {req.first_name or req.user_id}"[:20], data=f"auth:app:{req.user_id}".encode("utf-8")),
                    Button.inline("🚫 Decline", data=f"auth:den:{req.user_id}".encode("utf-8")),
                ])
            lines.append("")

        await message.reply("\n".join(lines), buttons=buttons if buttons else None)

    async def handle_revoke(self, message: Message) -> None:
        """Handle /revoke <user_id> command."""
        if not self.access_manager:
            return

        admin_name = getattr(self.config, "admin_name", "Santhosh Reddy")
        parts = (message.text or "").strip().split()
        if len(parts) < 2:
            await message.reply("Usage: `/revoke <user_id>`\nOr use `/users` for interactive management.")
            return

        try:
            target_id = int(parts[1])
        except ValueError:
            await message.reply("⚠️ Invalid user ID. Must be a numeric Telegram ID.")
            return

        if target_id == self.config.authorized_user_id:
            await message.reply("⚠️ Cannot revoke the Super Admin.")
            return

        success = await self.access_manager.revoke_user(target_id)
        if success:
            await message.reply(
                f"🚫 **Access Revoked**\n\n"
                f"User `{target_id}` has been removed from authorized VIP members."
            )
            if self.bot_manager:
                try:
                    await self.bot_manager.send_message(
                        target_id,
                        "🔒 **Access Revoked** 🚫\n\n"
                        f"Your VIP access to **My Music Cloud** has been revoked by **{admin_name}**.\n\n"
                        f"If you believe this was done in error, please contact {admin_name} directly."
                    )
                except Exception as e:
                    logger.warning(f"Could not send revocation notice to {target_id}: {e}")
        else:
            await message.reply(f"ℹ️ User `{target_id}` is not currently in the approved list.")

    async def handle_unauthorized_message(self, message: Message) -> None:
        """Prompt unauthorized users to request access."""
        if not self.access_manager:
            await message.reply("Access denied.")
            return

        admin_name = getattr(self.config, "admin_name", "Santhosh Reddy")
        sender_id = message.sender_id

        if self.access_manager.is_pending(sender_id):
            await message.reply(
                "⏳ **Access Request Pending** 🕒\n\n"
                f"Your VIP access request has already been submitted to **{admin_name}** and is currently awaiting review.\n\n"
                "📋 **Status:** `Pending Verification ⏳`\n"
                "🔔 **Notification:** You will automatically receive a message here the moment your access pass is approved!\n\n"
                "Thank you for your patience! Exceptional music is on the way. ✨"
            )
            return

        buttons = [[Button.inline("✨ Request VIP Access 🎟️", data=b"req:access")]]
        await message.reply(
            "🎧 **Welcome to My Music Cloud!** 🚀\n"
            "Private VIP Audio Sanctuary\n\n"
            f"Greetings! You have arrived at an exclusive, private high-fidelity music streaming cloud curated by **{admin_name}**.\n\n"
            "🔒 **Access Policy:** `Private Music Cloud • Invite-Only`\n"
            f"👑 **Curator & Admin:** {admin_name}\n\n"
            "✨ **Inside the Cloud:**\n"
            "- 💎 **Lossless Streaming:** Studio-grade FLAC & 320kbps MP3s\n"
            "- 🚀 **Web Player Mini App:** 32-band reactive visualizer & vinyl deck\n"
            "- 📥 **Instant Telegram Delivery:** 1-tap download straight to this chat\n"
            "- 🔎 **Smart Search:** Fuzzy query by song, artist, album, or genre\n\n"
            "🔎 **How to join:**\n"
            "1️⃣ Tap the button below to submit a VIP access request.\n"
            "2️⃣ Once approved, you'll unlock the entire music sanctuary!\n\n"
            "It's fast and simple! Tap below to request access: 💡",
            buttons=buttons,
        )

    async def handle_request_access_callback(self, event: events.CallbackQuery.Event) -> None:
        """Handle unauthorized user tapping 'Request Access'."""
        if not self.access_manager:
            await event.answer("Access control unavailable.", alert=True)
            return

        admin_name = getattr(self.config, "admin_name", "Santhosh Reddy")
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
            "⏳ **Access Request Submitted!** 🚀\n\n"
            f"Your VIP access application has been forwarded directly to **{admin_name}** for review!\n\n"
            "📋 **Application Status:** `Pending Verification ⏳`\n"
            "🔔 **Notification:** You will receive a direct notification and welcome pack the moment your access is approved.\n\n"
            "Sit tight — exceptional music is worth waiting for! ✨"
        )
        await event.answer("Request submitted successfully!")

        # Alert the Super Admin
        if self.bot_manager:
            full_name = f"{first_name} {last_name}".strip() or f"User {sender_id}"
            username_str = f"@{username}" if username else "*None*"

            admin_card = (
                "🔔 **New VIP Access Request!** 🎟️\n\n"
                "A listener is knocking on your music cloud doors!\n\n"
                "👤 **User Details:**\n"
                f"- **Name:** {full_name}\n"
                f"- **Username:** {username_str}\n"
                f"- **User ID:** `{sender_id}`\n"
                "- **Status:** `Waiting for Approval ⏳`\n\n"
                "Grant this user access to search, stream, and download your cloud library?"
            )
            admin_buttons = [
                [
                    Button.inline("✅ Grant VIP Access 🎧", data=f"auth:app:{sender_id}".encode("utf-8")),
                    Button.inline("🚫 Decline Request", data=f"auth:den:{sender_id}".encode("utf-8")),
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

        admin_name = getattr(self.config, "admin_name", "Santhosh Reddy")
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
                    "✨ **Access Granted!** 🎧\n\n"
                    f"- **Member:** {user.display_name} ({user.mention})\n"
                    f"- **User ID:** `{user.user_id}`\n"
                    "- **Access Level:** `Authorized VIP Listener 🟢`\n"
                    f"- **Approved by:** {admin_name}\n\n"
                    "🎉 *Onboarding welcome pack delivered to the listener!*",
                    buttons=[[Button.inline("🚫 Revoke Access", data=f"auth:rev:{user.user_id}".encode("utf-8"))]],
                )
                await event.answer("User approved!")

                # Send welcome onboarding message to the approved user
                if self.bot_manager:
                    welcome_msg = (
                        "🎉 **Access Granted • Welcome to My Music Cloud!** 🚀\n\n"
                        f"Your VIP listening pass has been approved by **{admin_name}**!\n\n"
                        "You now have full access to stream lossless audio, explore curated discographies, and download studio tracks directly inside Telegram.\n\n"
                        "✨ **What you can do:**\n"
                        "- 🚀 **Web Player:** Tap `🎵 Web Player` below for live waveform visualizers & instant seeking!\n"
                        "- 🔎 **Instant Search:** Type any track, artist, or album name directly in chat.\n"
                        "- 💿 **Browse Albums:** Explore full collections with high-res cover art.\n"
                        "- 📁 **File Explorer:** Drill down by genre, recent drops, or A-Z alphabet jump.\n"
                        "- ⭐ **Starred Tracks:** Tap `⭐ Favorites` to listen to top curated songs.\n\n"
                        "🔎 **How to start:**\n"
                        "1️⃣ Type any song title or artist directly in this chat.\n"
                        "2️⃣ Or tap any button below to launch the experience!\n\n"
                        "It's fast, simple, and lossless! Enjoy the music. 💡"
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
                "🚫 **Request Declined**\n\n"
                f"- **User ID:** `{target_id}`\n"
                f"- **Decision:** Rejected by {admin_name}\n"
                "- **Status:** `Access Denied 🔴`",
                buttons=[[Button.inline("✅ Change Mind & Approve 🎧", data=f"auth:app:{target_id}".encode("utf-8"))]],
            )
            await event.answer("Request denied.")

            # Notify user politely
            if self.bot_manager:
                try:
                    await self.bot_manager.send_message(
                        target_id,
                        "🔒 **Access Request Declined**\n\n"
                        "Thank you for your interest in **My Music Cloud**.\n\n"
                        f"At this time, your access request could not be approved by **{admin_name}**. "
                        "This private music cloud remains strictly limited to authorized personal contacts.\n\n"
                        "Thank you for understanding! ✨"
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
                    "🚫 **Access Revoked**\n\n"
                    f"User `{target_id}` has been removed from authorized VIP members.",
                    buttons=[[Button.inline("✅ Re-Authorize User 🎧", data=f"auth:app:{target_id}".encode("utf-8"))]],
                )
                await event.answer("User access revoked.")

                # Notify user
                if self.bot_manager:
                    try:
                        await self.bot_manager.send_message(
                            target_id,
                            "🔒 **Access Revoked** 🚫\n\n"
                            f"Your VIP access to **My Music Cloud** has been revoked by **{admin_name}**.\n\n"
                            f"If you believe this was done in error, please contact {admin_name} directly."
                        )
                    except Exception as e:
                        logger.warning(f"Could not notify revoked user {target_id}: {e}")
            else:
                await event.answer("User was not in approved list.", alert=True)
