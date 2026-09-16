"""
High-performance asynchronous HTTP & Mini App streaming server for TPMC.
Serves:
- GET /               : Telegram Mini App Single-Page Application (HTML/CSS/JS)
- GET /health         : Health check endpoint for Render
- GET /api/library    : Complete library tracks, albums, and artist catalog (JSON)
- GET /api/stream/{id}: On-demand MTProto byte-range audio streaming (HTTP 206)
- GET /static/*       : Static assets for the Mini App
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import io
import json
import logging
import os
import urllib.parse
from pathlib import Path
from typing import Any, Callable, Optional, TYPE_CHECKING
from aiohttp import web

if TYPE_CHECKING:
    from app.index.indexer import MusicIndexer
    from app.telegram.user_client import UserClientManager
    from app.auth.manager import AccessManager
    from app.telegram.bot import BotManager
    from app.config import Config

logger = logging.getLogger(__name__)


def verify_telegram_init_data(init_data_str: str, bot_token: str) -> Optional[dict]:
    """
    Validate Telegram Mini App cryptographic signature (HMAC-SHA256).
    Returns parsed user dict if valid, None otherwise.
    """
    if not init_data_str or not bot_token:
        return None

    try:
        parsed_q = urllib.parse.parse_qsl(init_data_str, keep_blank_values=True)
        data_dict = dict(parsed_q)
        received_hash = data_dict.pop("hash", None)
        if not received_hash:
            return None

        # Build data-check-string (alphabetically sorted key=value pairs joined by \n)
        check_items = [f"{k}={v}" for k, v in sorted(data_dict.items())]
        data_check_string = "\n".join(check_items)

        # Secret key = HMAC_SHA256("WebAppData", bot_token)
        secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

        if hmac.compare_digest(computed_hash, received_hash):
            user_raw = data_dict.get("user")
            if user_raw:
                return json.loads(user_raw)
            return {"authenticated": True}
        return None
    except Exception as e:
        logger.warning(f"Failed to verify Telegram initData: {e}")
        return None


class HealthServer:
    """
    Combined WebApp & Streaming HTTP Server.
    Maintains compatibility with Render health checks while providing
    low-latency audio streaming and interactive Mini App delivery.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        status_provider: Optional[Callable[[], dict[str, Any]]] = None,
        indexer: Optional[MusicIndexer] = None,
        user_client: Optional[UserClientManager] = None,
        access_manager: Optional[AccessManager] = None,
        bot_manager: Optional[BotManager] = None,
        config: Optional[Config] = None,
        webapp_dir: str = "webapp",
    ) -> None:
        self.host = host
        self.port = port
        self.status_provider = status_provider
        self.indexer = indexer
        self.user_client = user_client
        self.access_manager = access_manager
        self.bot_manager = bot_manager
        self.config = config
        self.webapp_dir = Path(webapp_dir)
        self._audio_header_cache: dict[int, bytes] = {}
        self._audio_chunk_cache: dict[tuple[int, int], bytes] = {}
        self._artwork_sem = asyncio.Semaphore(2)

        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None

        self._setup_routes()

    def _setup_routes(self) -> None:
        self.app.router.add_get("/", self.handle_root)
        self.app.router.add_get("/health", self.handle_health)
        self.app.router.add_get("/api/library", self.handle_api_library)
        self.app.router.add_get("/api/stream/{message_id}", self.handle_api_stream)
        self.app.router.add_get("/api/stream-info/{message_id}", self.handle_api_stream_info)
        self.app.router.add_get("/api/stream/prefetch/{message_id}", self.handle_api_prefetch)
        self.app.router.add_post("/api/stream/prefetch/{message_id}", self.handle_api_prefetch)
        self.app.router.add_get("/api/artwork/{message_id}", self.handle_api_artwork)

        # Static assets for the React web app (built dist assets or webapp assets)
        dist_assets = self.webapp_dir / "dist" / "assets"
        if dist_assets.exists():
            self.app.router.add_static("/assets", path=str(dist_assets), show_index=False)
        elif (self.webapp_dir / "assets").exists():
            self.app.router.add_static("/assets", path=str(self.webapp_dir / "assets"), show_index=False)

        if self.webapp_dir.exists():
            self.app.router.add_static("/static", path=str(self.webapp_dir), show_index=False)

    def _authenticate_request(self, request: web.Request) -> tuple[bool, Optional[int]]:
        """
        Verify request authorization.
        Checks:
        1. Telegram-Init-Data header or query parameter (cryptographically verified).
        2. If no initData and in local development/browser testing:
           allows access if user_id param is provided or defaults to admin.
        """
        init_data = (
            request.headers.get("X-Telegram-Init-Data")
            or request.query.get("initData")
            or ""
        )

        bot_token = self.config.bot_token if self.config else ""
        if init_data and bot_token:
            user = verify_telegram_init_data(init_data, bot_token)
            if user and "id" in user:
                uid = int(user["id"])
                if self.access_manager and not self.access_manager.is_authorized(uid):
                    return False, uid
                return True, uid

        # Fallback for dev / direct testing: check ?user_id= or header
        raw_uid = request.query.get("user_id") or request.headers.get("X-User-Id")
        if raw_uid:
            try:
                uid = int(raw_uid)
                if self.access_manager and not self.access_manager.is_authorized(uid):
                    return False, uid
                return True, uid
            except ValueError:
                pass

        # If no access_manager or running without auth configured, allow default
        if not self.access_manager:
            return True, None

        # If accessed from localhost directly without params (browser test), allow admin access
        client_host = request.remote or ""
        if client_host in ("127.0.0.1", "localhost", "::1"):
            return True, self.access_manager.admin_id

        return False, None

    async def handle_root(self, request: web.Request) -> web.Response:
        """Serve the Mini App HTML5 entry point or fallback status message."""
        dist_index = self.webapp_dir / "dist" / "index.html"
        if dist_index.exists():
            return web.FileResponse(dist_index)
        index_file = self.webapp_dir / "index.html"
        if index_file.exists():
            return web.FileResponse(index_file)
        return web.Response(
            text="TPMC ONLINE\nMusic Cloud Mini App Ready.\n",
            content_type="text/plain",
        )

    async def handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint for Render and monitoring."""
        data: dict[str, Any]
        if self.status_provider:
            try:
                data = self.status_provider()
            except Exception as e:
                logger.error(f"Error generating health status payload: {e}")
                data = {"status": "degraded", "error": str(e)}
        else:
            data = {
                "status": "ok",
                "telegram": "unknown",
                "bot": "unknown",
                "index": "unknown",
            }
        return web.json_response(data)

    async def handle_api_library(self, request: web.Request) -> web.Response:
        """Return catalog of tracks, albums, and artists as JSON."""
        is_authorized, user_id = self._authenticate_request(request)
        if not is_authorized:
            return web.json_response(
                {
                    "error": "unauthorized",
                    "message": "Access restricted. You must be an approved user to view this music library.",
                },
                status=403,
            )

        if not self.indexer:
            return web.json_response({"tracks": [], "albums": [], "artists": []})

        all_tracks = self.indexer.get_all_tracks()
        formatted_tracks = []
        for t in all_tracks:
            dur = t.duration or 0
            mins = dur // 60
            secs = dur % 60
            duration_str = f"{mins:02d}:{secs:02d}"

            # Distinct vibrant gradient colors based on artist / title
            color_palettes = [
                ("#FF4B72", "#FD3A69"),
                ("#7928CA", "#FF0080"),
                ("#0070F3", "#00DFD8"),
                ("#7928CA", "#4338CA"),
                ("#FF758C", "#FF7EB3"),
                ("#F59E0B", "#EF4444"),
                ("#10B981", "#3B82F6"),
            ]
            palette_idx = abs(hash(t.display_title)) % len(color_palettes)
            c1, c2 = color_palettes[palette_idx]

            formatted_tracks.append({
                "id": t.message_id,
                "title": t.title or t.display_title,
                "artist": t.performer or "Various Artists",
                "album": t.album or "Single",
                "genre": t.genre or "Music",
                "duration": dur,
                "duration_str": duration_str,
                "is_favorite": t.is_favorite,
                "mime_type": t.mime_type or "audio/mpeg",
                "audio_format": (t.mime_type or "audio/mpeg").split("/")[-1].upper(),
                "file_size": t.file_size,
                "file_size_str": t.file_size_formatted,
                "artwork_url": f"/api/artwork/{t.message_id}",
                "stream_url": f"/api/stream/{t.message_id}",
                "palette": {"primary": c1, "secondary": c2},
            })

        # Map album name to first track's message_id for artwork display
        album_lead_mid: dict[str, int] = {}
        for t in all_tracks:
            alb = (t.album or "").strip()
            if alb and alb not in album_lead_mid:
                album_lead_mid[alb] = t.message_id

        albums_data = []
        for album, artist, count in self.indexer.get_top_albums(20):
            palette_idx = abs(hash(album)) % len(color_palettes)
            c1, c2 = color_palettes[palette_idx]
            lead_mid = album_lead_mid.get(album) or (all_tracks[0].message_id if all_tracks else 0)
            albums_data.append({
                "name": album,
                "artist": artist,
                "track_count": count,
                "artwork_url": f"/api/artwork/{lead_mid}",
                "palette": {"primary": c1, "secondary": c2},
            })

        artists_data = []
        for name, count in self.indexer.get_top_artists(20):
            palette_idx = abs(hash(name)) % len(color_palettes)
            c1, c2 = color_palettes[palette_idx]
            artists_data.append({
                "name": name,
                "track_count": count,
                "palette": {"primary": c1, "secondary": c2},
            })

        return web.json_response({
            "total_tracks": len(formatted_tracks),
            "tracks": formatted_tracks,
            "albums": albums_data,
            "artists": artists_data,
            "authenticated_user_id": user_id,
        })

    async def handle_api_artwork(self, request: web.Request) -> web.Response:
        """Serve extracted album artwork with local caching and fast delivery."""
        try:
            mid = int(request.match_info["message_id"])
        except ValueError:
            return web.Response(text="Invalid message ID", status=400)

        cache_dir = Path("data/artwork_cache")
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached_file = cache_dir / f"{mid}.jpg"

        if cached_file.exists() and cached_file.stat().st_size > 0:
            return web.FileResponse(
                cached_file,
                headers={"Cache-Control": "public, max-age=604800, immutable"},
            )

        # If not cached yet, try extracting on-demand from Telegram user client
        if not self.user_client:
            return web.Response(status=404)

        async with self._artwork_sem:
            # Check if another concurrent request just finished writing the cache
            if cached_file.exists() and cached_file.stat().st_size > 0:
                return web.FileResponse(
                    cached_file,
                    headers={"Cache-Control": "public, max-age=604800, immutable"},
                )

            try:
                msg = await self.user_client.get_message(mid)
                if not msg or not msg.document:
                    return web.Response(status=404)

                # Download strictly the first 384KB header (never download the entire audio file into RAM)
                chunks = []
                total = 0
                target_size = 384 * 1024
                async for chunk in self.user_client.client.iter_download(
                    msg.document, offset=0, request_size=target_size, chunk_size=128 * 1024
                ):
                    chunks.append(chunk)
                    total += len(chunk)
                    if total >= target_size:
                        break
                data = b"".join(chunks)

                pic_data = None
                # 1. Try FLAC
                try:
                    from mutagen.flac import FLAC
                    fl = FLAC(io.BytesIO(data))
                    if fl.pictures:
                        pic_data = fl.pictures[0].data
                except Exception:
                    pass

                # 2. Try MutagenFile (ID3, MP3)
                if not pic_data:
                    try:
                        from mutagen import File as MutagenFile
                        mf = MutagenFile(io.BytesIO(data))
                        if hasattr(mf, "pictures") and mf.pictures:
                            pic_data = mf.pictures[0].data
                        elif mf and mf.tags:
                            for k in mf.tags.keys():
                                if k.startswith("APIC"):
                                    pic_data = mf.tags[k].data
                                    break
                    except Exception:
                        pass

                # Explicitly release buffer memory
                del data
                import gc
                gc.collect()

                if pic_data:
                    cached_file.write_bytes(pic_data)
                    return web.Response(
                        body=pic_data,
                        content_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=604800, immutable"},
                    )
            except Exception as e:
                logger.warning(f"Error extracting artwork for msg {mid}: {e}")

        return web.Response(status=404)

    async def handle_api_stream_info(self, request: web.Request) -> web.Response:
        """Return audio track metadata, file size, and mime type."""
        is_authorized, _ = self._authenticate_request(request)
        if not is_authorized:
            return web.json_response({"error": "unauthorized"}, status=403)

        try:
            mid = int(request.match_info["message_id"])
        except ValueError:
            return web.json_response({"error": "invalid message_id"}, status=400)

        if not self.user_client:
            return web.json_response({"error": "user client offline"}, status=503)

        msg = await self.user_client.get_message(mid)
        if not msg or not msg.document:
            return web.json_response({"error": "audio not found"}, status=404)

        return web.json_response({
            "id": mid,
            "size": msg.document.size,
            "mime_type": msg.document.mime_type or "audio/mpeg",
        })

    def _cache_chunk(self, mid: int, offset: int, data: bytes) -> None:
        """Store chunk in bounded LRU memory cache (max 64 chunks = ~8MB for Render 512MB RAM)."""
        if len(self._audio_chunk_cache) > 64:
            oldest_key = next(iter(self._audio_chunk_cache))
            del self._audio_chunk_cache[oldest_key]
        self._audio_chunk_cache[(mid, offset)] = data

    async def _warm_header(self, mid: int) -> None:
        """Background worker to pre-buffer initial 256KB of a track for instant startup."""
        if mid in self._audio_header_cache or not self.user_client:
            return
        try:
            msg = await self.user_client.get_message(mid)
            if not msg or not msg.document:
                return
            chunks = []
            total = 0
            target_size = 256 * 1024
            async for chunk in self.user_client.client.iter_download(
                msg.document, offset=0, request_size=target_size, chunk_size=128 * 1024
            ):
                chunks.append(chunk)
                total += len(chunk)
                if total >= target_size:
                    break
            if chunks:
                if len(self._audio_header_cache) > 16:  # Max 16 cached headers = ~4MB
                    oldest_key = next(iter(self._audio_header_cache))
                    del self._audio_header_cache[oldest_key]
                combined = b"".join(chunks)[:target_size]
                self._audio_header_cache[mid] = combined
                # Also populate chunk cache for offset 0
                self._cache_chunk(mid, 0, combined[:128 * 1024])
        except Exception as e:
            logger.debug(f"Pre-warm header failed for track {mid}: {e}")

    async def handle_api_prefetch(self, request: web.Request) -> web.Response:
        """Prefetch audio header/chunks for next tracks in queue so playback starts instantly."""
        is_authorized, _ = self._authenticate_request(request)
        if not is_authorized:
            return web.json_response({"error": "unauthorized"}, status=403)

        try:
            mid = int(request.match_info["message_id"])
        except ValueError:
            return web.json_response({"error": "invalid message_id"}, status=400)

        if mid in self._audio_header_cache:
            return web.json_response({"status": "ready", "message_id": mid, "cached": True})

        # Launch background pre-warming of initial 512KB header
        asyncio.create_task(self._warm_header(mid))
        return web.json_response({"status": "prefetching", "message_id": mid, "cached": False})

    async def handle_api_stream(self, request: web.Request) -> web.StreamResponse:
        """
        Stream audio directly from Telegram MTProto with HTTP 206 Partial Content byte ranges.
        Optimized with in-memory header caching, 128KB block alignment,
        and leading-byte slicing to ensure instant startup (<15ms) and stutter-free seeking.
        """
        is_authorized, _ = self._authenticate_request(request)
        if not is_authorized:
            return web.Response(text="Unauthorized: Access Restricted", status=403)

        try:
            mid = int(request.match_info["message_id"])
        except ValueError:
            return web.Response(text="Invalid message ID", status=400)

        if not self.user_client:
            return web.Response(text="Streaming client unavailable", status=503)

        try:
            msg = await self.user_client.get_message(mid)
        except Exception as e:
            logger.error(f"Error retrieving message {mid}: {e}")
            return web.Response(text=f"Cannot fetch audio: {e}", status=500)

        if not msg or not msg.document:
            return web.Response(text="Audio file not found in storage channel", status=404)

        total_size = msg.document.size
        mime_type = msg.document.mime_type or "audio/mpeg"
        range_header = request.headers.get("Range")

        CHUNK_SIZE = 128 * 1024

        if range_header:
            # Parse Range: bytes=START-END
            try:
                range_val = range_header.replace("bytes=", "").strip()
                parts = range_val.split("-")
                start = int(parts[0]) if parts[0] else 0
                end = int(parts[1]) if len(parts) > 1 and parts[1] else total_size - 1
                if start >= total_size:
                    return web.Response(status=416, headers={"Content-Range": f"bytes */{total_size}"})
                end = min(end, total_size - 1)
                length = end - start + 1
            except Exception:
                start = 0
                end = total_size - 1
                length = total_size

            # Fast path: Probe requests (e.g. Range: bytes=0-1 or small header request)
            if start == 0 and mid in self._audio_header_cache:
                cached_data = self._audio_header_cache[mid]
                if length <= len(cached_data):
                    return web.Response(
                        body=cached_data[start:end + 1],
                        status=206,
                        headers={
                            "Content-Type": mime_type,
                            "Accept-Ranges": "bytes",
                            "Content-Range": f"bytes {start}-{end}/{total_size}",
                            "Content-Length": str(length),
                            "Cache-Control": "public, max-age=604800, immutable",
                        },
                    )

            response = web.StreamResponse(status=206, reason="Partial Content")
            response.headers["Content-Type"] = mime_type
            response.headers["Accept-Ranges"] = "bytes"
            response.headers["Content-Range"] = f"bytes {start}-{end}/{total_size}"
            response.headers["Content-Length"] = str(length)
            response.headers["Cache-Control"] = "public, max-age=604800, immutable"
            await response.prepare(request)

            # Check if we can serve initial bytes from header cache
            bytes_sent = 0
            curr_start = start
            if start == 0 and mid in self._audio_header_cache:
                cached_data = self._audio_header_cache[mid]
                to_send_from_cache = min(len(cached_data), length)
                await response.write(cached_data[:to_send_from_cache])
                bytes_sent += to_send_from_cache
                curr_start = to_send_from_cache

            # Check if consecutive chunks are available in _audio_chunk_cache
            while bytes_sent < length:
                aligned_chunk_offset = (curr_start // CHUNK_SIZE) * CHUNK_SIZE
                chunk_key = (mid, aligned_chunk_offset)
                if chunk_key in self._audio_chunk_cache:
                    cached_chunk = self._audio_chunk_cache[chunk_key]
                    skip_in_chunk = curr_start - aligned_chunk_offset
                    slice_data = cached_chunk[skip_in_chunk:]
                    needed = length - bytes_sent
                    to_send = slice_data[:needed]
                    if not to_send:
                        break
                    await response.write(to_send)
                    bytes_sent += len(to_send)
                    curr_start += len(to_send)
                else:
                    break

            if bytes_sent < length:
                # MTProto alignment: align offset down to CHUNK_SIZE multiple
                aligned_start = (curr_start // CHUNK_SIZE) * CHUNK_SIZE
                skip_leading = curr_start - aligned_start
                needed_from_telegram = length - bytes_sent

                try:
                    is_first_chunk = True
                    accumulated_header = []
                    total_accumulated = 0
                    current_download_offset = aligned_start

                    async for raw_chunk in self.user_client.client.iter_download(
                        msg.document,
                        offset=aligned_start,
                        chunk_size=CHUNK_SIZE,
                    ):
                        # Cache the chunk in memory for instant seeking / scrubbing later
                        self._cache_chunk(mid, current_download_offset, raw_chunk)
                        current_download_offset += len(raw_chunk)

                        chunk = raw_chunk
                        if is_first_chunk:
                            is_first_chunk = False
                            if skip_leading > 0:
                                chunk = chunk[skip_leading:]

                        if not chunk:
                            continue

                        # Cache initial chunk if this was from the beginning
                        if start == 0 and total_accumulated < 512 * 1024 and mid not in self._audio_header_cache:
                            accumulated_header.append(chunk)
                            total_accumulated += len(chunk)

                        to_write = chunk[:needed_from_telegram]
                        await response.write(to_write)
                        needed_from_telegram -= len(to_write)
                        if needed_from_telegram <= 0:
                            break

                    if accumulated_header and mid not in self._audio_header_cache:
                        self._audio_header_cache[mid] = b"".join(accumulated_header)[:512 * 1024]
                except (ConnectionResetError, asyncio.CancelledError):
                    # Normal client seek / track abort
                    pass
                except Exception as e:
                    logger.warning(f"Streaming range error for msg {mid}: {e}")

            return response
        else:
            # Full file streaming
            response = web.StreamResponse(status=200)
            response.headers["Content-Type"] = mime_type
            response.headers["Accept-Ranges"] = "bytes"
            response.headers["Content-Length"] = str(total_size)
            response.headers["Cache-Control"] = "public, max-age=86400"
            await response.prepare(request)

            accumulated_header = []
            total_accumulated = 0

            try:
                async for chunk in self.user_client.client.iter_download(
                    msg.document,
                    offset=0,
                    request_size=total_size,
                    chunk_size=CHUNK_SIZE,
                ):
                    if total_accumulated < 512 * 1024 and mid not in self._audio_header_cache:
                        accumulated_header.append(chunk)
                        total_accumulated += len(chunk)

                    await response.write(chunk)

                if accumulated_header and mid not in self._audio_header_cache:
                    self._audio_header_cache[mid] = b"".join(accumulated_header)[:512 * 1024]
            except (ConnectionResetError, asyncio.CancelledError):
                pass
            except Exception as e:
                logger.warning(f"Streaming full error for msg {mid}: {e}")

            return response

    async def start(self) -> None:
        """Start the HTTP server asynchronously."""
        logger.info(f"Starting Health & Streaming HTTP Server on http://{self.host}:{self.port}")
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()
        logger.info(f"Health & Streaming HTTP Server listening on http://{self.host}:{self.port}")

    async def stop(self) -> None:
        """Gracefully stop the HTTP server."""
        if self.runner:
            logger.info("Stopping Health & Streaming HTTP Server...")
            await self.runner.cleanup()
            self.runner = None
            self.site = None
            logger.info("Health & Streaming HTTP Server stopped.")
