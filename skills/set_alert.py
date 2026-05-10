"""Create a price or RSI alert for a symbol."""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.alerts import get_alert_manager
from src.schemas import AlertCreate

DESCRIPTION = "Create a price alert that triggers when a symbol crosses a threshold"
PARAMS = {
    "symbol": "str — trading pair e.g. BTCUSDT",
    "alert_type": "str — price, rsi, or volume (default: price)",
    "condition": "str — above or below",
    "threshold": "float — the trigger value",
    "message": "str — optional custom alert message",
}
RETURNS = "dict with created alert ID and details"


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    symbol = params.get("symbol", "").upper()
    alert_type = params.get("alert_type", "price")
    condition = params.get("condition", "").lower()
    threshold = params.get("threshold")
    message = params.get("message")

    if not symbol:
        return {"error": "symbol is required"}
    if condition not in ("above", "below"):
        return {"error": "condition must be 'above' or 'below'"}
    if threshold is None:
        return {"error": "threshold is required"}

    alert_data = AlertCreate(
        alert_type=alert_type,
        symbol=symbol,
        condition=condition,
        threshold=float(threshold),
        message=message,
    )

    manager = get_alert_manager()
    try:
        alert = await manager.create_alert(alert_data)
    except Exception as exc:
        logger.error(f"set_alert: creation failed: {exc}")
        return {"error": str(exc)}

    logger.info(f"set_alert: {symbol} {condition} {threshold} created (id={alert.id})")
    return {
        "success": True,
        "alert_id": alert.id,
        "symbol": alert.symbol,
        "alert_type": alert.alert_type,
        "condition": alert.condition,
        "threshold": alert.threshold,
        "message": alert.message,
        "is_active": alert.is_active,
    }
