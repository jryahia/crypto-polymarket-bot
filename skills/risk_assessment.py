"""Assess risk for a potential trade or current portfolio."""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.config import get_settings
from src.exchanges.binance_client import get_binance_client
from src.memory import get_memory_orchestrator
from src.soul_manager import get_soul_manager
from ta.volatility import AverageTrueRange

settings = get_settings()

DESCRIPTION = "Assess risk of a trade or current portfolio including position sizing, drawdown, and correlation"
PARAMS = {
    "symbol": "str — symbol to assess (optional, assesses full portfolio if omitted)",
    "side": "str — buy or sell (optional)",
    "quantity": "float — trade quantity for sizing check (optional)",
    "price": "float — entry price for sizing check (optional)",
}
RETURNS = "dict with risk_score, position_size_ok, drawdown_status, recommendations"


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    symbol = params.get("symbol", "").upper()
    side = params.get("side", "").lower()
    quantity = float(params.get("quantity", 0))
    price = float(params.get("price", 0))

    soul = await get_soul_manager().load_soul()
    memory = get_memory_orchestrator()
    stats = await memory.long_term.compute_performance_stats()
    open_positions = await memory.long_term.get_open_positions()
    state = memory.short_term.get_state_snapshot()

    daily_pnl = float(state.get("daily_pnl", 0))
    total_open_exposure = sum(
        p.get("quantity", 0) * p.get("current_price", 0)
        for p in open_positions
    )

    warnings: list[str] = []
    recommendations: list[str] = []
    risk_score = 0.0

    # Daily loss limit check
    if daily_pnl < -soul.max_daily_loss_usd * 0.8:
        warnings.append(f"Daily P&L ${daily_pnl:.2f} approaching daily loss limit ${-soul.max_daily_loss_usd:.2f}")
        risk_score += 0.3
    if daily_pnl < -soul.max_daily_loss_usd:
        warnings.append("DAILY LOSS LIMIT EXCEEDED — no new trades recommended")
        risk_score += 0.5
        recommendations.append("Stop trading for today")

    # Portfolio concentration
    if total_open_exposure > soul.max_position_size_usd * 3:
        warnings.append(f"High portfolio exposure: ${total_open_exposure:.2f}")
        risk_score += 0.2

    # Specific trade sizing check
    trade_value = quantity * price
    position_size_ok = True
    if quantity > 0 and price > 0:
        if trade_value > soul.max_position_size_usd:
            warnings.append(
                f"Trade value ${trade_value:.2f} exceeds max position ${soul.max_position_size_usd:.2f}"
            )
            risk_score += 0.25
            position_size_ok = False
            recommended_qty = soul.max_position_size_usd / price
            recommendations.append(f"Reduce quantity to {recommended_qty:.6f} ({soul.max_position_size_usd:.0f} USD)")

    # Volatility check
    volatility_info: dict[str, Any] = {}
    if symbol:
        try:
            client = get_binance_client()
            df = await client.get_ohlcv(symbol=symbol, interval="1h", limit=50)
            atr = float(
                AverageTrueRange(
                    high=df["high"], low=df["low"], close=df["close"], window=14
                ).average_true_range().iloc[-1]
            )
            current_price = float(df["close"].iloc[-1])
            atr_pct = atr / current_price * 100
            volatility_info = {
                "atr": round(atr, 4),
                "atr_pct": round(atr_pct, 2),
                "volatility_level": "high" if atr_pct > 3 else ("medium" if atr_pct > 1.5 else "low"),
            }
            if atr_pct > 5:
                warnings.append(f"High volatility: ATR={atr_pct:.1f}% of price")
                risk_score += 0.15
                recommendations.append("Consider smaller position size due to high volatility")

            # Suggested stop-loss based on ATR
            if side == "buy" and current_price > 0:
                recommendations.append(f"Suggested stop-loss: ${current_price - 2 * atr:.4f} (2x ATR below entry)")
                recommendations.append(f"Suggested take-profit: ${current_price + 3 * atr:.4f} (3x ATR above entry)")
        except Exception as exc:
            logger.debug(f"risk_assessment: volatility check skipped: {exc}")

    # Win rate check
    win_rate = stats.get("win_rate", 0.5)
    if win_rate < 0.4 and stats.get("total_trades", 0) > 5:
        warnings.append(f"Win rate is low: {win_rate:.1%}")
        risk_score += 0.1

    risk_score = min(risk_score, 1.0)
    risk_level = "low" if risk_score < 0.3 else ("medium" if risk_score < 0.6 else "high")

    if not recommendations:
        recommendations.append("Risk parameters look acceptable — proceed with normal caution")

    result = {
        "risk_score": round(risk_score, 3),
        "risk_level": risk_level,
        "position_size_ok": position_size_ok,
        "trade_value_usd": round(trade_value, 2) if trade_value > 0 else None,
        "max_position_usd": soul.max_position_size_usd,
        "daily_pnl": round(daily_pnl, 2),
        "daily_loss_limit": soul.max_daily_loss_usd,
        "open_positions": len(open_positions),
        "total_exposure_usd": round(total_open_exposure, 2),
        "win_rate": round(win_rate, 3),
        "warnings": warnings,
        "recommendations": recommendations,
        "volatility": volatility_info,
        "performance": {
            "total_trades": stats.get("total_trades", 0),
            "total_pnl_usd": stats.get("total_pnl_usd", 0),
            "profit_factor": stats.get("profit_factor", 0),
        },
    }

    logger.info(
        f"risk_assessment: risk={risk_level} ({risk_score:.2f}) | "
        f"warnings={len(warnings)} | exposure=${total_open_exposure:.2f}"
    )
    return result
