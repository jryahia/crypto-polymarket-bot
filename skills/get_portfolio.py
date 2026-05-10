"""Get the current portfolio state across Binance and Polymarket."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger

from src.exchanges.binance_client import get_binance_client
from src.exchanges.polymarket_client import get_polymarket_client
from src.memory import get_memory_orchestrator

DESCRIPTION = "Fetch current portfolio balances, open positions, and P&L from Binance and Polymarket"
PARAMS = {}
RETURNS = "dict with total_value_usd, binance_balances, polymarket_positions, open_positions, daily_pnl"


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    binance = get_binance_client()
    poly = get_polymarket_client()
    memory = get_memory_orchestrator()

    binance_value = 0.0
    binance_balances: dict[str, float] = {}
    try:
        account = await binance.get_account()
        binance_balances = account.get("balances", {})
        binance_value = await binance.get_usdt_value()
    except Exception as exc:
        logger.warning(f"get_portfolio: Binance fetch failed: {exc}")

    poly_positions: list[dict[str, Any]] = []
    poly_value = 0.0
    try:
        poly_positions = await poly.get_positions()
        poly_value = sum(p.get("value", 0) for p in poly_positions)
    except Exception as exc:
        logger.warning(f"get_portfolio: Polymarket fetch failed: {exc}")

    open_positions = await memory.long_term.get_open_positions()
    stats = await memory.long_term.compute_performance_stats()

    total_value = binance_value + poly_value

    result = {
        "total_value_usd": round(total_value, 2),
        "binance_value_usd": round(binance_value, 2),
        "polymarket_value_usd": round(poly_value, 2),
        "binance_balances": {k: round(v, 6) for k, v in binance_balances.items()},
        "polymarket_positions": poly_positions,
        "open_positions": open_positions,
        "open_positions_count": len(open_positions),
        "performance": stats,
        "last_updated": datetime.utcnow().isoformat(),
    }

    memory.short_term.set("positions", open_positions)
    memory.short_term.set("balances", {"binance_usd": binance_value, "polymarket_usd": poly_value})

    logger.info(
        f"get_portfolio: total=${total_value:.2f} | binance=${binance_value:.2f} "
        f"| poly=${poly_value:.2f} | open_positions={len(open_positions)}"
    )
    return result
