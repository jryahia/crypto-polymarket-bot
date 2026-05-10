"""Three-tier memory system: short-term (in-memory), long-term (SQL), semantic (ChromaDB)."""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Optional

from loguru import logger
from sqlalchemy import desc, select

from src.config import get_settings
from src.database import get_session
from src.memory_store import get_memory_store
from src.models import BrainCycle, Lesson, MarketObservation, Position, Trade
from src.schemas import LessonCreate, LessonSchema

settings = get_settings()


class ShortTermMemory:
    """In-memory working memory for the current session."""

    def __init__(self, max_observations: int = 100) -> None:
        self._state: dict[str, Any] = {}
        self._price_history: dict[str, deque[dict[str, Any]]] = {}
        self._recent_reasoning: deque[str] = deque(maxlen=10)
        self._max_observations = max_observations

    def update_market_price(self, symbol: str, price: float, timestamp: Optional[datetime] = None) -> None:
        ts = timestamp or datetime.utcnow()
        if symbol not in self._price_history:
            self._price_history[symbol] = deque(maxlen=self._max_observations)
        self._price_history[symbol].append({"price": price, "ts": ts.isoformat()})

    def get_price_history(self, symbol: str, minutes: int = 60) -> list[dict[str, Any]]:
        if symbol not in self._price_history:
            return []
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        return [
            p for p in self._price_history[symbol]
            if datetime.fromisoformat(p["ts"]) >= cutoff
        ]

    def set(self, key: str, value: Any) -> None:
        self._state[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)

    def add_reasoning(self, text: str) -> None:
        self._recent_reasoning.appendleft(text)

    def get_recent_reasoning(self, n: int = 3) -> list[str]:
        return list(self._recent_reasoning)[:n]

    def get_state_snapshot(self) -> dict[str, Any]:
        return {
            "positions": self._state.get("positions", []),
            "balances": self._state.get("balances", {}),
            "open_alerts": self._state.get("open_alerts", []),
            "market_prices": {
                sym: list(hist)[-1] if hist else {}
                for sym, hist in self._price_history.items()
            },
            "last_cycle_at": self._state.get("last_cycle_at"),
            "cycle_count": self._state.get("cycle_count", 0),
            "daily_pnl": self._state.get("daily_pnl", 0.0),
            "bot_status": self._state.get("bot_status", "running"),
        }


class LongTermMemory:
    """SQL-backed episodic memory for past trades, predictions, and lessons."""

    async def get_recent_trades(self, limit: int = 10) -> list[dict[str, Any]]:
        async with get_session() as session:
            result = await session.execute(
                select(Trade).order_by(desc(Trade.created_at)).limit(limit)
            )
            trades = result.scalars().all()
            return [
                {
                    "id": t.id,
                    "symbol": t.symbol,
                    "side": t.side,
                    "pnl_usd": t.pnl_usd,
                    "status": t.status,
                    "reasoning": t.reasoning,
                    "opened_at": t.opened_at.isoformat() if t.opened_at else None,
                }
                for t in trades
            ]

    async def get_open_positions(self) -> list[dict[str, Any]]:
        async with get_session() as session:
            result = await session.execute(
                select(Position).where(Position.is_open.is_(True))
            )
            positions = result.scalars().all()
            return [
                {
                    "id": p.id,
                    "exchange": p.exchange,
                    "symbol": p.symbol,
                    "side": p.side,
                    "quantity": p.quantity,
                    "entry_price": p.entry_price,
                    "current_price": p.current_price,
                    "unrealized_pnl": p.unrealized_pnl,
                    "unrealized_pnl_pct": p.unrealized_pnl_pct,
                }
                for p in positions
            ]

    async def get_lessons(self, limit: int = 20) -> list[LessonSchema]:
        async with get_session() as session:
            result = await session.execute(
                select(Lesson).order_by(desc(Lesson.importance), desc(Lesson.created_at)).limit(limit)
            )
            lessons = result.scalars().all()
            return [LessonSchema.model_validate(l) for l in lessons]

    async def save_lesson(self, lesson_data: LessonCreate) -> LessonSchema:
        memory_store = get_memory_store()
        async with get_session() as session:
            chroma_id = memory_store.add_lesson(
                title=lesson_data.title,
                content=lesson_data.content,
                metadata={
                    "lesson_type": lesson_data.lesson_type,
                    "market_context": lesson_data.market_context or "",
                    "importance": lesson_data.importance,
                    "tags": ",".join(lesson_data.tags),
                },
            )
            lesson = Lesson(
                title=lesson_data.title,
                content=lesson_data.content,
                lesson_type=lesson_data.lesson_type,
                market_context=lesson_data.market_context,
                related_trade_id=lesson_data.related_trade_id,
                importance=lesson_data.importance,
                tags=lesson_data.tags,
                chroma_id=chroma_id,
            )
            session.add(lesson)
            await session.commit()
            await session.refresh(lesson)
            logger.info(f"Lesson saved: {lesson.title}")
            return LessonSchema.model_validate(lesson)

    async def save_trade(self, trade_data: dict[str, Any]) -> str:
        async with get_session() as session:
            trade = Trade(**trade_data)
            session.add(trade)
            await session.commit()
            await session.refresh(trade)
            return trade.id

    async def close_trade(
        self,
        trade_id: str,
        exit_price: float,
        outcome_analysis: str,
    ) -> Optional[dict[str, Any]]:
        async with get_session() as session:
            result = await session.execute(select(Trade).where(Trade.id == trade_id))
            trade = result.scalars().first()
            if not trade:
                return None

            trade.exit_price = exit_price
            trade.status = "closed"
            trade.closed_at = datetime.utcnow()
            trade.outcome_analysis = outcome_analysis

            if trade.entry_price and exit_price:
                if trade.side == "buy":
                    trade.pnl_usd = (exit_price - trade.entry_price) * trade.quantity
                else:
                    trade.pnl_usd = (trade.entry_price - exit_price) * trade.quantity
                trade.pnl_pct = (trade.pnl_usd / (trade.entry_price * trade.quantity)) * 100

            await session.commit()

            # Store outcome in ChromaDB
            if trade.pnl_usd is not None:
                memory_store = get_memory_store()
                memory_store.add_trade_outcome(
                    symbol=trade.symbol,
                    side=trade.side,
                    pnl_usd=trade.pnl_usd,
                    reasoning=trade.reasoning or "",
                    outcome_analysis=outcome_analysis,
                )
            return {"id": trade.id, "pnl_usd": trade.pnl_usd}

    async def save_market_observation(self, symbol: str, data: dict[str, Any]) -> None:
        async with get_session() as session:
            obs = MarketObservation(
                symbol=symbol,
                exchange=data.get("exchange", "binance"),
                price=data.get("price", 0.0),
                volume_24h=data.get("volume_24h"),
                change_1h=data.get("change_1h"),
                change_24h=data.get("change_24h"),
                rsi_14=data.get("rsi_14"),
                macd_signal=data.get("macd_signal"),
                indicators=data.get("indicators", {}),
            )
            session.add(obs)
            await session.commit()

    async def get_last_brain_cycle(self) -> Optional[dict[str, Any]]:
        async with get_session() as session:
            result = await session.execute(
                select(BrainCycle).order_by(desc(BrainCycle.started_at)).limit(1)
            )
            cycle = result.scalars().first()
            if not cycle:
                return None
            return {
                "id": cycle.id,
                "cycle_number": cycle.cycle_number,
                "reasoning": cycle.reasoning,
                "action_taken": cycle.action_taken,
                "confidence": cycle.confidence,
                "executed": cycle.executed,
                "started_at": cycle.started_at.isoformat(),
            }

    async def save_brain_cycle(self, data: dict[str, Any]) -> str:
        async with get_session() as session:
            cycle = BrainCycle(**data)
            session.add(cycle)
            await session.commit()
            await session.refresh(cycle)
            return cycle.id

    async def compute_performance_stats(self) -> dict[str, Any]:
        async with get_session() as session:
            result = await session.execute(
                select(Trade).where(Trade.status == "closed")
            )
            closed_trades = result.scalars().all()

            if not closed_trades:
                return {
                    "total_trades": 0,
                    "win_rate": 0.0,
                    "total_pnl_usd": 0.0,
                    "avg_pnl_usd": 0.0,
                    "best_trade_usd": 0.0,
                    "worst_trade_usd": 0.0,
                    "profit_factor": 0.0,
                }

            pnls = [t.pnl_usd for t in closed_trades if t.pnl_usd is not None]
            wins = [p for p in pnls if p > 0]
            losses = [p for p in pnls if p < 0]

            gross_profit = sum(wins) if wins else 0.0
            gross_loss = abs(sum(losses)) if losses else 0.0
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

            return {
                "total_trades": len(closed_trades),
                "win_rate": len(wins) / len(pnls) if pnls else 0.0,
                "total_pnl_usd": sum(pnls),
                "avg_pnl_usd": sum(pnls) / len(pnls) if pnls else 0.0,
                "best_trade_usd": max(pnls) if pnls else 0.0,
                "worst_trade_usd": min(pnls) if pnls else 0.0,
                "profit_factor": profit_factor,
                "gross_profit": gross_profit,
                "gross_loss": gross_loss,
            }


class MemoryOrchestrator:
    """Coordinates all three memory tiers for the brain cycle."""

    def __init__(self) -> None:
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory()
        self.semantic = get_memory_store()

    async def get_context_for_cycle(self, watchlist: list[str]) -> dict[str, Any]:
        """Assemble full memory context for an LLM reasoning cycle."""
        state = self.short_term.get_state_snapshot()

        recent_trades = await self.long_term.get_recent_trades(5)
        open_positions = await self.long_term.get_open_positions()
        last_cycle = await self.long_term.get_last_brain_cycle()

        market_context = ", ".join(
            f"{sym}@{state['market_prices'].get(sym, {}).get('price', '?')}"
            for sym in watchlist[:5]
        )

        relevant_memories = self.semantic.search_relevant_past(
            f"market: {market_context}, positions: {len(open_positions)} open"
        )

        return {
            "short_term": state,
            "open_positions": open_positions,
            "recent_trades": recent_trades,
            "relevant_memories": relevant_memories,
            "last_reasoning": self.short_term.get_recent_reasoning(3),
            "last_cycle": last_cycle,
            "performance_stats": await self.long_term.compute_performance_stats(),
        }

    def format_context_for_llm(self, context: dict[str, Any]) -> str:
        """Format the memory context for injection into the LLM prompt."""
        positions = context.get("open_positions", [])
        trades = context.get("recent_trades", [])
        memories = context.get("relevant_memories", [])
        state = context.get("short_term", {})
        stats = context.get("performance_stats", {})

        positions_text = "\n".join(
            f"  {p['symbol']} {p['side'].upper()} qty={p['quantity']:.4f} "
            f"entry=${p['entry_price']:.4f} pnl={p['unrealized_pnl']:+.2f}$"
            for p in positions
        ) or "  None"

        trades_text = "\n".join(
            f"  {t.get('symbol')} {t.get('side')} pnl={t.get('pnl_usd') or 0:+.2f}$ [{t.get('status')}]"
            for t in trades
        ) or "  None"

        memories_text = "\n".join(
            f"  [{m.get('collection','?')}] {m.get('content','')[:200]}..."
            for m in memories
        ) or "  No relevant past experiences found"

        prices = state.get("market_prices", {})
        prices_text = ", ".join(
            f"{sym}: ${data.get('price', '?')}"
            for sym, data in list(prices.items())[:6]
        ) or "No price data"

        return f"""=== CURRENT STATE ===
Portfolio:
  Daily P&L: ${state.get('daily_pnl', 0):+.2f}
  Status: {state.get('bot_status', 'running')}
  Cycle #: {state.get('cycle_count', 0)}

Open Positions:
{positions_text}

Market Prices:
  {prices_text}

Recent Trades (last 5):
{trades_text}

Performance Stats:
  Trades: {stats.get('total_trades', 0)} | Win Rate: {stats.get('win_rate', 0):.1%}
  Total P&L: ${stats.get('total_pnl_usd', 0):+.2f} | Profit Factor: {stats.get('profit_factor', 0):.2f}

=== RELEVANT PAST EXPERIENCES ===
{memories_text}
=== END STATE ==="""


_orchestrator: Optional[MemoryOrchestrator] = None


def get_memory_orchestrator() -> MemoryOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MemoryOrchestrator()
    return _orchestrator
