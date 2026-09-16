#!/usr/bin/env python3
"""
High-Speed Bulk Audio Uploader for Telegram Personal Music Cloud (TPMC)
Features:
- Multi-connection parallel chunk pipelining (FastTelethon architecture)
- C-accelerated AES encryption (via cryptg)
- Maximum 512 KB MTProto part chunking
- Real-time transfer speed meter (MB/s)
- Automatic embedded tag extraction (mutagen)
- Resumable history tracking (.uploaded_history.json)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import os
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Optional, Set

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.helpers import generate_random_long
from telethon.sessions import StringSession
from telethon.tl.functions.upload import SaveBigFilePartRequest
from telethon.tl.types import DocumentAttributeAudio, InputFileBig

try:
    import mutagen
except ImportError:
    mutagen = None

# Configure UTF-8 encoding on Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

logger = logging.getLogger("tpmc.uploader")

SUPPORTED_AUDIO_EXTENSIONS = {
    ".flac",
    ".m4a",
    ".mp3",
    ".wav",
    ".ogg",
    ".opus",
    ".aac",
}

HISTORY_FILE = Path(".uploaded_history.json")
PART_SIZE = 512 * 1024  # Maximum 512 KB per MTProto chunk


def normalize_tag_value(val: str) -> str:
    """Clean string for hashtag usage: lowercase, alphanumeric and underscores."""
    norm = unicodedata.normalize("NFKD", val).encode("ascii", "ignore").decode("utf-8")
    norm = re.sub(r"[^\w\s-]", "", norm).strip().lower()
    return re.sub(r"[\s-]+", "_", norm)


def extract_metadata(file_path: Path) -> dict:
    """
    Extract title, artist, album, genre, and duration from embedded audio tags or filename.
    """
    title = ""
    artist = ""
    album = ""
    genre = ""
    duration = 0

    if mutagen:
        try:
            audio = mutagen.File(str(file_path))
            if audio:
                if hasattr(audio.info, "length"):
                    duration = int(audio.info.length)

                tags = getattr(audio, "tags", {}) or {}
                if tags:
                    def get_val(keys):
                        for k in keys:
                            if k in tags:
                                v = tags[k]
                                if isinstance(v, list) and v:
                                    return str(v[0])
                                return str(v)
                        return ""

                    title = get_val(["title", "TITLE", "\xa9nam", "TIT2"])
                    artist = get_val(["artist", "ARTIST", "\xa9ART", "TPE1", "performer"])
                    album = get_val(["album", "ALBUM", "\xa9alb", "TALB"])
                    genre = get_val(["genre", "GENRE", "\xa9gen", "TCON"])
        except Exception as e:
            logger.debug(f"Mutagen read error for {file_path.name}: {e}")

    base_name = file_path.stem
    if not title or not artist:
        if " - " in base_name:
            parts = base_name.split(" - ", 1)
            if not title:
                title = parts[0].strip()
            if not artist:
                artist = parts[1].strip()
        else:
            if not title:
                title = base_name
            if not artist:
                artist = "Unknown Artist"

    return {
        "title": title.strip() or base_name,
        "artist": artist.strip() or "Unknown Artist",
        "album": album.strip(),
        "genre": genre.strip(),
        "duration": duration,
    }


def generate_caption(meta: dict, extra_tags: list[str]) -> str:
    """Generate standardized caption with structured hashtags."""
    tags = []
    if meta.get("artist") and meta["artist"] != "Unknown Artist":
        artists = re.split(r"[,&/]\s*", meta["artist"])
        for a in artists:
            norm_a = normalize_tag_value(a)
            if norm_a and len(norm_a) > 1:
                tags.append(f"#artist:{norm_a}")

    if meta.get("album"):
        norm_alb = normalize_tag_value(meta["album"])
        if norm_alb:
            tags.append(f"#album:{norm_alb}")

    if meta.get("genre"):
        norm_gen = normalize_tag_value(meta["genre"])
        if norm_gen:
            tags.append(f"#genre:{norm_gen}")

    for t in extra_tags:
        cleaned = t.strip().lstrip("#")
        if cleaned:
            tags.append(f"#{cleaned}")

    caption_lines = [f"🎵 **{meta['title']}** - {meta['artist']}"]
    if tags:
        caption_lines.append(" ".join(tags))

    return "\n\n".join(caption_lines)


def load_history() -> Set[str]:
    """Load previously uploaded file basenames."""
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data)
        except Exception:
            return set()
    return set()


def save_history(history: Set[str]) -> None:
    """Save uploaded file basenames."""
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(list(history)), f, indent=2)


async def fast_upload_file(
    client: TelegramClient,
    file_path: Path,
    workers: int = 4,
    progress_callback=None,
) -> InputFileBig:
    """
    High-speed parallel chunk uploader for big audio files (>10MB).
    Sends multiple 512KB MTProto chunks in parallel.
    """
    file_size = file_path.stat().st_size
    is_big = file_size > 10 * 1024 * 1024

    # For smaller files (<=10MB), client.upload_file with cryptg and 512KB parts is already super fast
    if not is_big:
        start_time = time.monotonic()
        def _cb(curr, tot):
            if progress_callback:
                progress_callback(curr, tot, start_time)

        return await client.upload_file(
            str(file_path),
            part_size_kb=512,
            progress_callback=_cb,
        )

    total_parts = math.ceil(file_size / PART_SIZE)
    file_id = generate_random_long()

    queue: asyncio.Queue[int] = asyncio.Queue()
    for i in range(total_parts):
        queue.put_nowait(i)

    uploaded_bytes = 0
    start_time = time.monotonic()
    lock = asyncio.Lock()
    file_handle = open(file_path, "rb")

    async def worker() -> None:
        nonlocal uploaded_bytes
        while True:
            try:
                part_index = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            offset = part_index * PART_SIZE
            async with lock:
                file_handle.seek(offset)
                chunk = file_handle.read(PART_SIZE)

            req = SaveBigFilePartRequest(
                file_id=file_id,
                file_part=part_index,
                file_total_parts=total_parts,
                bytes=chunk,
            )

            for attempt in range(5):
                try:
                    await client(req)
                    break
                except FloodWaitError as err:
                    await asyncio.sleep(err.seconds + 1)
                except Exception as e:
                    if attempt == 4:
                        raise
                    await asyncio.sleep(0.5 * (attempt + 1))

            uploaded_bytes += len(chunk)
            if progress_callback:
                progress_callback(uploaded_bytes, file_size, start_time)
            queue.task_done()

    try:
        tasks = [asyncio.create_task(worker()) for _ in range(workers)]
        await asyncio.gather(*tasks)
    finally:
        file_handle.close()

    return InputFileBig(
        id=file_id,
        parts=total_parts,
        name=file_path.name,
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description="TPMC High-Speed Local Songs Uploader")
    parser.add_argument(
        "--folder",
        type=str,
        default=r"C:\Users\heysa\Music\Songs",
        help="Path to folder containing audio files",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of songs to upload in this run",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of concurrent upload worker pipelines (default: 4, recommended: 4-6)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.8,
        help="Delay in seconds between songs (default: 0.8s)",
    )
    parser.add_argument(
        "--tag",
        type=str,
        nargs="*",
        default=[],
        help="Additional custom tags to attach (e.g. --tag favorite telugu)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate scan and show metadata without uploading",
    )

    args = parser.parse_args()
    music_dir = Path(args.folder)

    if not music_dir.exists() or not music_dir.is_dir():
        print(f"[ERROR] Music folder not found: {music_dir}")
        sys.exit(1)

    load_dotenv()
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    session_str = os.getenv("TELEGRAM_SESSION")
    raw_channel_id = os.getenv("CHANNEL_ID")

    if not all([api_id, api_hash, session_str, raw_channel_id]):
        print("[ERROR] Missing required credentials in .env file.")
        sys.exit(1)

    channel_id = int(raw_channel_id)
    history = load_history()

    all_files = [
        f for f in music_dir.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS
    ]
    all_files.sort(key=lambda x: x.name.lower())

    pending_files = [f for f in all_files if f.name not in history]

    print("=" * 60)
    print("TPMC — High-Speed Parallel Music Cloud Uploader ⚡")
    print("=" * 60)
    print(f"Folder:         {music_dir}")
    print(f"Total files:    {len(all_files)}")
    print(f"Already synced: {len(all_files) - len(pending_files)}")
    print(f"Pending upload: {len(pending_files)}")
    print(f"Workers:        {args.workers} concurrent chunk streams")
    print("=" * 60)

    if not pending_files:
        print("✨ All songs in this folder have already been uploaded!")
        return

    files_to_upload = pending_files[: args.limit] if args.limit else pending_files
    print(f"Uploading {len(files_to_upload)} song(s)...\n")

    if args.dry_run:
        print("[DRY RUN MODE] Simulating first 5 files:\n")
        for i, f in enumerate(files_to_upload[:5], start=1):
            meta = extract_metadata(f)
            caption = generate_caption(meta, args.tag)
            size_mb = f.stat().st_size / (1024 * 1024)
            print(f"[{i}] {f.name} ({size_mb:.1f} MB)")
            print(f"    Caption:\n{caption}\n")
        return

    client = TelegramClient(
        StringSession(session_str),
        int(api_id),
        api_hash,
        connection_retries=10,
        retry_delay=2,
    )
    await client.connect()

    if not await client.is_user_authorized():
        print("[ERROR] Telegram session authorization failed.")
        await client.disconnect()
        return

    channel = await client.get_entity(channel_id)
    print(f"[CONNECTED] Uploading to channel: '{channel.title}' ({channel_id})\n")

    uploaded_count = 0
    failed_count = 0

    try:
        for idx, file_path in enumerate(files_to_upload, start=1):
            meta = extract_metadata(file_path)
            caption = generate_caption(meta, args.tag)
            file_size_mb = file_path.stat().st_size / (1024 * 1024)

            print(f"[{idx}/{len(files_to_upload)}] {file_path.name} ({file_size_mb:.1f} MB)...")

            def progress_callback(current: int, total: int, start_time: Optional[float] = None) -> None:
                if total:
                    pct = int(current / total * 100)
                    mb_curr = current / (1024 * 1024)
                    mb_total = total / (1024 * 1024)
                    speed_str = ""
                    if start_time:
                        elapsed = time.monotonic() - start_time
                        if elapsed > 0.3:
                            speed_mb = mb_curr / elapsed
                            speed_str = f" | {speed_mb:.1f} MB/s"
                    sys.stdout.write(
                        f"\r   ⚡ Uploading: {pct}% [{mb_curr:.1f}MB / {mb_total:.1f}MB]{speed_str}   "
                    )
                    sys.stdout.flush()

            while True:
                try:
                    # 1. High-speed parallel chunk upload
                    uploaded_file = await fast_upload_file(
                        client=client,
                        file_path=file_path,
                        workers=args.workers,
                        progress_callback=progress_callback,
                    )

                    # 2. Attach metadata and post to channel
                    attributes = [
                        DocumentAttributeAudio(
                            duration=meta["duration"],
                            title=meta["title"],
                            performer=meta["artist"],
                        )
                    ]
                    msg = await client.send_file(
                        channel,
                        file=uploaded_file,
                        caption=caption,
                        attributes=attributes,
                    )
                    sys.stdout.write("\n")
                    print(f"   [SUCCESS] Delivered as message ID: {msg.id}")

                    history.add(file_path.name)
                    save_history(history)
                    uploaded_count += 1
                    break

                except FloodWaitError as e:
                    print(f"\n   [FLOOD WAIT] Telegram rate limit: waiting {e.seconds} seconds...")
                    await asyncio.sleep(e.seconds + 2)
                except Exception as e:
                    sys.stdout.write("\n")
                    print(f"   [FAILED] Could not upload {file_path.name}: {e}")
                    failed_count += 1
                    break

            await asyncio.sleep(args.delay)

    except KeyboardInterrupt:
        print("\n\n[PAUSED] Upload paused by user. Progress has been saved.")
    finally:
        await client.disconnect()
        print("\n" + "=" * 60)
        print(f"Upload Summary: {uploaded_count} uploaded, {failed_count} failed.")
        print(f"Total uploaded in cloud history: {len(history)} songs.")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
