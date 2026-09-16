# 🎵 Telegram Personal Music Cloud (TPMC)

**TPMC** is a resilient, personal music storage, indexing, and delivery system that uses a private Telegram channel as the durable source of truth and a Python backend hosted on Render Free Web Service as the search, command, and delivery layer.

---

## 🌟 Key Architecture Principles

1. **Telegram is the Source of Truth:** Music files are stored permanently in your private Telegram channel.
2. **Disposable Hosting:** Render's filesystem is completely ephemeral. No music is permanently saved on Render disk.
3. **Mode A Media Forwarding:** Tracks are forwarded directly from the private channel to your DM, avoiding heavy download/upload bandwidth and memory usage.
4. **Dual Telegram Identity:**
   - **Bot Client (`BOT_TOKEN`):** Communicates directly with you in Telegram DM (`/start`, `/search`, `/download`, buttons, progress notifications).
   - **User MTProto Client (`TELEGRAM_SESSION`):** Accesses your private channel, reads audio metadata, and forwards media.
5. **Fast Boot & Non-Blocking In-Memory Indexer:** The bot boots up and answers commands immediately while an asynchronous background task reconstructs the searchable index from channel history.
6. **Adaptive Rate Limiting:** Intercepts Telegram `FloodWait` exceptions, sleeps server-mandated durations dynamically, and applies exponential backoff for network drops.
7. **Strict Security:** Strictly rejects any unauthorized user (`AUTHORIZED_USER_ID`) with an "Access denied" response. All secrets and session tokens are scrubbed from log outputs.

---

## 📁 Project Structure

```text
├── app/
│   ├── __init__.py
│   ├── config.py             # Strongly typed environment configuration & validator
│   ├── logging_config.py     # Sanitized structured logger (redacts secrets)
│   ├── main.py               # Main orchestrator, lifecycle & shutdown handler
│   ├── telegram/
│   │   ├── connection.py     # Centralized dual Telegram connection manager
│   │   ├── bot.py            # Bot client & event router
│   │   └── user_client.py    # MTProto user client for channel access
│   ├── commands/
│   │   ├── router.py         # Master command dispatcher
│   │   ├── start.py          # /start and /help handlers
│   │   ├── status.py         # /status and /library stats
│   │   ├── search.py         # /search with interactive pagination buttons
│   │   ├── download.py       # /download, /download_all, and /cancel
│   │   └── admin.py          # /reindex confirmation handler
│   ├── index/
│   │   ├── models.py         # Track & Tag dataclass models
│   │   ├── parser.py         # Caption tag tokenizer & audio metadata extractor
│   │   ├── indexer.py        # In-memory index store with background sync
│   │   └── search.py         # Multi-field search & scoring engine
│   ├── jobs/
│   │   ├── models.py         # Job state machine & progress bar
│   │   ├── manager.py        # Single-job concurrency limiter & throttled updates
│   │   ├── delivery.py       # Mode A media forwarding pipeline
│   │   └── retry.py          # FloodWait & transient error backoff handler
│   └── health/
│       └── server.py         # Asyncio-native HTTP health endpoint (GET / and /health)
├── scripts/
│   └── generate_session.py   # Interactive CLI tool to generate TELEGRAM_SESSION locally
├── tests/                    # Comprehensive unit and integration test suite
├── render.yaml               # Render Blueprint deployment configuration
├── requirements.txt          # Pinned dependencies
├── .env.example              # Environment variables template
└── .gitignore                # Secret and cache exclusions
```

---

## 🚀 Getting Started

### 1. Prerequisites

- Python 3.10+ (tested on Python 3.14)
- A Telegram account with:
  - `API_ID` & `API_HASH` from [my.telegram.org](https://my.telegram.org)
  - A Telegram Bot created via [@BotFather](https://t.me/BotFather) (`BOT_TOKEN`)
  - A private Telegram channel where you upload your music (`CHANNEL_ID`)
  - Your Telegram User ID from [@userinfobot](https://t.me/userinfobot) (`AUTHORIZED_USER_ID`)

---

### 2. Generate Your User Session String

To allow the user client to read your private channel without saving session files to disk, generate a Telethon `StringSession` once on your local computer:

```bash
# Activate virtual environment
.venv\Scripts\activate   # On Windows
# or: source .venv/bin/activate  # On Linux/macOS

# Run the generator
python scripts/generate_session.py
```

Follow the prompts to log in. Copy the resulting `TELEGRAM_SESSION` string.

---

### 3. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```env
API_ID=1234567
API_HASH=abcdef0123456789abcdef0123456789
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
CHANNEL_ID=-1001234567890
TELEGRAM_SESSION=1BVtsO...
AUTHORIZED_USER_ID=123456789

PORT=8080
LOG_LEVEL=INFO
```

---

### 4. Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Start TPMC
python -m app.main
```

Visit `http://localhost:8080/health` in your browser to inspect system health:
```json
{
  "status": "ok",
  "telegram": "connected",
  "bot": "connected",
  "index": "ready",
  "tracks": 42
}
```

---

### 5. Running the Test Suite

Run the full automated test suite using `pytest`:

```bash
pytest -v
```

---

## 🌐 Deploying to Render Free Web Service

1. Push this repository to a **Private GitHub Repository**.
2. Log into [Render Dashboard](https://dashboard.render.com).
3. Click **New +** $\rightarrow$ **Blueprint**.
4. Connect your private repository. Render will automatically detect [`render.yaml`](file:///c:/Users/heysa/Documents/Dev/telegram%20music%20manager/render.yaml).
5. In the Render service settings, populate the required secret environment variables:
   - `API_ID`
   - `API_HASH`
   - `BOT_TOKEN`
   - `CHANNEL_ID`
   - `TELEGRAM_SESSION`
   - `AUTHORIZED_USER_ID`
6. Click **Apply**. Render will install dependencies, launch `python -m app.main`, and register the `/health` check path.

> [!TIP]
> **Render Free Tier Spin-Down:**
> When Render suspends your service after 15 minutes of inactivity, incoming web traffic or a new restart will wake it up automatically. Your music library remains safe in Telegram and the in-memory index will automatically rebuild in the background upon wake-up.

---

## 💬 Bot Commands & Usage

| Command | Description |
| :--- | :--- |
| `/start` | Welcome message and available commands list |
| `/help` | Detailed syntax and tagging instructions |
| `/status` | Real-time status of Telegram, Bot, Indexer, Jobs, and Render |
| `/library` | Summary of indexed tracks, artists, albums, and genres |
| `/search <query>` | Search library with interactive pagination and a `[Download Page]` button |
| `/download <query>` | Search and deliver matching audio tracks to your DM |
| `/download_all` | Bulk delivery request (requires confirmation: `/download_all confirm`) |
| `/cancel` | Gracefully stop any active delivery job |
| `/reindex` | Trigger a fresh rescan of your storage channel (requires `/reindex confirm`) |

---

## 🏷️ Recommended Channel Tagging Standard

When uploading music to your storage channel, include structured tags in the caption for rich search and indexing:

```text
#artist:linkin_park
#album:meteora
#genre:rock
#language:english
#year:2003
#favorite
```

### Search Examples:
- `/search rock` — Find songs with 'rock' anywhere in metadata or tags
- `/search artist:linkin_park` — Filter specifically by artist
- `/search album:meteora` — Filter specifically by album
- `/search #favorite` — Retrieve all songs marked as favorite
- `/download #rock` — Forward all rock tracks to your DM
