"""Scan the entire watchlist for trading opportunities across Binance and Polymarket."""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.exchanges.binance_client import get_binance_client
from src.memory import get_memory_orchestrator
from src.soul_manager import get_soul_manager
from ta.momentum import RSIIndicator
from ta.trend import MACD

DESCRIPTION = "Scan the full watchlist for buy/sell signals and rank opportunities by strength"
PARAMS = {
    "symbols": "list[str] — optional override list of symbols to scan (default: soul watchlist)",
    "interval": "str — candle interval: 1h, 4h, 1d (default: 1h)",
    "top_n": "int — return top N opportunities (default: 5)",
}
RETURNS = "dict with ranked opportunities list and scan summary"


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    interval = params.get("interval", "1h")
    top_n = int(params.get("top_n", 5))

    soul = await get_soul_manager().load_soul()
    symbols: list[str] = params.get("symbols") or soul.watchlist or ["BTCUSDT", "ETHUSDT"]
    symbols = [s.upper() for s in symbols]

    client = get_binance_client()
    opportunities: list[dict[str, Any]] = []
    errors: list[str] = []

    for symbol in symbols:
        try:
            df = await client.get_ohlcv(symbol=symbol, interval=interval, limit=100)
            close = df["close"]
            high = df["high"]
            low = df["low"]

            rsi = float(RSIIndicator(close=close, window=14).rsi().iloc[-1])
            macd_hist = float(MACD(close=close).macd_diff().iloc[-1])
            current_price = float(close.iloc[-1])
            support = float(low.tail(20).min())
            resistance = float(high.tail(20).max())

            dist_to_support = (current_price - support) / support if support > 0 else 0
            dist_to_resistance = (resistance - current_price) / current_price if current_price > 0 else 0

            score = 0.0
            signal = "hold"
            if rsi < 30 and macd_hist > 0:
                score = (30 - rsi) / 30 * 0.5 + min(macd_hist / current_price * 1000, 0.5)
                signal = "buy"
            elif rsi > 70 and macd_hist < 0:
                score = (rsi - 70) / 30 * 0.5 + min(abs(macd_hist) / current_price * 1000, 0.5)
                signal = "sell"
            elif rsi < 40 and dist_to_support < 0.02:
                score = 0.3
                signal = "buy"
            elif rsi > 60 and dist_to_resistance < 0.02:
                score = 0.3
                signal = "sell"

            if score > 0.1:
                opportunities.append({
                    "symbol": symbol,
                    "signal": signal,
                    "score": round(score, 3),
                    "current_price": current_price,
                    "rsi": round(rsi, 2),
                    "macd_histogram": round(macd_hist, 6),
                    "support": round(support, 4),
                    "resistance": round(resistance, 4),
                    "dist_to_support_pct": round(dist_to_support * 100, 2),
                    "dist_to_resistance_pct": round(dist_to_resistance * 100, 2),
                })
                mem = get_memory_orchestrator()
                mem.short_term.update_market_price(symbol, current_price)

        except Exception as exc:
            logger.warning(f"scan_opportunities: {symbol} failed: {exc}")
            errors.append(f"{symbol}: {exc}")

    opportunities.sort(key=lambda x: x["score"], reverse=True)
    top = opportunities[:top_n]

    logger.info(
        f"scan_opportunities: scanned {len(symbols)} symbols, "
        f"found {len(opportunities)} signals, top={top[0]['symbol'] if top else 'none'}"
    )

    return {
        "scanned": len(symbols),
        "signals_found": len(opportunities),
        "opportunities": top,
        "errors": errors,
        "interval": interval,
    }
