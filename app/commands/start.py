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


START_MESSAGE = """🎵 **Music Cloud • High-Fidelity Streaming (TPMC)**

Welcome to your private cloud music sanctuary. Stream lossless audio, browse albums with cover art, and take your music anywhere.

🎧 **Web Player Mini App:**
Tap `🎵 Web Player` below or use the button to launch your luxury dark-mode streaming studio with real-time waveform visualizers and instant seeking!

✨ **Quick Navigation:**
• **Browse Albums:** Tap `💿 Browse Albums` to view collections with high-res cover art.
• **All Songs:** Tap `🎵 All Songs` to list all tracks with quick audio delivery.
• **Instant Search:** Type any song or album name directly into the chat!
• **Surprise Pick:** Tap `🎲 Surprise Pick` for an instant curated track pick.

💡 *Use the permanent menu buttons below or type `/albums`, `/songs`, or `/library` anytime.*
"""

HELP_MESSAGE = """📖 **Music Cloud Command & Tagging Guide**

**Touch Navigation:**
• Use the permanent menu buttons at the bottom of your screen for one-tap access.
• Type any song title or album name anytime for instant fuzzy search.

**Search & Playback Commands:**
• `/player` — Open the luxury Web App streaming player
• `/albums` — Browse all albums with track counts and cover art
• `/songs` — View all songs indexed in your cloud (A-Z)
• `/album <name>` — Directly open an album's tracklist and cover art
• `/search <title>` — Search songs across your library
• `/search album:<name>` — Filter specifically by album name
• `/download #<genre>` — Deliver all songs in a genre (e.g. `/download #rock`)
• `/library` — Open interactive albums and songs dashboard
• `/status` — View cloud connection & index status

**Channel Tagging Standard:**
When adding new songs to your storage channel:
`#album:Album_Name #genre:Genre #favorite`
"""


async def handle_start(message: Message, webapp_url: Optional[str] = None) -> None:
    await message.reply(START_MESSAGE, buttons=get_main_menu_keyboard())
    if webapp_url:
        card = (
            "🎧 **Experience Your Music in Web Player**\n\n"
            "Full album artwork, 32-band audio reactive visualizer, and instant seeking.\n\n"
            f"🔗 Direct Link: `{webapp_url}`\n\n"
            "👇 *Tap below to launch:* "
        )
        is_public = webapp_url.startswith("https://") or (webapp_url.startswith("http://") and "localhost" not in webapp_url and "127.0.0.1" not in webapp_url)
        if is_public:
            try:
                await message.reply(card, buttons=[[get_webapp_button(webapp_url)]])
                return
            except Exception:
                pass
        await message.reply(card)


async def handle_help(message: Message) -> None:
    await message.reply(HELP_MESSAGE, buttons=get_main_menu_keyboard())


async def handle_player(message: Message, webapp_url: Optional[str] = None) -> None:
    target_url = webapp_url or "http://localhost:8080"
    card = (
        "🎧 **Telegram Mini App • Luxury Web Player**\n\n"
        "Your private streaming studio is online.\n\n"
        "✨ **Highlights:**\n"
        "• 32-Bar Real-Time Audio Visualizer\n"
        "• Concentric Radial Vinyl Deck\n"
        "• Instant Byte-Range Partial Audio Streaming\n"
        "• High-Resolution Artwork & Media Session Controls\n\n"
        f"🔗 Direct Link: `{target_url}`"
    )
    is_public = target_url.startswith("https://") or (target_url.startswith("http://") and "localhost" not in target_url and "127.0.0.1" not in target_url)
    if is_public:
        try:
            await message.reply(card + "\n\n👇 *Tap below to open your player:*", buttons=[[get_webapp_button(target_url)]])
            return
        except Exception:
            pass
    await message.reply(card)
