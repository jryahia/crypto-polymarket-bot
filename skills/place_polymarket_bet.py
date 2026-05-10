"""Place a bet on a Polymarket prediction market."""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.config import get_settings
from src.exchanges.polymarket_client import get_polymarket_client
from src.memory import get_memory_orchestrator

settings = get_settings()

DESCRIPTION = "Place a YES or NO bet on a Polymarket prediction market (paper or live)"
PARAMS = {
    "condition_id": "str — market condition ID from Polymarket",
    "outcome": "str — yes or no",
    "amount_usd": "float — USD amount to bet",
    "price": "float — optional limit price (0.01–0.99), defaults to market price",
    "reasoning": "str — reasoning for the bet",
}
RETURNS = "dict with order ID, outcome, amount, and trade status"


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    condition_id = params.get("condition_id", "")
    outcome = params.get("outcome", "").lower()
    amount_usd = float(params.get("amount_usd", 0))
    price = params.get("price")
    reasoning = params.get("reasoning", "")

    if not condition_id:
        return {"error": "condition_id is required"}
    if outcome not in ("yes", "no"):
        return {"error": "outcome must be 'yes' or 'no'"}
    if amount_usd <= 0:
        return {"error": "amount_usd must be > 0"}
    if amount_usd > settings.max_position_size_usd:
        return {
            "error": f"Bet ${amount_usd:.2f} exceeds max position ${settings.max_position_size_usd:.2f}",
            "blocked": True,
        }

    client = get_polymarket_client()
    try:
        result = await client.place_bet(
            condition_id=condition_id,
            outcome=outcome,
            amount_usd=amount_usd,
            price=float(price) if price else None,
        )
    except Exception as exc:
        logger.error(f"place_polymarket_bet: bet failed: {exc}")
        return {"error": str(exc)}

    try:
        memory = get_memory_orchestrator()
        actual_price = result.get("price", float(price) if price else 0.5)
        await memory.long_term.save_trade({
            "exchange": "polymarket",
            "symbol": condition_id[:50],
            "side": outcome,
            "order_type": "limit",
            "quantity": amount_usd / actual_price if actual_price > 0 else 0,
            "entry_price": actual_price,
            "reasoning": reasoning,
            "status": "open",
            "exchange_order_id": str(result.get("order_id", "")),
            "skill_used": "place_polymarket_bet",
            "metadata_": {"condition_id": condition_id, "outcome": outcome},
        })
    except Exception as e:
        logger.warning(f"place_polymarket_bet: DB save failed: {e}")

    logger.info(
        f"place_polymarket_bet: {outcome.upper()} ${amount_usd:.2f} on {condition_id[:40]} "
        f"| paper={result.get('paper_trade', not settings.enable_live_trading)}"
    )
    return {
        "success": True,
        "order_id": result.get("order_id"),
        "condition_id": condition_id,
        "outcome": outcome,
        "amount_usd": amount_usd,
        "price": result.get("price"),
        "status": result.get("status"),
        "paper_trade": result.get("paper_trade", not settings.enable_live_trading),
    }
