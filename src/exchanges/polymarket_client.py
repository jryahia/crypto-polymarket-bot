"""Polymarket CLOB API client for prediction market trading."""

from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime
from typing import Any, Optional

import httpx
from eth_account import Account
from loguru import logger

from src.config import get_settings

settings = get_settings()

CLOB_BASE = settings.polymarket_clob_url
GAMMA_BASE = "https://gamma-api.polymarket.com"


class PolymarketClient:
    """Polymarket CLOB API client with signature-based authentication."""

    def __init__(self) -> None:
        self._http: Optional[httpx.AsyncClient] = None
        self._account: Optional[Any] = None

    def _get_account(self) -> Optional[Any]:
        if self._account is None and settings.polymarket_private_key:
            try:
                self._account = Account.from_key(settings.polymarket_private_key)
            except Exception as exc:
                logger.error(f"Invalid Polymarket private key: {exc}")
        return self._account

    def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
        return self._http

    def _build_hmac_headers(self, method: str, path: str, body: str = "") -> dict[str, str]:
        """Build HMAC authentication headers for authenticated endpoints."""
        if not settings.polymarket_api_key or not settings.polymarket_api_secret:
            return {}

        timestamp = str(int(time.time() * 1000))
        message = timestamp + method.upper() + path + body
        signature = hmac.new(
            settings.polymarket_api_secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

        return {
            "POLY-API-KEY": settings.polymarket_api_key,
            "POLY-TIMESTAMP": timestamp,
            "POLY-SIGNATURE": signature,
        }

    async def get_markets(
        self,
        category: Optional[str] = None,
        active_only: bool = True,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Fetch markets from the Gamma API."""
        http = self._get_http()
        try:
            params: dict[str, Any] = {"limit": limit, "order": "volume24hr", "ascending": "false"}
            if active_only:
                params["active"] = "true"
                params["closed"] = "false"
            if category:
                params["tag"] = category

            resp = await http.get(f"{GAMMA_BASE}/markets", params=params)
            resp.raise_for_status()
            data = resp.json()

            markets = []
            for m in data:
                try:
                    outcomes = m.get("outcomes", "[]")
                    if isinstance(outcomes, str):
                        import json
                        outcomes = json.loads(outcomes)

                    prices = m.get("outcomePrices", "[]")
                    if isinstance(prices, str):
                        import json
                        prices = json.loads(prices)

                    yes_price = float(prices[0]) if prices else 0.5
                    no_price = float(prices[1]) if len(prices) > 1 else 1.0 - yes_price

                    markets.append({
                        "condition_id": m.get("conditionId", ""),
                        "question": m.get("question", ""),
                        "category": m.get("category", ""),
                        "volume": float(m.get("volume", 0)),
                        "liquidity": float(m.get("liquidity", 0)),
                        "yes_price": yes_price,
                        "no_price": no_price,
                        "closing_date": m.get("endDate", ""),
                        "is_resolved": m.get("resolved", False),
                        "outcome": m.get("resolution", None),
                        "description": m.get("description", ""),
                        "market_slug": m.get("slug", ""),
                        "image_url": m.get("image", ""),
                    })
                except Exception as parse_exc:
                    logger.debug(f"Skipping market due to parse error: {parse_exc}")

            return markets
        except httpx.HTTPStatusError as exc:
            logger.error(f"Polymarket markets fetch failed: {exc.response.status_code}")
            return []
        except Exception as exc:
            logger.error(f"Polymarket markets error: {exc}")
            return []

    async def get_market(self, condition_id: str) -> Optional[dict[str, Any]]:
        """Get details for a specific market."""
        http = self._get_http()
        try:
            resp = await http.get(f"{GAMMA_BASE}/markets/{condition_id}")
            resp.raise_for_status()
            m = resp.json()

            prices = m.get("outcomePrices", "[]")
            if isinstance(prices, str):
                import json
                prices = json.loads(prices)

            yes_price = float(prices[0]) if prices else 0.5
            no_price = float(prices[1]) if len(prices) > 1 else 1.0 - yes_price

            return {
                "condition_id": m.get("conditionId", condition_id),
                "question": m.get("question", ""),
                "category": m.get("category", ""),
                "volume": float(m.get("volume", 0)),
                "liquidity": float(m.get("liquidity", 0)),
                "yes_price": yes_price,
                "no_price": no_price,
                "closing_date": m.get("endDate", ""),
                "is_resolved": m.get("resolved", False),
                "outcome": m.get("resolution", None),
                "description": m.get("description", ""),
            }
        except Exception as exc:
            logger.error(f"Get market {condition_id} failed: {exc}")
            return None

    async def get_order_book(self, token_id: str) -> dict[str, Any]:
        """Get the order book for a market token."""
        http = self._get_http()
        try:
            resp = await http.get(f"{CLOB_BASE}/book", params={"token_id": token_id})
            resp.raise_for_status()
            data = resp.json()
            return {
                "bids": data.get("bids", []),
                "asks": data.get("asks", []),
                "mid_price": self._calculate_mid(data),
            }
        except Exception as exc:
            logger.error(f"Order book failed for {token_id}: {exc}")
            return {"bids": [], "asks": [], "mid_price": 0.5}

    def _calculate_mid(self, book: dict[str, Any]) -> float:
        bids = book.get("bids", [])
        asks = book.get("asks", [])
        best_bid = float(bids[0]["price"]) if bids else 0.0
        best_ask = float(asks[0]["price"]) if asks else 1.0
        return (best_bid + best_ask) / 2

    async def place_bet(
        self,
        condition_id: str,
        outcome: str,  # "yes" or "no"
        amount_usd: float,
        price: Optional[float] = None,
    ) -> dict[str, Any]:
        """Place a bet on a Polymarket market."""
        if not settings.enable_live_trading:
            logger.warning(f"[PAPER] Polymarket bet: {outcome.upper()} on {condition_id} for ${amount_usd}")
            return {
                "order_id": f"PAPER-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                "condition_id": condition_id,
                "outcome": outcome,
                "amount_usd": amount_usd,
                "price": price or 0.5,
                "status": "filled",
                "paper_trade": True,
            }

        account = self._get_account()
        if not account:
            raise RuntimeError("Polymarket private key not configured for live trading")

        market = await self.get_market(condition_id)
        if not market:
            raise ValueError(f"Market {condition_id} not found")

        if price is None:
            price = market["yes_price"] if outcome.lower() == "yes" else market["no_price"]

        # Clamp price to valid range
        price = max(0.01, min(0.99, price))
        shares = amount_usd / price

        http = self._get_http()
        body = {
            "conditionId": condition_id,
            "outcome": outcome.upper(),
            "price": str(price),
            "size": str(round(shares, 6)),
            "side": "BUY",
            "orderType": "LIMIT",
            "walletAddress": account.address,
        }

        import json
        body_str = json.dumps(body, separators=(",", ":"))
        auth_headers = self._build_hmac_headers("POST", "/order", body_str)

        try:
            resp = await http.post(
                f"{CLOB_BASE}/order",
                content=body_str,
                headers=auth_headers,
            )
            resp.raise_for_status()
            result = resp.json()
            logger.info(f"Polymarket bet placed: {outcome} on {condition_id} for ${amount_usd}")
            return {
                "order_id": result.get("orderID", ""),
                "condition_id": condition_id,
                "outcome": outcome,
                "amount_usd": amount_usd,
                "price": price,
                "shares": shares,
                "status": result.get("status", "pending"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error(f"Polymarket bet failed: {exc.response.text}")
            raise
        except Exception as exc:
            logger.error(f"Polymarket bet error: {exc}")
            raise

    async def get_positions(self) -> list[dict[str, Any]]:
        """Get open Polymarket positions for the configured wallet."""
        account = self._get_account()
        if not account:
            return []

        http = self._get_http()
        try:
            resp = await http.get(
                f"{CLOB_BASE}/positions",
                params={"user": account.address},
            )
            resp.raise_for_status()
            data = resp.json()
            positions = []
            for pos in data:
                positions.append({
                    "condition_id": pos.get("conditionId", ""),
                    "outcome": pos.get("outcome", ""),
                    "shares": float(pos.get("size", 0)),
                    "avg_price": float(pos.get("avgPrice", 0)),
                    "current_price": float(pos.get("currentPrice", 0)),
                    "pnl": float(pos.get("pnl", 0)),
                    "value": float(pos.get("value", 0)),
                })
            return positions
        except Exception as exc:
            logger.error(f"Polymarket positions error: {exc}")
            return []

    async def search_markets(
        self,
        query: str,
        categories: Optional[list[str]] = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search markets by keyword."""
        all_markets = await self.get_markets(limit=100)
        query_lower = query.lower()

        filtered = [
            m for m in all_markets
            if query_lower in m["question"].lower()
            or (m.get("description") and query_lower in m["description"].lower())
        ]

        if categories:
            filtered = [
                m for m in filtered
                if any(c.lower() in (m.get("category") or "").lower() for c in categories)
            ]

        return filtered[:limit]

    async def close(self) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None


_polymarket_client: Optional[PolymarketClient] = None


def get_polymarket_client() -> PolymarketClient:
    global _polymarket_client
    if _polymarket_client is None:
        _polymarket_client = PolymarketClient()
    return _polymarket_client
