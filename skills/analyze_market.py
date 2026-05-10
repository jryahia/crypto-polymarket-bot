"""Analyze technical indicators for a crypto symbol on Binance."""

from __future__ import annotations

from typing import Any

from loguru import logger
from ta.momentum import RSIIndicator
from ta.trend import MACD, EMAIndicator
from ta.volatility import BollingerBands, AverageTrueRange

from src.exchanges.binance_client import get_binance_client
from src.memory import get_memory_orchestrator

DESCRIPTION = "Analyze technical indicators (RSI, MACD, Bollinger Bands, EMA) for a crypto symbol"
PARAMS = {
    "symbol": "str — trading pair e.g. BTCUSDT",
    "interval": "str — candle interval: 1h, 4h, 1d (default: 1h)",
    "limit": "int — number of candles (default: 100)",
}
RETURNS = "dict with rsi, macd_signal, trend, support, resistance, recommendation"


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    symbol = params.get("symbol", "BTCUSDT").upper()
    interval = params.get("interval", "1h")
    limit = int(params.get("limit", 100))

    client = get_binance_client()
    try:
        df = await client.get_ohlcv(symbol=symbol, interval=interval, limit=limit)
    except Exception as exc:
        logger.error(f"analyze_market: OHLCV fetch failed for {symbol}: {exc}")
        return {"error": str(exc), "symbol": symbol}

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    rsi = float(RSIIndicator(close=close, window=14).rsi().iloc[-1])

    macd_ind = MACD(close=close)
    macd_hist = float(macd_ind.macd_diff().iloc[-1])
    macd_val = float(macd_ind.macd().iloc[-1])
    macd_sig_val = float(macd_ind.macd_signal().iloc[-1])
    macd_direction = "bullish" if macd_hist > 0 else "bearish"

    bb = BollingerBands(close=close, window=20, window_dev=2)
    bb_upper = float(bb.bollinger_hband().iloc[-1])
    bb_lower = float(bb.bollinger_lband().iloc[-1])
    bb_mid = float(bb.bollinger_mavg().iloc[-1])

    atr = float(AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range().iloc[-1])
    ema20 = float(EMAIndicator(close=close, window=20).ema_indicator().iloc[-1])
    ema50 = float(EMAIndicator(close=close, window=50).ema_indicator().iloc[-1])

    current_price = float(close.iloc[-1])
    resistance = float(high.tail(20).max())
    support = float(low.tail(20).min())

    avg_volume = float(volume.tail(20).mean())
    volume_ratio = float(volume.iloc[-1]) / avg_volume if avg_volume > 0 else 1.0

    if current_price > ema20 > ema50:
        trend = "bullish"
    elif current_price < ema20 < ema50:
        trend = "bearish"
    else:
        trend = "neutral"

    score = 0
    if rsi < 30:
        score += 2
    elif rsi > 70:
        score -= 2
    score += 1 if macd_direction == "bullish" else -1
    score += 1 if trend == "bullish" else (-1 if trend == "bearish" else 0)
    if current_price < bb_lower:
        score += 1
    elif current_price > bb_upper:
        score -= 1

    if score >= 3:
        recommendation = "strong_buy"
    elif score >= 1:
        recommendation = "buy"
    elif score <= -3:
        recommendation = "strong_sell"
    elif score <= -1:
        recommendation = "sell"
    else:
        recommendation = "hold"

    result = {
        "symbol": symbol,
        "interval": interval,
        "current_price": current_price,
        "rsi": round(rsi, 2),
        "macd": {
            "value": round(macd_val, 6),
            "signal": round(macd_sig_val, 6),
            "histogram": round(macd_hist, 6),
            "direction": macd_direction,
        },
        "bollinger_bands": {
            "upper": round(bb_upper, 4),
            "mid": round(bb_mid, 4),
            "lower": round(bb_lower, 4),
        },
        "ema": {"ema20": round(ema20, 4), "ema50": round(ema50, 4)},
        "atr": round(atr, 4),
        "support": round(support, 4),
        "resistance": round(resistance, 4),
        "trend": trend,
        "volume_ratio": round(volume_ratio, 2),
        "recommendation": recommendation,
        "score": score,
    }

    try:
        memory = get_memory_orchestrator()
        await memory.long_term.save_market_observation(symbol, {
            "price": current_price,
            "exchange": "binance",
            "rsi_14": rsi,
            "macd_signal": macd_direction,
            "indicators": {"trend": trend, "bb_upper": bb_upper, "bb_lower": bb_lower},
        })
        memory.short_term.update_market_price(symbol, current_price)
    except Exception as mem_exc:
        logger.debug(f"analyze_market: memory update skipped: {mem_exc}")

    logger.info(
        f"analyze_market: {symbol} @ {current_price:.4f} | RSI={rsi:.1f} | trend={trend} | rec={recommendation}"
    )
    return result
