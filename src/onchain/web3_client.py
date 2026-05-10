"""Web3.py client for Ethereum and Polygon on-chain interaction."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from loguru import logger
from web3 import AsyncWeb3
from web3.middleware import ExtraDataToPOAMiddleware

from src.config import get_settings

settings = get_settings()

# ERC20 minimal ABI for token queries
ERC20_ABI = [
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "name", "outputs": [{"name": "", "type": "string"}], "type": "function"},
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
]


class Web3Client:
    """Async Web3 client for Ethereum and Polygon chains."""

    def __init__(self, chain: str = "ethereum") -> None:
        self.chain = chain
        self._w3: Optional[AsyncWeb3] = None

    def _get_w3(self) -> AsyncWeb3:
        if self._w3 is None:
            rpc = (
                settings.polygon_rpc_url
                if self.chain == "polygon"
                else settings.ethereum_rpc_url
            )
            if not rpc:
                raise RuntimeError(f"No RPC URL configured for chain '{self.chain}'")

            provider = AsyncWeb3.AsyncHTTPProvider(rpc)
            self._w3 = AsyncWeb3(provider)
            if self.chain == "polygon":
                self._w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            logger.info(f"Web3 client initialized for {self.chain}")
        return self._w3

    async def is_connected(self) -> bool:
        try:
            w3 = self._get_w3()
            return await w3.is_connected()
        except Exception:
            return False

    async def get_eth_balance(self, address: str) -> float:
        """Get native token balance (ETH/MATIC) in token units."""
        w3 = self._get_w3()
        checksum_addr = w3.to_checksum_address(address)
        wei = await w3.eth.get_balance(checksum_addr)
        return float(w3.from_wei(wei, "ether"))

    async def get_token_balance(self, token_address: str, wallet_address: str) -> dict[str, Any]:
        """Get ERC20 token balance for a wallet."""
        w3 = self._get_w3()
        token_addr = w3.to_checksum_address(token_address)
        wallet_addr = w3.to_checksum_address(wallet_address)

        contract = w3.eth.contract(address=token_addr, abi=ERC20_ABI)
        try:
            decimals = await contract.functions.decimals().call()
            symbol = await contract.functions.symbol().call()
            raw_balance = await contract.functions.balanceOf(wallet_addr).call()
            balance = raw_balance / (10 ** decimals)
            return {
                "token": token_address,
                "symbol": symbol,
                "balance": balance,
                "decimals": decimals,
                "wallet": wallet_address,
            }
        except Exception as exc:
            logger.error(f"Token balance failed {token_address}: {exc}")
            raise

    async def get_gas_price(self) -> dict[str, float]:
        """Get current gas prices in Gwei."""
        w3 = self._get_w3()
        try:
            gas_price_wei = await w3.eth.gas_price
            gas_gwei = float(w3.from_wei(gas_price_wei, "gwei"))
            # Estimate fast/slow variants
            return {
                "slow": round(gas_gwei * 0.8, 2),
                "standard": round(gas_gwei, 2),
                "fast": round(gas_gwei * 1.2, 2),
                "rapid": round(gas_gwei * 1.5, 2),
            }
        except Exception as exc:
            logger.error(f"Gas price fetch failed: {exc}")
            return {"slow": 0, "standard": 0, "fast": 0, "rapid": 0}

    async def get_block_number(self) -> int:
        w3 = self._get_w3()
        return await w3.eth.block_number

    async def get_transaction(self, tx_hash: str) -> Optional[dict[str, Any]]:
        """Get transaction details by hash."""
        w3 = self._get_w3()
        try:
            tx = await w3.eth.get_transaction(tx_hash)
            if tx is None:
                return None
            return {
                "hash": tx["hash"].hex(),
                "from": tx["from"],
                "to": tx.get("to", ""),
                "value_eth": float(w3.from_wei(tx["value"], "ether")),
                "gas": tx["gas"],
                "gas_price_gwei": float(w3.from_wei(tx.get("gasPrice", 0), "gwei")),
                "nonce": tx["nonce"],
                "block_number": tx.get("blockNumber"),
                "input": tx["input"].hex() if isinstance(tx["input"], bytes) else str(tx["input"]),
            }
        except Exception as exc:
            logger.error(f"Transaction fetch failed {tx_hash}: {exc}")
            return None

    async def get_wallet_info(self, address: str) -> dict[str, Any]:
        """Get comprehensive wallet info."""
        w3 = self._get_w3()
        checksum = w3.to_checksum_address(address)
        eth_balance = await self.get_eth_balance(address)
        nonce = await w3.eth.get_transaction_count(checksum)
        block = await w3.eth.block_number
        gas = await self.get_gas_price()

        return {
            "address": checksum,
            "chain": self.chain,
            "eth_balance": eth_balance,
            "tx_count": nonce,
            "current_block": block,
            "gas_prices": gas,
            "timestamp": datetime.utcnow().isoformat(),
        }


_eth_client: Optional[Web3Client] = None
_poly_client: Optional[Web3Client] = None


def get_web3_client(chain: str = "ethereum") -> Web3Client:
    global _eth_client, _poly_client
    if chain == "polygon":
        if _poly_client is None:
            _poly_client = Web3Client(chain="polygon")
        return _poly_client
    else:
        if _eth_client is None:
            _eth_client = Web3Client(chain="ethereum")
        return _eth_client
