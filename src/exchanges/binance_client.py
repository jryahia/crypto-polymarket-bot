"""Binance REST + WebSocket client for spot trading and market data."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Callable, Optional

import pandas as pd
from binance import AsyncClient, BinanceSocketManager
from binance.exceptions import BinanceAPIException
from loguru import logger

from src.config import get_settings

settings = get_settings()


class BinanceClient:
    """Async Binance client for trading and market data."""

    def __init__(self) -> None:
        self._client: Optional[AsyncClient] = None
        self._bsm: Optional[BinanceSocketManager] = None
        self._ws_tasks: list[asyncio.Task] = []
        self._price_callbacks: dict[str, list[Callable]] = {}

    async def _get_client(self) -> AsyncClient:
        if self._client is None:
            if settings.binance_testnet:
                self._client = await AsyncClient.create(
                    api_key=settings.binance_api_key,
                    api_secret=settings.binance_api_secret,
                    testnet=True,
                )
            else:
                self._client = await AsyncClient.create(
                    api_key=settings.binance_api_key,
                    api_secret=settings.binance_api_secret,
                )
            logger.info(f"Binance client initialized (testnet={settings.binance_testnet})")
        return self._client

    async def get_price(self, symbol: str) -> float:
        """Get current price for a symbol."""
        client = await self._get_client()
        try:
            ticker = await client.get_symbol_ticker(symbol=symbol)
            return float(ticker["price"])
        except BinanceAPIException as exc:
            logger.error(f"Binance price error for {symbol}: {exc}")
            raise

    async def get_prices(self, symbols: list[str]) -> dict[str, float]:
        """Get prices for multiple symbols in one call."""
        client = await self._get_client()
        try:
            all_tickers = await client.get_all_tickers()
            price_map = {t["symbol"]: float(t["price"]) for t in all_tickers}
            return {sym: price_map[sym] for sym in symbols if sym in price_map}
        except Exception as exc:
            logger.error(f"Binance bulk prices error: {exc}")
            return {}

    async def get_ohlcv(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 100,
    ) -> pd.DataFrame:
        """Fetch OHLCV candlestick data as a DataFrame."""
        client = await self._get_client()
        try:
            klines = await client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit,
            )
            df = pd.DataFrame(
                klines,
                columns=[
                    "open_time", "open", "high", "low", "close", "volume",
                    "close_time", "quote_volume", "trades",
                    "taker_buy_base", "taker_buy_quote", "ignore",
                ],
            )
            df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)
            df.set_index("open_time", inplace=True)
            return df
        except BinanceAPIException as exc:
            logger.error(f"Binance OHLCV error for {symbol}/{interval}: {exc}")
            raise

    async def get_account(self) -> dict[str, Any]:
        """Get account balances and info."""
        client = await self._get_client()
        try:
            info = await client.get_account()
            balances = {
                b["asset"]: float(b["free"])
                for b in info["balances"]
                if float(b["free"]) > 0 or float(b["locked"]) > 0
            }
            return {
                "balances": balances,
                "can_trade": info.get("canTrade", False),
                "can_withdraw": info.get("canWithdraw", False),
                "maker_commission": info.get("makerCommission", 0) / 100.0,
                "taker_commission": info.get("takerCommission", 0) / 100.0,
            }
        except BinanceAPIException as exc:
            logger.error(f"Binance account error: {exc}")
            raise

    async def get_usdt_value(self) -> float:
        """Calculate total portfolio value in USDT."""
        try:
            account = await self.get_account()
            balances = account["balances"]
            total = balances.get("USDT", 0.0)

            for asset, qty in balances.items():
                if asset == "USDT" or qty == 0:
                    continue
                symbol = f"{asset}USDT"
                try:
                    price = await self.get_price(symbol)
                    total += qty * price
                except Exception:
                    pass  # Skip assets with no USDT pair

            return total
        except Exception as exc:
            logger.error(f"USDT value calculation failed: {exc}")
            return 0.0

    async def place_market_order(
        self,
        symbol: str,
        side: str,  # BUY or SELL
        quantity: float,
    ) -> dict[str, Any]:
        """Place a market order."""
        if not settings.enable_live_trading:
            logger.warning(f"[PAPER] Market {side} {quantity} {symbol}")
            return {
                "orderId": "PAPER-" + datetime.utcnow().strftime("%Y%m%d%H%M%S"),
                "symbol": symbol,
                "side": side,
                "type": "MARKET",
                "quantity": quantity,
                "status": "FILLED",
                "paper_trade": True,
            }

        client = await self._get_client()
        try:
            order = await client.order_market(
                symbol=symbol,
                side=side,
                quantity=quantity,
            )
            logger.info(f"Market order placed: {side} {quantity} {symbol} -> {order['orderId']}")
            return dict(order)
        except BinanceAPIException as exc:
            logger.error(f"Market order failed {side} {quantity} {symbol}: {exc}")
            raise

    async def place_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
    ) -> dict[str, Any]:
        """Place a limit order."""
        if not settings.enable_live_trading:
            logger.warning(f"[PAPER] Limit {side} {quantity} {symbol} @ {price}")
            return {
                "orderId": "PAPER-" + datetime.utcnow().strftime("%Y%m%d%H%M%S"),
                "symbol": symbol,
                "side": side,
                "type": "LIMIT",
                "quantity": quantity,
                "price": price,
                "status": "NEW",
                "paper_trade": True,
            }

        client = await self._get_client()
        try:
            order = await client.order_limit(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=str(price),
            )
            logger.info(f"Limit order placed: {side} {quantity} {symbol} @ {price} -> {order['orderId']}")
            return dict(order)
        except BinanceAPIException as exc:
            logger.error(f"Limit order failed: {exc}")
            raise

    async def cancel_order(self, symbol: str, order_id: str) -> dict[str, Any]:
        """Cancel an open order."""
        client = await self._get_client()
        try:
            result = await client.cancel_order(symbol=symbol, orderId=order_id)
            logger.info(f"Order cancelled: {order_id}")
            return dict(result)
        except BinanceAPIException as exc:
            logger.error(f"Cancel order failed {order_id}: {exc}")
            raise

    async def get_open_orders(self, symbol: Optional[str] = None) -> list[dict[str, Any]]:
        """Get all open orders, optionally filtered by symbol."""
        client = await self._get_client()
        try:
            if symbol:
                orders = await client.get_open_orders(symbol=symbol)
            else:
                orders = await client.get_open_orders()
            return [dict(o) for o in orders]
        except BinanceAPIException as exc:
            logger.error(f"Get open orders failed: {exc}")
            return []

    async def get_order_history(
        self,
        symbol: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get order history for a symbol."""
        client = await self._get_client()
        try:
            orders = await client.get_all_orders(symbol=symbol, limit=limit)
            return [dict(o) for o in orders]
        except BinanceAPIException as exc:
            logger.error(f"Order history failed for {symbol}: {exc}")
            return []

    async def get_24h_ticker(self, symbol: str) -> dict[str, Any]:
        """Get 24h price change statistics."""
        client = await self._get_client()
        try:
            ticker = await client.get_ticker(symbol=symbol)
            return {
                "symbol": ticker["symbol"],
                "price": float(ticker["lastPrice"]),
                "change_24h": float(ticker["priceChangePercent"]),
                "high_24h": float(ticker["highPrice"]),
                "low_24h": float(ticker["lowPrice"]),
                "volume_24h": float(ticker["volume"]),
                "quote_volume_24h": float(ticker["quoteVolume"]),
                "trades_24h": int(ticker["count"]),
            }
        except BinanceAPIException as exc:
            logger.error(f"24h ticker failed for {symbol}: {exc}")
            raise

    async def subscribe_price_stream(
        self,
        symbols: list[str],
        callback: Callable[[str, float], None],
    ) -> None:
        """Subscribe to real-time price updates via WebSocket."""
        client = await self._get_client()
        self._bsm = BinanceSocketManager(client)
        streams = [f"{sym.lower()}@miniTicker" for sym in symbols]

        async def _handle_message(msg: dict[str, Any]) -> None:
            if msg.get("e") == "24hrMiniTicker":
                sym = msg["s"]
                price = float(msg["c"])
                await callback(sym, price) if asyncio.iscoroutinefunction(callback) else callback(sym, price)

        socket = self._bsm.multiplex_socket(streams)

        async def _run() -> None:
            async with socket as ts:
                while True:
                    msg = await ts.recv()
                    if msg:
                        data = msg.get("data", msg)
                        await _handle_message(data) if asyncio.iscoroutinefunction(_handle_message) else _handle_message(data)

        task = asyncio.create_task(_run())
        self._ws_tasks.append(task)
        logger.info(f"WebSocket subscribed to {symbols}")

    async def close(self) -> None:
        """Clean up WebSocket connections and client."""
        for task in self._ws_tasks:
            task.cancel()
        self._ws_tasks.clear()
        if self._client:
            await self._client.close_connection()
            self._client = None
        logger.info("Binance client closed")


_binance_client: Optional[BinanceClient] = None


def get_binance_client() -> BinanceClient:
    global _binance_client
    if _binance_client is None:
        _binance_client = BinanceClient()
    return _binance_client
