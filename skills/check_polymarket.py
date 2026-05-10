"""Scan Polymarket prediction markets for opportunities."""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.exchanges.polymarket_client import get_polymarket_client

DESCRIPTION = "Scan Polymarket prediction markets for trading opportunities based on pricing anomalies"
PARAMS = {
    "category": "str — optional category filter: crypto, economics, politics, science",
    "limit": "int — max markets to return (default: 20)",
    "min_volume": "float — minimum 24h volume in USD (default: 1000)",
}
RETURNS = "dict with markets list and top opportunities scored by edge"


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    category = params.get("category")
    limit = int(params.get("limit", 20))
    min_volume = float(params.get("min_volume", 1000))

    client = get_polymarket_client()
    try:
        markets = await client.get_markets(category=category, limit=limit * 2)
    except Exception as exc:
        logger.error(f"check_polymarket: fetch failed: {exc}")
        return {"error": str(exc), "markets": []}

    markets = [m for m in markets if m.get("volume", 0) >= min_volume]

    opportunities = []
    for m in markets:
        yes_price = m.get("yes_price", 0.5)
        volume = m.get("volume", 0)
        liquidity = m.get("liquidity", 0)

        edge_score = 0.0
        recommendation = "skip"
        side = None

        if yes_price < 0.15:
            edge_score = (0.15 - yes_price) * 10
            recommendation = "bet_no"
            side = "no"
        elif yes_price > 0.85:
            edge_score = (yes_price - 0.85) * 10
            recommendation = "bet_yes"
            side = "yes"
        elif 0.35 < yes_price < 0.65:
            edge_score = 0.1
            recommendation = "research"

        if liquidity > 10000:
            edge_score *= 1.2
        if volume > 100000:
            edge_score *= 1.1

        opportunities.append({
            **m,
            "edge_score": round(edge_score, 3),
            "recommendation": recommendation,
            "suggested_side": side,
        })

    opportunities.sort(key=lambda x: x["edge_score"], reverse=True)
    top = opportunities[:limit]

    top_q = top[0]["question"][:60] if top else "none"
    logger.info(f"check_polymarket: {len(markets)} markets found, top: {top_q}")

    return {
        "total_markets": len(markets),
        "markets": top,
        "top_opportunities": [o for o in top if o["edge_score"] > 0.5][:5],
    }
