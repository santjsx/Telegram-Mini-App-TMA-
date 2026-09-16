# System Context & Architecture Blueprint

**Project Name:** Telegram Personal Music Cloud (TPMC) / Telegram Mini App (TMA)  
**Version:** 2.2.1  
**Target Environment:** Render Free Web Service + Telegram MTProto Cloud Storage  
**Repository Identity:** Personal Music Streaming & Management System  

---

## 1. Executive Summary & Core Tech Stack

TPMC is a resilient music indexing, streaming, and delivery system designed to operate within the strict hardware constraints of a **Render Free Web Service** (512MB RAM, ephemeral filesystem, 15-minute idle sleep) by utilizing a **private Telegram channel as a durable, zero-cost media repository**.

### Complete Technology Stack:

| Layer | Technologies & Libraries | Version / Notes |
| :--- | :--- | :--- |
| **Backend Runtime** | Python | 3.10+ (tested on Python 3.14) |
| **Telegram Client (MTProto)** | `telethon`, `cryptg` | Dual-client (Bot Token + StringSession) |
| **Asynchronous Web Server** | `aiohttp` | Low-latency HTTP/1.1 & streaming engine |
| **Metadata Parsing** | `mutagen` | ID3, FLAC, Vorbis tag extraction |
| **Fuzzy Search & Ranking** | `rapidfuzz` | Token sort ratio, title/artist weighting |
| **Config & Logging** | `python-dotenv`, custom logger | Strongly typed, auto-redacts tokens |
| **Testing Framework** | `pytest`, `pytest-asyncio` | Full async unit and integration suite |
| **Frontend Framework** | React 19, TypeScript 5.7+ | Telegram Mini App SPA |
| **Build Tooling & Bundler** | Vite 6, PostCSS, Autoprefixer | Output configured to `webapp/dist/` |
| **CSS & Styling** | Tailwind CSS v3.4, Vanilla CSS | Dark glassmorphism, responsive mobile UI |
| **Iconography** | `lucide-react` | Ultra-lightweight SVG icons |
| **Hosting & Platform** | Render Free Tier, Telegram Bot Platform | Ephemeral Linux container, WebApp bridge |

---

## 2. Directory Structure & Subsystem Responsibilities

```text
telegram-music-manager/
├── .cursorrules                   # Strict "no-breakage, no-hallucination" rules
├── system-context.md              # Complete architectural context & do-not-touch map
├── requirements.txt               # Pinned Python dependencies
├── render.yaml                    # Render Blueprint infrastructure declaration
├── Procfile                       # Process execution command (web: python -m app.main)
├── .env.example                   # Environment configuration template
├── app/                           # Core Python Backend Subsystem
│   ├── main.py                    # App lifecycle, graceful shutdown, keep-alive loop
│   ├── config.py                  # Strongly typed Config dataclass & validation
│   ├── logging_config.py          # Sanitized logger redacting all Telegram tokens
│   ├── telegram/
│   │   ├── connection.py          # Dual connection manager & fault tolerance
│   │   ├── bot.py                 # Telethon Bot client, event router, inline buttons
│   │   └── user_client.py         # MTProto user client (StringSession) for channel access
│   ├── auth/
│   │   └── manager.py             # Access control, approval flow, atomic JSON persistence
│   ├── commands/
│   │   ├── router.py              # Master command & callback router
│   │   ├── start.py               # /start, /help, access request prompts
│   │   ├── status.py              # /status, /library diagnostics
│   │   ├── search.py              # /search with interactive pagination
│   │   ├── download.py            # /download, /download_all, /cancel
│   │   └── admin.py               # /reindex, user approvals, denial, broadcast
│   ├── index/
│   │   ├── models.py              # Track & Tag dataclass models
│   │   ├── parser.py              # Mutagen metadata parser & caption tokenizer
│   │   ├── indexer.py             # In-memory index, background spider, catalog stats
│   │   └── search.py              # RapidFuzz search engine with multi-field weighting
│   ├── jobs/
│   │   ├── models.py              # Job state machine & progress bar calculation
│   │   ├── manager.py             # Single-job concurrency limiter & throttled updates
│   │   ├── delivery.py            # Mode A direct media forwarding pipeline
│   │   └── retry.py               # FloodWait and transient network error backoff
│   └── health/
│       └── server.py              # aiohttp server: Mini App delivery & MTProto 206 streaming
├── frontend/                      # React 19 + TypeScript Telegram Mini App (Source)
│   ├── package.json               # Frontend dependencies & scripts
│   ├── vite.config.ts             # Vite config (builds directly to ../webapp/dist)
│   ├── tailwind.config.js         # Custom theme colors and gradients
│   └── src/
│       ├── main.tsx               # React entry point
│       ├── App.tsx                # Master UI state, Telegram BackButton, hydration
│       ├── types.ts               # Core TypeScript definitions (Track, Album, etc.)
│       ├── utils.ts               # Telegram WebApp initData parser & utilities
│       ├── hooks/
│       │   └── useAudioPlayer.ts  # HTML5 Audio controller, prefetch, queue, haptics
│       └── components/            # UI components (Player, Modals, Playlists, etc.)
├── webapp/                        # Public Web Directory served by aiohttp
│   ├── dist/                      # Production compiled assets generated by Vite
│   ├── index.html                 # Fallback static entry point
│   ├── app.js                     # Fallback vanilla client
│   └── style.css                  # Fallback styling
├── scripts/                       # Local Operational Tools
│   ├── generate_session.py        # Interactive Telethon StringSession generator
│   └── upload_local_songs.py      # Batch uploader for populating Telegram channel
└── tests/                         # Automated Pytest Suite
    ├── test_auth.py               # Access control and persistence tests
    ├── test_commands.py           # Command parsing and dispatch tests
    ├── test_config.py             # Validation and placeholder rejection tests
    ├── test_delivery.py           # Mode A forwarding pipeline tests
    ├── test_health.py             # Render health check & fault tolerance tests
    ├── test_jobs.py               # Concurrency limiter tests
    ├── test_logging.py            # Secret redaction tests
    ├── test_parser.py             # Metadata and caption parsing tests
    ├── test_search.py             # Search scoring and ranking tests
    └── test_webapp_api.py         # HTTP 206 streaming and catalog API tests
```

---

## 3. Major Architectural Patterns

### Pattern 1: Telegram as Media Source of Truth (Zero Disk Audio)
- All audio tracks (.mp3, .flac, .m4a) reside permanently inside the private Telegram channel (`CHANNEL_ID`).
- The Render container filesystem is treated as completely ephemeral.
- Media is **never** downloaded to disk on the server. Audio files are streamed on-the-fly or forwarded directly.

### Pattern 2: Disposable Host & Strict 512MB RAM Budget
- The server strictly enforces bounded memory usage to survive within Render's 512MB RAM threshold:
  - Header cache capped at 16 entries (~4MB max).
  - Audio chunk cache capped at 64 entries (~8MB max).
  - Mutagen album art extraction reads only the initial 384KB header and invokes explicit `gc.collect()`.
  - Background keep-alive worker executes regular garbage collection.

### Pattern 3: Dual Telegram Identity
- **Bot Client (`BOT_TOKEN`):** Communicates directly with users in Telegram DM. Dispatches command buttons, progress bars, interactive search pagination, and system status.
- **User MTProto Client (`TELEGRAM_SESSION`):** Acts as the privileged channel reader. Uses Telethon's `StringSession` to crawl the channel history, extract audio tags, and stream audio chunks over MTProto.

### Pattern 4: On-Demand MTProto HTTP 206 Partial Content Streaming
- Implemented in `app/health/server.py` (`handle_api_stream`):
  - Handles HTTP `Range: bytes=START-END` headers.
  - Aligns seek offsets to 128KB boundaries for MTProto wire efficiency.
  - Returns `206 Partial Content` with `Accept-Ranges: bytes`.
  - Enables instant playback startup (<15ms) and smooth scrubbing without buffering entire files.

### Pattern 5: Mode A Direct Media Forwarding
- When a user downloads songs through Telegram DM commands (`/download <id>` or `/download_all <query>`), the system forwards the original message directly from the private channel to the user's chat (`client.forward_messages`).
- Bypasses intermediate disk storage and server bandwidth exhaustion.

### Pattern 6: Fast Boot & Non-Blocking In-Memory Indexer
- The service boots up and immediately responds to Render health checks within 1–2 seconds.
- An asynchronous background task (`MusicIndexer.start_indexing`) crawls channel history without blocking the web server or bot listener.
- Real-time channel listener (`handle_new_channel_post`) automatically indexes new uploads as they occur.

### Pattern 7: Keep-Alive Self-Ping Worker
- Background loop in `app/main.py` pings `{WEBAPP_URL}/health` every 10 minutes to prevent Render Free tier instances from entering idle sleep during active usage periods.

### Pattern 8: Cryptographic Telegram WebApp Authentication
- WebApp requests provide `initData` signed by Telegram.
- `verify_telegram_init_data` computes HMAC-SHA256 signature using `BOT_TOKEN` to ensure user authenticity.
- Local development fallback automatically authenticates `localhost` connections to facilitate browser testing.

---

## 4. State Management & Data Flow

### Backend State:
1. **Catalog Index (`MusicIndexer`):**
   - Pure in-memory dictionaries: `tracks_by_id`, `tracks_by_artist`, `tracks_by_album`.
   - Populated asynchronously at startup; updated on channel message events.
2. **Access Control (`AccessManager`):**
   - In-memory approval map backed by thread-safe atomic JSON file writing (`data/access_control.json`).
3. **Delivery Job Manager (`JobManager`):**
   - Active job tracker enforcing single-job concurrency per instance (`max_concurrent_jobs: 1`).
4. **Streaming Caches (`HealthServer`):**
   - In-memory bounded LRU dicts for audio headers (`_audio_header_cache`) and chunk buffers (`_audio_chunk_cache`).
   - Disk cache for extracted album art in `data/artwork_cache/{message_id}.jpg`.

### Frontend State:
1. **Audio Player (`useAudioPlayer` hook):**
   - HTML5 `Audio` instance reference.
   - States: `currentTrack`, `isPlaying`, `currentTime`, `duration`, `volume`, `repeatMode`, `isShuffled`, `queue`, `queueIndex`, `history`.
2. **Persistence (`localStorage`):**
   - `tpmc_library_cache`: Instant 0ms perceived hydration before background refresh.
   - `tpmc_favorites`: Array of favorited track message IDs.
   - `tpmc_recent_tracks`: Last 50 played track IDs.
   - `tpmc_custom_playlists`: User-created custom playlists with metadata.
3. **Navigation & Modals:**
   - Active tabs: `all`, `favorites`, `recent`, `playlists`, `albums`, `artists`.
   - Modals: Full player, queue drawer, album detail, artist detail, playlists, lyrics, sleep timer.
   - Synced with Telegram native `WebApp.BackButton`.

---

## 5. Routing & API Specifications

### Backend Web Server (`aiohttp` on `PORT: 8080`):
- `GET /`: Serves the compiled React Mini App (`webapp/dist/index.html` or fallback `webapp/index.html`).
- `GET /health`: JSON status provider for Render health monitoring.
- `GET /api/library`: Returns catalog of tracks, top 20 albums, and top 20 artists (auth required).
- `GET /api/stream/{message_id}`: HTTP 206 partial content audio streaming.
- `GET /api/stream-info/{message_id}`: Returns file size, duration, and mime type.
- `GET/POST /api/stream/prefetch/{message_id}`: Pre-warms track header in background.
- `GET /api/artwork/{message_id}`: Serves extracted cover artwork with HTTP caching.
- `GET /assets/*`: Static JS/CSS bundles from `webapp/dist/assets`.
- `GET /static/*`: Static files from `webapp/`.

### Telegram Bot Commands:
- `/start`: Welcome message, Mini App launcher button, access request button.
- `/help`: Detailed command guide and usage tips.
- `/status`: System health, Telegram connection state, RAM usage, index count.
- `/library`: Overview of catalog, track count, total duration, format breakdown.
- `/search <query>`: Fuzzy multi-field search with 5-per-page inline pagination.
- `/download <id>`: Forward track directly to user DM via Mode A forwarding.
- `/download_all <query>`: Batch forward matching tracks with progress notification.
- `/cancel`: Abort current active delivery job.
- `/reindex` (Admin only): Trigger channel crawl to rebuild in-memory catalog.

---

## 6. DO NOT TOUCH / Working Features Map

The following subsystems are production-tested, stable, and must **NOT** be refactored, rewritten, or structurally rearranged:

### 🛡️ 1. Audio Streaming Pipeline (`app/health/server.py`)
- **DO NOT TOUCH:**
  - `handle_api_stream`: The byte-range calculation, 128KB chunk alignment, and chunk caching logic are finely tuned for MTProto streaming. Changing this will cause audio stuttering or broken seek functionality in mobile browsers.
  - `handle_api_artwork`: The 384KB header-only download and Mutagen picture extraction are tuned to prevent loading multi-megabyte audio files into RAM.

### 🛡️ 2. Dual Connection Manager (`app/telegram/connection.py`)
- **DO NOT TOUCH:**
  - `connect_all`: The fault-tolerant boot sequence ensures that if the user client fails or hits `FloodWaitError`, the HTTP health server remains online to keep Render happy.
  - `ConnectionState` enum and status reporting.

### 🛡️ 3. Mode A Media Forwarding (`app/jobs/delivery.py`)
- **DO NOT TOUCH:**
  - `deliver_tracks`: Relies on `client.forward_messages` directly between Telegram entities. Never replace this with a download-then-upload implementation.

### 🛡️ 4. Concurrency Limiter & Throttling (`app/jobs/manager.py` & `app/jobs/retry.py`)
- **DO NOT TOUCH:**
  - `JobManager.start_job`: Single active job restriction prevents Render OOM crashes.
  - Progress message throttling (minimum 3 seconds between Telegram message edits to avoid Bot API flood limits).

### 🛡️ 5. Access Control Persistence (`app/auth/manager.py`)
- **DO NOT TOUCH:**
  - `_save_sync`: Atomic temporary file write + rename pattern ensures `data/access_control.json` is never corrupted during server restarts.

### 🛡️ 6. Audio Engine Hook (`frontend/src/hooks/useAudioPlayer.ts`)
- **DO NOT TOUCH:**
  - Prefetching trigger on `timeupdate` (pre-fetches next track when current track reaches 80% completion).
  - MediaSession API integration and Telegram WebApp haptic triggers.

### 🛡️ 7. Render Deployment Blueprint (`render.yaml`, `Procfile`)
- **DO NOT TOUCH:**
  - Environment variable declarations, health check path (`/health`), and start command (`python -m app.main`).
