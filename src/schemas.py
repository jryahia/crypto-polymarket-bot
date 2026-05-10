"""Pydantic v2 schemas for request/response validation."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class SoulProfileSchema(BaseModel):
    id: Optional[str] = None
    name: str = "Aether"
    personality: str
    risk_tolerance: float = Field(ge=0.0, le=1.0, default=0.3)
    max_position_size_usd: float = Field(gt=0, default=1000.0)
    max_daily_loss_usd: float = Field(gt=0, default=500.0)
    preferred_markets: list[str] = []
    avoided_markets: list[str] = []
    trading_hours: str = "24/7"
    ethics: list[str] = []
    communication_style: str = ""
    decision_philosophy: str = ""
    core_beliefs: list[str] = []
    watchlist: list[str] = []
    polymarket_categories: list[str] = []
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SoulProfileUpdate(BaseModel):
    name: Optional[str] = None
    personality: Optional[str] = None
    risk_tolerance: Optional[float] = Field(None, ge=0.0, le=1.0)
    max_position_size_usd: Optional[float] = Field(None, gt=0)
    max_daily_loss_usd: Optional[float] = Field(None, gt=0)
    preferred_markets: Optional[list[str]] = None
    avoided_markets: Optional[list[str]] = None
    trading_hours: Optional[str] = None
    ethics: Optional[list[str]] = None
    communication_style: Optional[str] = None
    decision_philosophy: Optional[str] = None
    core_beliefs: Optional[list[str]] = None
    watchlist: Optional[list[str]] = None
    polymarket_categories: Optional[list[str]] = None


class TradeSchema(BaseModel):
    id: Optional[str] = None
    exchange: str
    symbol: str
    side: str
    order_type: str = "market"
    quantity: float
    entry_price: float
    exit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    pnl_usd: Optional[float] = None
    pnl_pct: Optional[float] = None
    status: str = "open"
    exchange_order_id: Optional[str] = None
    reasoning: Optional[str] = None
    confidence: Optional[float] = None
    skill_used: Optional[str] = None
    outcome_analysis: Optional[str] = None
    metadata_: dict[str, Any] = Field(default_factory=dict, alias="metadata")
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
        populate_by_name = True


class PositionSchema(BaseModel):
    id: Optional[str] = None
    exchange: str
    symbol: str
    side: str
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trade_id: Optional[str] = None
    is_open: bool = True
    opened_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LessonSchema(BaseModel):
    id: Optional[str] = None
    title: str
    content: str
    lesson_type: str = "observation"
    market_context: Optional[str] = None
    related_trade_id: Optional[str] = None
    importance: int = Field(ge=1, le=10, default=5)
    tags: list[str] = []
    chroma_id: Optional[str] = None
    times_recalled: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LessonCreate(BaseModel):
    title: str
    content: str
    lesson_type: str = "observation"
    market_context: Optional[str] = None
    related_trade_id: Optional[str] = None
    importance: int = Field(ge=1, le=10, default=5)
    tags: list[str] = []


class AlertSchema(BaseModel):
    id: Optional[str] = None
    alert_type: str
    symbol: str
    condition: str
    threshold: float
    message: Optional[str] = None
    is_active: bool = True
    triggered_count: int = 0
    last_triggered: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AlertCreate(BaseModel):
    alert_type: str = "price"
    symbol: str
    condition: str
    threshold: float
    message: Optional[str] = None


class BrainCycleSchema(BaseModel):
    id: Optional[str] = None
    cycle_number: int
    reasoning: Optional[str] = None
    action_taken: Optional[str] = None
    action_params: dict[str, Any] = {}
    action_result: dict[str, Any] = {}
    confidence: Optional[float] = None
    executed: bool = False
    llm_provider_used: Optional[str] = None
    tokens_used: int = 0
    duration_ms: int = 0
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ChatMessageSchema(BaseModel):
    id: Optional[str] = None
    role: str
    content: str
    session_id: Optional[str] = None
    tokens_used: int = 0
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    tokens_used: int = 0


class MemorySearchRequest(BaseModel):
    query: str
    n_results: int = Field(ge=1, le=20, default=5)
    collection: str = "lessons"


class MemorySearchResult(BaseModel):
    id: str
    content: str
    metadata: dict[str, Any] = {}
    distance: float = 0.0


class MemorySearchResponse(BaseModel):
    results: list[MemorySearchResult]
    query: str
    collection: str


class PortfolioResponse(BaseModel):
    total_value_usd: float
    available_balance_usd: float
    positions: list[PositionSchema]
    total_pnl_usd: float
    total_pnl_pct: float
    daily_pnl_usd: float
    exchange_balances: dict[str, float]
    last_updated: datetime


class MarketSnapshot(BaseModel):
    symbol: str
    price: float
    change_1h: Optional[float] = None
    change_24h: Optional[float] = None
    volume_24h: Optional[float] = None
    rsi_14: Optional[float] = None
    macd_signal: Optional[str] = None
    trend: Optional[str] = None
    indicators: dict[str, Any] = {}


class BotStatusResponse(BaseModel):
    status: str  # running | paused | error
    cycle_count: int
    last_cycle_at: Optional[datetime] = None
    next_cycle_at: Optional[datetime] = None
    current_action: Optional[str] = None
    uptime_seconds: float = 0.0
    live_trading_enabled: bool = False
    positions_count: int = 0
    daily_pnl_usd: float = 0.0


class PolymarketMarket(BaseModel):
    condition_id: str
    question: str
    category: Optional[str] = None
    volume: float = 0.0
    liquidity: float = 0.0
    yes_price: float = 0.5
    no_price: float = 0.5
    closing_date: Optional[str] = None
    is_resolved: bool = False
    outcome: Optional[str] = None
    description: Optional[str] = None


class PlaceBetRequest(BaseModel):
    condition_id: str
    outcome: str  # yes | no
    amount_usd: float = Field(gt=0)
    price: Optional[float] = Field(None, ge=0.01, le=0.99)


class SkillInfo(BaseModel):
    name: str
    description: str
    params: dict[str, Any] = {}
    returns: str = "dict"
    is_enabled: bool = True
    last_executed: Optional[datetime] = None
    execution_count: int = 0


class CycleRunResponse(BaseModel):
    cycle_id: str
    reasoning: str
    action: Optional[str] = None
    params: dict[str, Any] = {}
    confidence: float = 0.0
    executed: bool = False
    result: dict[str, Any] = {}
    duration_ms: int = 0
    tokens_used: int = 0
    provider: str = ""
