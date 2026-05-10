"""Place a spot trade on Binance."""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.config import get_settings
from src.exchanges.binance_client import get_binance_client
from src.memory import get_memory_orchestrator

settings = get_settings()

DESCRIPTION = "Place a buy or sell order on Binance spot market (paper or live based on ENABLE_LIVE_TRADING)"
PARAMS = {
    "symbol": "str — trading pair e.g. BTCUSDT",
    "side": "str — buy or sell",
    "quantity": "float — amount of base asset to trade",
    "order_type": "str — market or limit (default: market)",
    "price": "float — limit price, required for limit orders",
    "stop_loss": "float — optional stop loss price",
    "take_profit": "float — optional take profit price",
    "reasoning": "str — reason for the trade",
}
RETURNS = "dict with order details and database trade ID"


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    symbol = params.get("symbol", "").upper()
    side = params.get("side", "").lower()
    quantity = float(params.get("quantity", 0))
    order_type = params.get("order_type", "market").lower()
    price = params.get("price")
    stop_loss = params.get("stop_loss")
    take_profit = params.get("take_profit")
    reasoning = params.get("reasoning", "")

    if not symbol:
        return {"error": "symbol is required"}
    if side not in ("buy", "sell"):
        return {"error": "side must be 'buy' or 'sell'"}
    if quantity <= 0:
        return {"error": "quantity must be > 0"}

    client = get_binance_client()
    try:
        current_price = await client.get_price(symbol)
    except Exception as exc:
        return {"error": f"Failed to get price for {symbol}: {exc}"}

    trade_value = quantity * (float(price) if price else current_price)
    if trade_value > settings.max_position_size_usd:
        return {
            "error": (
                f"Trade value ${trade_value:.2f} exceeds max position size "
                f"${settings.max_position_size_usd:.2f}"
            ),
            "blocked": True,
        }

    try:
        if order_type == "limit" and price:
            order = await client.place_limit_order(
                symbol=symbol, side=side.upper(), quantity=quantity, price=float(price)
            )
        else:
            order = await client.place_market_order(
                symbol=symbol, side=side.upper(), quantity=quantity
            )
    except Exception as exc:
        logger.error(f"place_trade: order failed {symbol}: {exc}")
        return {"error": str(exc), "symbol": symbol}

    trade_db_id = None
    try:
        memory = get_memory_orchestrator()
        trade_db_id = await memory.long_term.save_trade({
            "exchange": "binance",
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "quantity": quantity,
            "entry_price": float(price) if price else current_price,
            "stop_loss": float(stop_loss) if stop_loss else None,
            "take_profit": float(take_profit) if take_profit else None,
            "reasoning": reasoning,
            "status": "open",
            "exchange_order_id": str(order.get("orderId", "")),
            "skill_used": "place_trade",
        })
        memory.short_term.update_market_price(symbol, current_price)
    except Exception as e:
        logger.warning(f"place_trade: DB save failed: {e}")

    logger.info(
        f"place_trade: {side.upper()} {quantity} {symbol} @ {price or current_price:.4f} "
        f"| paper={order.get('paper_trade', not settings.enable_live_trading)}"
    )
    return {
        "success": True,
        "order": order,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "price": float(price) if price else current_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "trade_db_id": trade_db_id,
        "paper_trade": order.get("paper_trade", not settings.enable_live_trading),
    }
