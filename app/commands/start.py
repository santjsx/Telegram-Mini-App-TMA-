"""
Start, Help, and Web Player command handlers.
"""

from __future__ import annotations

from typing import Optional
from telethon import Button
from telethon.tl import types
from telethon.tl.custom.message import Message


def get_main_menu_keyboard():
    return [
        [Button.text("🎵 Web Player"), Button.text("🔍 Search Songs & Albums")],
        [Button.text("💿 Browse Albums"), Button.text("🎵 All Songs")],
        [Button.text("📁 File Explorer"), Button.text("⭐ Favorites")],
        [Button.text("🎲 Surprise Pick"), Button.text("⚡ Cloud Status")],
    ]


def get_webapp_button(url: str, label: str = "🚀 Launch Web Player 🎧"):
    """
    Creates an inline web app button.
    If the URL starts with https://, creates an InlineButtonTypeWebView for native Telegram Mini App overlay.
    Otherwise, creates standard Button.url.
    """
    if url.startswith("https://"):
        try:
            return types.KeyboardInlineButton(
                text=label,
                type=types.InlineButtonTypeWebView(url=url),
            )
        except Exception:
            return Button.url(label, url)
    return Button.url(label, url)


def get_start_message(admin_name: str = "Santhosh Reddy") -> str:
    return (
        "╔══════════════════════════════════════════╗\n"
        "   🎧 ✦ **My Music Cloud • High-Fidelity Streaming (TPMC)** ✦ 🎧\n"
        "╚══════════════════════════════════════════╝\n\n"
        f"Welcome back! Your personal music sanctuary curated by **{admin_name}** is online and ready for playback.\n\n"
        "⚡ **Quick Action Matrix:**\n"
        "┌ 🚀 **Web Player:** Tap `🎵 Web Player` for full waveform visuals & seeking\n"
        "├ 🔍 **Instant Search:** Type any song title or artist directly in this chat\n"
        "├ 💿 **Album Vault:** Browse discographies with high-res cover artwork\n"
        "├ 📁 **File Explorer:** Drill down through albums, genres, and A–Z index\n"
        "└ 🎲 **Surprise Pick:** Get an instant curated track recommendation\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *Navigate using the touch keyboard below or type `/albums`, `/songs`, or `/library` anytime.*"
    )


START_MESSAGE = get_start_message("Santhosh Reddy")

HELP_MESSAGE = """╔══════════════════════════════════════════╗
   📖 ✦ **Music Cloud Command & Tagging Guide** ✦ 📖
╚══════════════════════════════════════════╝

✨ **Instant Natural Search:**
• Type any song title, artist, or album directly into chat for instant 1-tap playback!
• Examples: `blinding lights`, `coldplay`, `starboy`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎛️ **Primary Audio Commands:**
• `/player` — Launch luxury Web Player Mini App with waveform visualizer
• `/albums` — Browse all indexed albums with high-res cover art
• `/songs` — List all tracks in your cloud library alphabetically
• `/album <name>` — Directly open a specific album's tracklist
• `/search <query>` — Multi-attribute search (title, artist, album, genre)
• `/explore` — Open hierarchical file manager & A-Z alphabet jump
• `/random` — Instant surprise track recommendation
• `/status` — View cloud connection, index state, and metrics

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏷️ **Tag-Based Filtering:**
• `/search #rock` — Filter tracks tagged with `#rock`
• `/search #favorite` — View your starred favorite tracks
• `/download #<genre>` — Batch deliver all songs matching a genre tag

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 *Tip: Use the permanent keyboard buttons below for 1-tap touch navigation.*
"""


async def handle_start(
    message: Message, webapp_url: Optional[str] = None, admin_name: str = "Santhosh Reddy"
) -> None:
    await message.reply(get_start_message(admin_name), buttons=get_main_menu_keyboard())
    if webapp_url:
        card = (
            "🎧 ✦ **Studio Web Player Available** ✦ 🎧\n\n"
            "Full album artwork, 32-band live reactive audio visualizer, and instant seeking.\n\n"
            f"🔗 Direct Link: `{webapp_url}`\n\n"
            "👇 *Tap below to launch your streaming deck:*"
        )
        is_public = webapp_url.startswith("https://") or (
            webapp_url.startswith("http://")
            and "localhost" not in webapp_url
            and "127.0.0.1" not in webapp_url
        )
        if is_public:
            try:
                await message.reply(
                    card,
                    buttons=[[get_webapp_button(webapp_url, "🚀 Launch Web Player Mini App 🎧")]],
                )
                return
            except Exception:
                pass
        await message.reply(card)


async def handle_help(message: Message) -> None:
    await message.reply(HELP_MESSAGE, buttons=get_main_menu_keyboard())


async def handle_player(
    message: Message, webapp_url: Optional[str] = None, admin_name: str = "Santhosh Reddy"
) -> None:
    target_url = webapp_url or "http://localhost:8080"
    card = (
        "╔══════════════════════════════════════════╗\n"
        "   🎧 ✦ 𝗟𝗨𝗫𝗨𝗥𝗬 𝗪𝗘𝗕 𝗣𝗟𝗔𝗬𝗘𝗥 ✦ 🎧\n"
        "      Telegram Mini App • Studio Edition\n"
        "╚══════════════════════════════════════════╝\n\n"
        f"Your private streaming sanctuary curated by **{admin_name}** is online.\n\n"
        "✨ **Studio Highlights:**\n"
        "◈ 🎚️ **32-Bar Real-Time Visualizer:** Live reactive audio spectrum\n"
        "◈ 💽 **Concentric Radial Vinyl Deck:** Analog vinyl rotation animation\n"
        "◈ ⚡ **Instant Lossless Streaming:** Partial byte-range seeking\n"
        "◈ 🎨 **Dynamic Canvas Art:** Full-resolution cover art & metadata\n"
        "◈ ⏱️ **Pro Controls:** Sleep timer, shuffle, repeat, & audio badges\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 **Direct URL:** `{target_url}`"
    )
    is_public = target_url.startswith("https://") or (
        target_url.startswith("http://")
        and "localhost" not in target_url
        and "127.0.0.1" not in target_url
    )
    if is_public:
        try:
            await message.reply(
                card + "\n\n👇 *Tap below to launch your Web Player experience:*",
                buttons=[[get_webapp_button(target_url, "🚀 Launch Web Player Mini App 🎧")]],
            )
            return
        except Exception:
            pass
    await message.reply(card)
