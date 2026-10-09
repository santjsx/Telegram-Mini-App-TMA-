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
        "🚀 **Introducing My Music Cloud (TPMC) on Telegram!** 🎧\n\n"
        f"Welcome! Your personal high-fidelity music sanctuary curated by **{admin_name}** is online and ready for playback. Enjoy studio-grade sound and features like:\n\n"
        "- 💎 Lossless FLAC & 320kbps MP3 audio\n"
        "- 🚀 Studio Web Player with live 32-band visualizer\n"
        "- 💿 Full album vaults with high-res cover artwork\n"
        "- 📥 Instant 1-tap download & file inspector\n\n"
        "🔎 **How it works:**\n"
        "1️⃣ Send any song title, artist, or album to the bot.\n"
        "2️⃣ Get instant playback, lyrics, artwork, and audio files!\n\n"
        "It's fast, simple, and lossless! Try it now. 💡\n\n"
        "👉 *Navigate using the menu below or explore* `/library`, `/albums`, *and* `/songs`."
    )


START_MESSAGE = get_start_message("Santhosh Reddy")

HELP_MESSAGE = """📖 **Music Cloud Command & Tagging Guide** 🎧

Everything you need to navigate and control your personal audio library:

🔎 **Instant Natural Search:**
Send any song title, artist, or album directly to the chat for instant 1-tap playback!
- Examples: `blinding lights`, `coldplay`, `starboy`

🎛️ **Audio Commands:**
- `/player` — Launch Studio Web Player with waveform visualizer
- `/albums` — Browse all indexed albums with high-res artwork
- `/songs` — List all tracks in your library alphabetically
- `/album <name>` — Directly open a specific album's tracklist
- `/search <query>` — Multi-attribute search (title, artist, album, genre)
- `/explore` — Open hierarchical file manager & A–Z alphabet jump
- `/random` — Instant surprise track recommendation
- `/status` — View cloud connection and audio metrics

🏷️ **Tag-Based Filtering:**
- `/search #rock` — Filter tracks tagged with `#rock`
- `/search #favorite` — View your starred favorite tracks
- `/download #<genre>` — Batch deliver all songs matching a genre

It's fast, simple, and organized! 💡
Tap the menu buttons below anytime for 1-tap navigation."""


async def handle_start(
    message: Message, webapp_url: Optional[str] = None, admin_name: str = "Santhosh Reddy"
) -> None:
    await message.reply(get_start_message(admin_name), buttons=get_main_menu_keyboard())
    if webapp_url:
        card = (
            "🎧 **Studio Web Player Available** 🚀\n\n"
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
        "🚀 **Studio Web Player is Live!** 🎧\n"
        "Telegram Mini App · High-Fidelity Edition\n\n"
        f"Your private streaming sanctuary curated by **{admin_name}** is online and ready for playback.\n\n"
        "✨ **Studio Highlights:**\n"
        "- 🎚️ **32-Bar Real-Time Visualizer:** Live reactive audio spectrum\n"
        "- 💽 **Analog Vinyl Rotation Deck:** Smooth vinyl animation\n"
        "- ⚡ **Instant Lossless Streaming:** Partial byte-range seeking\n"
        "- 🎨 **Dynamic Canvas Art:** Full-resolution cover artwork\n"
        "- ⏱️ **Pro Controls:** Sleep timer, shuffle, repeat, & audio badges\n\n"
        "🔎 **How to use:**\n"
        "1️⃣ Tap the button below to launch the Mini App.\n"
        "2️⃣ Enjoy smooth, seamless playback directly in Telegram!\n\n"
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
