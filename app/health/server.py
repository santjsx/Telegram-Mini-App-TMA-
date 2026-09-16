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
        self.app.router.add_get("/api/artwork/{message_id}", self.handle_api_artwork)

        # Static assets for the web app
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

        try:
            msg = await self.user_client.get_message(mid)
            if not msg or not msg.document:
                return web.Response(status=404)

            # Download up to 3MB chunks for header metadata extraction
            chunks = []
            total = 0
            async for chunk in self.user_client.client.iter_download(msg.document, request_size=3 * 1024 * 1024):
                chunks.append(chunk)
                total += len(chunk)
                if total >= 3 * 1024 * 1024:
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

            # 3. Try MP4 / M4A
            if not pic_data and ("mp4" in (msg.document.mime_type or "") or "m4a" in (msg.document.mime_type or "")):
                try:
                    from mutagen.mp4 import MP4
                    full_bytes = await self.user_client.client.download_media(msg.document, bytes)
                    mp = MP4(io.BytesIO(full_bytes))
                    if "covr" in mp and mp["covr"]:
                        pic_data = bytes(mp["covr"][0])
                except Exception:
                    pass

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

    async def handle_api_stream(self, request: web.Request) -> web.StreamResponse:
        """
        Stream audio directly from Telegram MTProto with HTTP 206 Partial Content byte ranges.
        Enables instantaneous playback start and smooth scrubber seeking.
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

            response = web.StreamResponse(status=206, reason="Partial Content")
            response.headers["Content-Type"] = mime_type
            response.headers["Accept-Ranges"] = "bytes"
            response.headers["Content-Range"] = f"bytes {start}-{end}/{total_size}"
            response.headers["Content-Length"] = str(length)
            response.headers["Cache-Control"] = "public, max-age=3600"
            await response.prepare(request)

            try:
                async for chunk in self.user_client.client.iter_download(
                    msg.document,
                    offset=start,
                    request_size=length,
                    chunk_size=128 * 1024,
                ):
                    await response.write(chunk)
            except (ConnectionResetError, asyncio.CancelledError):
                # Normal client abort when scrubbing or skipping tracks
                pass
            except Exception as e:
                logger.warning(f"Streaming chunk error for msg {mid}: {e}")

            return response
        else:
            # Full file streaming
            response = web.StreamResponse(status=200)
            response.headers["Content-Type"] = mime_type
            response.headers["Accept-Ranges"] = "bytes"
            response.headers["Content-Length"] = str(total_size)
            response.headers["Cache-Control"] = "public, max-age=3600"
            await response.prepare(request)

            try:
                async for chunk in self.user_client.client.iter_download(
                    msg.document,
                    offset=0,
                    request_size=total_size,
                    chunk_size=128 * 1024,
                ):
                    await response.write(chunk)
            except (ConnectionResetError, asyncio.CancelledError):
                pass
            except Exception as e:
                logger.warning(f"Streaming chunk error for msg {mid}: {e}")

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
