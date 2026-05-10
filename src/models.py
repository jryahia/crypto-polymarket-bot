"""SQLAlchemy ORM models for the Aether Trading Bot."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.utcnow()


class SoulProfile(Base):
    __tablename__ = "soul_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False, default="Aether")
    personality: Mapped[str] = mapped_column(Text, nullable=False)
    risk_tolerance: Mapped[float] = mapped_column(Float, nullable=False, default=0.3)
    max_position_size_usd: Mapped[float] = mapped_column(Float, nullable=False, default=1000.0)
    max_daily_loss_usd: Mapped[float] = mapped_column(Float, nullable=False, default=500.0)
    preferred_markets: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    avoided_markets: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    trading_hours: Mapped[str] = mapped_column(String(50), nullable=False, default="24/7")
    ethics: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    communication_style: Mapped[str] = mapped_column(Text, nullable=False)
    decision_philosophy: Mapped[str] = mapped_column(Text, nullable=False)
    core_beliefs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    watchlist: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    polymarket_categories: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now, onupdate=_now)


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    exchange: Mapped[str] = mapped_column(String(50), nullable=False)  # binance | polymarket
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # buy | sell | yes | no
    order_type: Mapped[str] = mapped_column(String(20), nullable=False)  # market | limit
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    take_profit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pnl_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")  # open | closed | cancelled
    exchange_order_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    skill_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    outcome_analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
    opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    current_price: Mapped[float] = mapped_column(Float, nullable=False)
    unrealized_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unrealized_pnl_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stop_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    take_profit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    trade_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("trades.id"), nullable=True)
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
    opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now, onupdate=_now)


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    market: Mapped[str] = mapped_column(String(200), nullable=False)
    symbol: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    prediction_text: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)  # up | down | yes | no | neutral
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    target_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    timeframe: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    outcome: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # correct | incorrect | partial | pending
    outcome_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    was_acted_on: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    trade_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    lesson_type: Mapped[str] = mapped_column(String(50), nullable=False)  # success | failure | observation | pattern
    market_context: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    related_trade_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=5)  # 1-10
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    chroma_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # ChromaDB document ID
    times_recalled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now, onupdate=_now)


class MarketObservation(Base):
    __tablename__ = "market_observations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    exchange: Mapped[str] = mapped_column(String(50), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    volume_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    change_1h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    change_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rsi_14: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    macd_signal: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # bullish | bearish | neutral
    market_cap: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    indicators: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)  # price | rsi | volume | custom
    symbol: Mapped[str] = mapped_column(String(50), nullable=False)
    condition: Mapped[str] = mapped_column(String(50), nullable=False)  # above | below | cross_up | cross_down
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    triggered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_triggered: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class BrainCycle(Base):
    __tablename__ = "brain_cycles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    cycle_number: Mapped[int] = mapped_column(Integer, nullable=False)
    soul_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    market_context: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    memories_used: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    llm_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    llm_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action_taken: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    action_params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    action_result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    executed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    llm_provider_used: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class SkillExecution(Base):
    __tablename__ = "skill_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    skill_name: Mapped[str] = mapped_column(String(100), nullable=False)
    params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    brain_cycle_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    session_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
