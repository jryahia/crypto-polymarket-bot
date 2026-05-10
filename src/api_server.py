"""FastAPI server with all REST endpoints for the trading bot."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from sqlalchemy import desc, select
from pydantic import BaseModel

from src.config import get_settings
from src.database import get_db, init_db, health_check, get_session
from src.memory import get_memory_orchestrator
from src.models import BrainCycle, ChatMessage, Lesson, Position, Trade
from src.schemas import (
    AlertCreate,
    AlertSchema,
    BotStatusResponse,
    ChatRequest,
    ChatResponse,
    CycleRunResponse,
    LessonCreate,
    LessonSchema,
    MemorySearchRequest,
    MemorySearchResponse,
    MemorySearchResult,
    PlaceBetRequest,
    PolymarketMarket,
    PortfolioResponse,
    PositionSchema,
    SkillInfo,
    SoulProfileSchema,
    SoulProfileUpdate,
    TradeSchema,
)
from src.soul_manager import get_soul_manager

settings = get_settings()

app = FastAPI(
    title="Aether Trading Bot API",
    description="Autonomous crypto and prediction market trading agent",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_startup_time = datetime.utcnow()


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()
    soul_manager = get_soul_manager()
    await soul_manager.ensure_soul_exists()
    logger.info("API server started")


@app.get("/health")
async def health() -> dict[str, Any]:
    db_ok = await health_check()
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "ok" if db_ok else "error",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/status", response_model=BotStatusResponse)
async def get_status() -> BotStatusResponse:
    from src.brain import get_brain
    from src.scheduler import get_scheduler

    brain_status = get_brain().get_status()
    scheduler_status = get_scheduler().get_status()
    memory = get_memory_orchestrator()
    open_positions = await memory.long_term.get_open_positions()
    state = memory.short_term.get_state_snapshot()

    bot_status = "paused" if scheduler_status.get("paused") else "running"
    uptime = (datetime.utcnow() - _startup_time).total_seconds()

    next_cycle = None
    if scheduler_status.get("next_run"):
        try:
            next_cycle = datetime.fromisoformat(scheduler_status["next_run"].replace("Z", "+00:00"))
        except Exception:
            pass

    last_cycle = None
    if brain_status.get("last_cycle_at"):
        try:
            last_cycle = datetime.fromisoformat(brain_status["last_cycle_at"])
        except Exception:
            pass

    return BotStatusResponse(
        status=bot_status,
        cycle_count=brain_status.get("cycle_count", 0),
        last_cycle_at=last_cycle,
        next_cycle_at=next_cycle,
        current_action=brain_status.get("current_action"),
        uptime_seconds=uptime,
        live_trading_enabled=settings.enable_live_trading,
        positions_count=len(open_positions),
        daily_pnl_usd=float(state.get("daily_pnl", 0)),
    )


@app.post("/api/cycle/run", response_model=CycleRunResponse)
async def run_cycle_now() -> CycleRunResponse:
    from src.brain import get_brain
    brain = get_brain()
    try:
        result = await brain.run_cycle()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return CycleRunResponse(
        cycle_id=result.get("cycle_id", str(uuid.uuid4())),
        reasoning=result.get("reasoning", ""),
        action=result.get("action"),
        params=result.get("params", {}),
        confidence=result.get("confidence", 0.0),
        executed=result.get("executed", False),
        result=result.get("result", {}),
        duration_ms=result.get("duration_ms", 0),
        tokens_used=result.get("tokens_used", 0),
        provider=result.get("provider", ""),
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    from src.llm_provider import get_llm_provider

    session_id = request.session_id or str(uuid.uuid4())
    soul_manager = get_soul_manager()
    soul = await soul_manager.load_soul()
    system = soul_manager.build_soul_prompt(soul)

    memory = get_memory_orchestrator()
    recent_reasoning = memory.short_term.get_recent_reasoning(3)
    context = "\n".join(recent_reasoning)
    full_system = (
        f"{system}\n\nYou are in direct conversation with your operator. "
        f"Recent context:\n{context}" if context else system
    )

    llm = get_llm_provider()
    try:
        response = await llm.generate(
            messages=[{"role": "user", "content": request.message}],
            system=full_system,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"LLM unavailable: {exc}")

    async with get_session() as session:
        session.add(ChatMessage(
            role="user",
            content=request.message,
            session_id=session_id,
        ))
        session.add(ChatMessage(
            role="assistant",
            content=response.content,
            session_id=session_id,
            tokens_used=response.tokens_used,
        ))
        await session.commit()

    return ChatResponse(
        response=response.content,
        session_id=session_id,
        tokens_used=response.tokens_used,
    )


@app.get("/api/trades")
async def get_trades(limit: int = 50, status: Optional[str] = None) -> list[dict[str, Any]]:
    async with get_session() as session:
        query = select(Trade).order_by(desc(Trade.created_at)).limit(limit)
        if status:
            query = query.where(Trade.status == status)
        result = await session.execute(query)
        trades = result.scalars().all()
        return [
            {
                "id": t.id,
                "exchange": t.exchange,
                "symbol": t.symbol,
                "side": t.side,
                "order_type": t.order_type,
                "quantity": t.quantity,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl_usd": t.pnl_usd,
                "pnl_pct": t.pnl_pct,
                "status": t.status,
                "reasoning": t.reasoning,
                "confidence": t.confidence,
                "skill_used": t.skill_used,
                "opened_at": t.opened_at.isoformat() if t.opened_at else None,
                "closed_at": t.closed_at.isoformat() if t.closed_at else None,
            }
            for t in trades
        ]


@app.get("/api/lessons")
async def get_lessons(limit: int = 30) -> list[dict[str, Any]]:
    memory = get_memory_orchestrator()
    lessons = await memory.long_term.get_lessons(limit)
    return [l.model_dump() for l in lessons]


@app.post("/api/lessons")
async def create_lesson(data: LessonCreate) -> LessonSchema:
    memory = get_memory_orchestrator()
    try:
        return await memory.long_term.save_lesson(data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/skills/install")
async def install_skill(name: str, code: str) -> dict[str, Any]:
    from skills.loader import get_skill_loader
    loader = get_skill_loader()
    success = loader.install_skill(name, code)
    return {"success": success, "skill": name}


@app.get("/api/skills")
async def list_skills() -> list[dict[str, Any]]:
    from skills.loader import get_skill_loader
    loader = get_skill_loader()
    return loader.get_skill_list()


@app.post("/api/skills/{skill_name}/execute")
async def execute_skill(skill_name: str, params: dict[str, Any] = {}) -> dict[str, Any]:
    from skills.loader import get_skill_loader
    loader = get_skill_loader()
    try:
        return await loader.execute_skill(skill_name, params)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/polymarket/markets")
async def get_polymarket_markets(
    category: Optional[str] = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    from src.exchanges.polymarket_client import get_polymarket_client
    client = get_polymarket_client()
    try:
        return await client.get_markets(category=category, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@app.post("/api/polymarket/bet")
async def place_polymarket_bet(request: PlaceBetRequest) -> dict[str, Any]:
    from skills.loader import get_skill_loader
    loader = get_skill_loader()
    try:
        return await loader.execute_skill("place_polymarket_bet", {
            "condition_id": request.condition_id,
            "outcome": request.outcome,
            "amount_usd": request.amount_usd,
            "price": request.price,
            "reasoning": "Manual bet via API",
        })
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/portfolio")
async def get_portfolio() -> dict[str, Any]:
    from skills.loader import get_skill_loader
    loader = get_skill_loader()
    try:
        return await loader.execute_skill("get_portfolio", {})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/soul", response_model=SoulProfileSchema)
async def get_soul() -> SoulProfileSchema:
    return await get_soul_manager().load_soul()


@app.post("/api/soul/update", response_model=SoulProfileSchema)
async def update_soul(updates: SoulProfileUpdate) -> SoulProfileSchema:
    try:
        return await get_soul_manager().update_soul(updates)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/api/memory/search", response_model=MemorySearchResponse)
async def search_memory(request: MemorySearchRequest) -> MemorySearchResponse:
    from src.memory_store import get_memory_store
    store = get_memory_store()
    raw_results = store.search_memories(
        query=request.query,
        n_results=request.n_results,
        collection=request.collection,
    )
    results = [
        MemorySearchResult(
            id=str(i),
            content=r.get("content", ""),
            metadata=r.get("metadata", {}),
            distance=r.get("distance", 0.0),
        )
        for i, r in enumerate(raw_results)
    ]
    return MemorySearchResponse(
        results=results,
        query=request.query,
        collection=request.collection,
    )


@app.post("/api/scheduler/pause")
async def pause_scheduler() -> dict[str, str]:
    from src.scheduler import get_scheduler
    get_scheduler().pause()
    return {"status": "paused"}


@app.post("/api/scheduler/resume")
async def resume_scheduler() -> dict[str, str]:
    from src.scheduler import get_scheduler
    get_scheduler().resume()
    return {"status": "resumed"}


@app.post("/api/alerts")
async def create_alert(data: AlertCreate) -> AlertSchema:
    from src.alerts import get_alert_manager
    return await get_alert_manager().create_alert(data)


@app.get("/api/alerts")
async def get_alerts() -> list[AlertSchema]:
    from src.alerts import get_alert_manager
    return await get_alert_manager().get_active_alerts()


@app.get("/api/brain/cycles")
async def get_brain_cycles(limit: int = 20) -> list[dict[str, Any]]:
    async with get_session() as session:
        result = await session.execute(
            select(BrainCycle).order_by(desc(BrainCycle.started_at)).limit(limit)
        )
        cycles = result.scalars().all()
        return [
            {
                "id": c.id,
                "cycle_number": c.cycle_number,
                "reasoning": (c.reasoning or "")[:300],
                "action_taken": c.action_taken,
                "confidence": c.confidence,
                "executed": c.executed,
                "llm_provider_used": c.llm_provider_used,
                "tokens_used": c.tokens_used,
                "duration_ms": c.duration_ms,
                "error": c.error,
                "started_at": c.started_at.isoformat() if c.started_at else None,
            }
            for c in cycles
        ]
