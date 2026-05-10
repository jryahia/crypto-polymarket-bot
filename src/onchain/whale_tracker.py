"""Whale wallet monitoring via Etherscan API and Web3."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import httpx
from loguru import logger

from src.config import get_settings
from src.onchain.web3_client import get_web3_client

settings = get_settings()

ETHERSCAN_BASE = "https://api.etherscan.io/api"
ETHERSCAN_POLY = "https://api.polygonscan.com/api"


class WhaleTracker:
    """Monitor large wallet activity for market intelligence."""

    def __init__(self) -> None:
        self._http: Optional[httpx.AsyncClient] = None
        self._whale_cache: dict[str, dict[str, Any]] = {}

    def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=15.0)
        return self._http

    async def _etherscan_request(
        self,
        module: str,
        action: str,
        params: dict[str, Any],
        chain: str = "ethereum",
    ) -> Optional[dict[str, Any]]:
        """Make an Etherscan/Polygonscan API request."""
        if not settings.etherscan_api_key:
            logger.debug("Etherscan API key not configured")
            return None

        base = ETHERSCAN_POLY if chain == "polygon" else ETHERSCAN_BASE
        all_params = {
            "module": module,
            "action": action,
            "apikey": settings.etherscan_api_key,
            **params,
        }
        http = self._get_http()
        try:
            resp = await http.get(base, params=all_params)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "1":
                return data
            logger.debug(f"Etherscan {action} returned status {data.get('status')}: {data.get('message')}")
            return None
        except Exception as exc:
            logger.error(f"Etherscan request failed ({action}): {exc}")
            return None

    async def get_wallet_transactions(
        self,
        address: str,
        limit: int = 20,
        chain: str = "ethereum",
    ) -> list[dict[str, Any]]:
        """Get recent transactions for a wallet."""
        data = await self._etherscan_request(
            module="account",
            action="txlist",
            params={"address": address, "sort": "desc", "offset": limit, "page": 1},
            chain=chain,
        )

        if not data:
            return []

        txs = []
        for tx in data.get("result", []):
            try:
                value_eth = int(tx["value"]) / 1e18
                txs.append({
                    "hash": tx["hash"],
                    "from": tx["from"],
                    "to": tx["to"],
                    "value_eth": value_eth,
                    "gas_price_gwei": int(tx["gasPrice"]) / 1e9,
                    "timestamp": datetime.utcfromtimestamp(int(tx["timeStamp"])).isoformat(),
                    "block": int(tx["blockNumber"]),
                    "is_error": tx["isError"] == "1",
                    "method": tx.get("functionName", "")[:50],
                })
            except Exception:
                continue

        return txs

    async def get_token_transfers(
        self,
        address: str,
        limit: int = 20,
        chain: str = "ethereum",
    ) -> list[dict[str, Any]]:
        """Get ERC20 token transfers for a wallet."""
        data = await self._etherscan_request(
            module="account",
            action="tokentx",
            params={"address": address, "sort": "desc", "offset": limit, "page": 1},
            chain=chain,
        )

        if not data:
            return []

        transfers = []
        for tx in data.get("result", []):
            try:
                decimals = int(tx.get("tokenDecimal", 18))
                value = int(tx["value"]) / (10 ** decimals)
                transfers.append({
                    "hash": tx["hash"],
                    "from": tx["from"],
                    "to": tx["to"],
                    "token_symbol": tx["tokenSymbol"],
                    "token_name": tx["tokenName"],
                    "token_address": tx["contractAddress"],
                    "value": value,
                    "timestamp": datetime.utcfromtimestamp(int(tx["timeStamp"])).isoformat(),
                    "block": int(tx["blockNumber"]),
                })
            except Exception:
                continue

        return transfers

    async def detect_whale_movements(
        self,
        address: str,
        threshold_eth: float = 100.0,
        chain: str = "ethereum",
    ) -> list[dict[str, Any]]:
        """Detect large ETH movements from a wallet."""
        txs = await self.get_wallet_transactions(address, limit=50, chain=chain)
        return [
            tx for tx in txs
            if tx["value_eth"] >= threshold_eth
        ]

    async def track_all_whales(self, threshold_eth: float = 50.0) -> list[dict[str, Any]]:
        """Track movements across all configured whale wallets."""
        wallets = settings.monitored_wallet_list
        if not wallets:
            return []

        all_movements: list[dict[str, Any]] = []
        for wallet in wallets:
            try:
                movements = await self.detect_whale_movements(wallet, threshold_eth)
                for m in movements:
                    m["tracked_wallet"] = wallet
                    all_movements.append(m)
            except Exception as exc:
                logger.error(f"Whale track failed for {wallet}: {exc}")

        all_movements.sort(key=lambda x: x["timestamp"], reverse=True)
        return all_movements

    async def get_wallet_summary(self, address: str) -> dict[str, Any]:
        """Get a comprehensive summary of a whale wallet."""
        w3 = get_web3_client("ethereum")
        try:
            eth_balance = await w3.get_eth_balance(address)
        except Exception:
            eth_balance = 0.0

        recent_txs = await self.get_wallet_transactions(address, 10)
        recent_transfers = await self.get_token_transfers(address, 10)

        large_moves = [t for t in recent_txs if t["value_eth"] >= 10.0]

        top_tokens: dict[str, float] = {}
        for transfer in recent_transfers:
            sym = transfer["token_symbol"]
            if sym not in top_tokens:
                top_tokens[sym] = 0.0
            top_tokens[sym] += transfer["value"]

        return {
            "address": address,
            "eth_balance": eth_balance,
            "recent_transactions": len(recent_txs),
            "recent_token_transfers": len(recent_transfers),
            "large_movements_count": len(large_moves),
            "large_movements": large_moves[:5],
            "top_tokens_by_volume": sorted(
                top_tokens.items(), key=lambda x: x[1], reverse=True
            )[:10],
            "last_activity": recent_txs[0]["timestamp"] if recent_txs else None,
            "scanned_at": datetime.utcnow().isoformat(),
        }

    async def close(self) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None


_whale_tracker: Optional[WhaleTracker] = None


def get_whale_tracker() -> WhaleTracker:
    global _whale_tracker
    if _whale_tracker is None:
        _whale_tracker = WhaleTracker()
    return _whale_tracker
