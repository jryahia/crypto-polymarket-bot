"""Backtest a simple RSI/MACD strategy on historical Binance data."""

from __future__ import annotations

from typing import Any

import pandas as pd
from loguru import logger
from ta.momentum import RSIIndicator
from ta.trend import MACD

from src.exchanges.binance_client import get_binance_client

DESCRIPTION = "Backtest an RSI + MACD crossover strategy on historical price data"
PARAMS = {
    "symbol": "str — trading pair e.g. BTCUSDT",
    "interval": "str — candle interval: 1h, 4h, 1d (default: 4h)",
    "limit": "int — number of candles for backtest (default: 500)",
    "rsi_buy": "float — RSI level to trigger buy (default: 35)",
    "rsi_sell": "float — RSI level to trigger sell (default: 65)",
    "position_size_usd": "float — simulated position size (default: 100)",
}
RETURNS = "dict with trades list, win_rate, total_pnl, max_drawdown, sharpe_ratio"


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    symbol = params.get("symbol", "BTCUSDT").upper()
    interval = params.get("interval", "4h")
    limit = int(params.get("limit", 500))
    rsi_buy = float(params.get("rsi_buy", 35))
    rsi_sell = float(params.get("rsi_sell", 65))
    pos_size = float(params.get("position_size_usd", 100))

    client = get_binance_client()
    try:
        df = await client.get_ohlcv(symbol=symbol, interval=interval, limit=limit)
    except Exception as exc:
        logger.error(f"backtest_strategy: OHLCV failed for {symbol}: {exc}")
        return {"error": str(exc), "symbol": symbol}

    close = df["close"]
    rsi_series = RSIIndicator(close=close, window=14).rsi()
    macd_ind = MACD(close=close)
    macd_hist = macd_ind.macd_diff()

    trades: list[dict[str, Any]] = []
    in_position = False
    entry_price = 0.0
    entry_idx = 0
    portfolio_values: list[float] = [1000.0]
    cash = 1000.0

    for i in range(20, len(df)):
        price = float(close.iloc[i])
        rsi = float(rsi_series.iloc[i])
        hist = float(macd_hist.iloc[i])
        hist_prev = float(macd_hist.iloc[i - 1])

        if not in_position:
            if rsi < rsi_buy and hist > 0 and hist_prev <= 0:
                qty = pos_size / price
                entry_price = price
                entry_idx = i
                in_position = True
                cash -= pos_size
        else:
            if rsi > rsi_sell and hist < 0 and hist_prev >= 0:
                exit_price = price
                qty = pos_size / entry_price
                pnl = (exit_price - entry_price) * qty
                cash += pos_size + pnl
                trades.append({
                    "entry_idx": entry_idx,
                    "exit_idx": i,
                    "entry_price": round(entry_price, 4),
                    "exit_price": round(exit_price, 4),
                    "pnl_usd": round(pnl, 2),
                    "pnl_pct": round((exit_price - entry_price) / entry_price * 100, 2),
                    "result": "win" if pnl > 0 else "loss",
                })
                in_position = False
            portfolio_values.append(cash + (price - entry_price) * (pos_size / entry_price))

        if not in_position:
            portfolio_values.append(cash)

    if not trades:
        return {
            "symbol": symbol,
            "interval": interval,
            "total_trades": 0,
            "win_rate": 0.0,
            "total_pnl_usd": 0.0,
            "message": "No trades triggered with these parameters",
        }

    pnls = [t["pnl_usd"] for t in trades]
    wins = [p for p in pnls if p > 0]
    total_pnl = sum(pnls)
    win_rate = len(wins) / len(pnls) if pnls else 0.0

    equity = pd.Series(portfolio_values)
    rolling_max = equity.cummax()
    drawdown = (equity - rolling_max) / rolling_max
    max_drawdown = float(drawdown.min())

    returns = equity.pct_change().dropna()
    sharpe = float(returns.mean() / returns.std() * (252 ** 0.5)) if returns.std() > 0 else 0.0

    logger.info(
        f"backtest_strategy: {symbol} {interval} | {len(trades)} trades | "
        f"win_rate={win_rate:.1%} | pnl=${total_pnl:.2f}"
    )

    return {
        "symbol": symbol,
        "interval": interval,
        "candles_analyzed": limit,
        "total_trades": len(trades),
        "win_rate": round(win_rate, 3),
        "total_pnl_usd": round(total_pnl, 2),
        "avg_pnl_usd": round(total_pnl / len(trades), 2),
        "best_trade_usd": round(max(pnls), 2),
        "worst_trade_usd": round(min(pnls), 2),
        "max_drawdown_pct": round(max_drawdown * 100, 2),
        "sharpe_ratio": round(sharpe, 3),
        "params": {"rsi_buy": rsi_buy, "rsi_sell": rsi_sell, "position_size_usd": pos_size},
        "trades": trades[-10:],
    }
