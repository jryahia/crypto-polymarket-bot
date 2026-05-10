# Aether — Autonomous Crypto & Polymarket Trading Bot

An autonomous AI trading agent that reasons, learns, and executes trades across Binance spot markets and Polymarket prediction markets. Powered by GPT-4o (with Anthropic fallback), equipped with a semantic memory system, and controlled via a Flet dark-theme desktop UI.

---

## Architecture

```
main.py
├── FastAPI (uvicorn background thread)          → REST API on :8000
├── APScheduler                                  → Brain cycle every 5 min
└── Flet Desktop UI                              → Dark-theme control panel

src/
├── brain.py          LLM reasoning cycle orchestrator
├── scheduler.py      APScheduler wrapper with pause/resume
├── api_server.py     FastAPI endpoints
├── soul_manager.py   Bot personality / identity management
├── memory.py         3-tier memory: short-term / SQL / ChromaDB
├── memory_store.py   ChromaDB semantic vector store
├── llm_provider.py   OpenAI + Anthropic with auto-fallback
├── alerts.py         Price alerts and email notifications
├── config.py         Pydantic settings (env-based)
├── database.py       Async SQLAlchemy (SQLite/PostgreSQL)
├── models.py         ORM models
├── schemas.py        Pydantic v2 request/response schemas
├── exchanges/
│   ├── binance_client.py     Spot trading, OHLCV, WebSocket
│   └── polymarket_client.py  Prediction market CLOB API
└── ui/
    ├── app.py           Navigation shell
    ├── dashboard.py     Live portfolio & cycle overview
    ├── chat_view.py     Direct conversation with the bot
    ├── soul_view.py     Edit bot personality
    ├── skills_view.py   Browse and execute skills
    ├── memory_view.py   Search semantic memory & lessons
    ├── scanner_view.py  Market opportunity scanner
    └── analytics_view.py  Trade history & performance

skills/
├── loader.py              Dynamic skill discovery & hot-reload
├── analyze_market.py      RSI, MACD, Bollinger Bands analysis
├── check_polymarket.py    Scan prediction markets for edges
├── place_trade.py         Execute Binance spot orders
├── place_polymarket_bet.py Execute Polymarket bets
├── get_portfolio.py       Fetch balances & positions
├── research_news.py       CryptoPanic + NewsAPI sentiment
├── scan_opportunities.py  Watchlist-wide signal scanner
├── set_alert.py           Create price/RSI alerts
├── backtest_strategy.py   RSI+MACD strategy backtest
├── risk_assessment.py     Position sizing & risk checks
├── send_report.py         Generate & email P&L reports
└── learn_lesson.py        Save insights to semantic memory
```

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — at minimum set:
# OPENAI_API_KEY or ANTHROPIC_API_KEY
# BINANCE_API_KEY + BINANCE_API_SECRET (testnet recommended)
```

### 3. Run (full mode with desktop UI)

```bash
python main.py
```

### 4. Run (API-only, for servers)

```bash
python main.py --api-only
```

### 5. Docker

```bash
docker-compose up -d
```

---

## Configuration

| Variable | Description | Default |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API key | — |
| `ANTHROPIC_API_KEY` | Anthropic API key (fallback) | — |
| `BINANCE_API_KEY` | Binance API key | — |
| `BINANCE_TESTNET` | Use testnet for paper trading | `true` |
| `ENABLE_LIVE_TRADING` | Master switch for real orders | `false` |
| `BRAIN_CYCLE_INTERVAL_SECONDS` | How often the LLM reasons | `300` |
| `CONFIDENCE_THRESHOLD` | Min confidence to execute a trade | `0.65` |
| `MAX_POSITION_SIZE_USD` | Max single position size | `1000` |
| `DAILY_LOSS_LIMIT_USD` | Stop trading after this daily loss | `500` |
| `DATABASE_URL` | SQLAlchemy async URL | SQLite |
| `CHROMA_PERSIST_DIR` | ChromaDB local storage path | `./data/chroma` |

---

## REST API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/api/status` | Bot status, cycle count, P&L |
| `POST` | `/api/cycle/run` | Trigger brain cycle immediately |
| `POST` | `/api/chat` | Chat with the bot's soul |
| `GET` | `/api/trades` | Trade history |
| `GET` | `/api/lessons` | Stored lessons |
| `GET` | `/api/portfolio` | Full portfolio snapshot |
| `GET` | `/api/soul` | Current soul profile |
| `POST` | `/api/soul/update` | Update personality/risk params |
| `GET` | `/api/skills` | List available skills |
| `POST` | `/api/skills/{name}/execute` | Execute a skill manually |
| `POST` | `/api/skills/install` | Install a new skill from code |
| `GET` | `/api/polymarket/markets` | Fetch Polymarket markets |
| `POST` | `/api/polymarket/bet` | Place a Polymarket bet |
| `POST` | `/api/memory/search` | Semantic memory search |
| `POST` | `/api/alerts` | Create a price alert |
| `GET` | `/api/brain/cycles` | Brain cycle history |

Interactive docs: `http://localhost:8000/docs`

---

## Brain Cycle

Every 5 minutes (configurable), the bot:

1. **Loads soul** — personality, risk limits, watchlist
2. **Assembles memory context** — short-term state, recent trades, top 3 semantic matches from ChromaDB
3. **Lists skills** — all available execute() modules
4. **Calls LLM** — GPT-4o with automatic Anthropic fallback
5. **Parses response** — `{reasoning, action, params, confidence}`
6. **Executes skill** — if confidence ≥ threshold (default 0.65)
7. **Saves to memory** — brain cycle logged to SQL, auto-observations to ChromaDB

---

## Custom Skills

Drop a `.py` file into `skills/` with:

```python
DESCRIPTION = "What this skill does"
PARAMS = {"symbol": "str — e.g. BTCUSDT"}
RETURNS = "dict description"

async def execute(params: dict) -> dict:
    # your implementation
    return {"result": ...}
```

The loader picks it up automatically on the next cycle. Hot-reload via `POST /api/skills/install`.

---

## Soul Profile

Edit `soul/profile.json` or use the UI Soul tab / `POST /api/soul/update` to change:

- **personality** — how the bot describes itself and reasons
- **risk_tolerance** — 0.0 (no risk) to 1.0 (max risk)
- **max_position_size_usd** — hard limit per trade
- **max_daily_loss_usd** — circuit breaker
- **watchlist** — symbols to scan each cycle
- **ethics** — constraints the bot must follow
- **decision_philosophy** — guides LLM reasoning

---

## Safety

- `ENABLE_LIVE_TRADING=false` by default → all orders are paper trades
- Confidence threshold blocks low-conviction actions
- Daily loss limit halts trading
- Position size hard cap per trade
- All reasoning logged to SQLite for audit
