"""Soul profile management — load, persist, and inject into LLM prompts."""

from __future__ import annotations

import json
import os
from typing import Optional

from loguru import logger
from sqlalchemy import select

from src.config import get_settings
from src.database import get_session
from src.models import SoulProfile
from src.schemas import SoulProfileSchema, SoulProfileUpdate

settings = get_settings()


def _load_default_soul() -> dict:
    """Load the default soul from soul/profile.json."""
    path = settings.soul_profile_path
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {
        "name": "Aether",
        "personality": "analytical, cautious, opportunistic",
        "risk_tolerance": 0.3,
        "max_position_size_usd": 1000.0,
        "max_daily_loss_usd": 500.0,
        "preferred_markets": ["BTC", "ETH", "polymarket-crypto"],
        "avoided_markets": [],
        "trading_hours": "24/7",
        "ethics": ["Never risk more than stop-loss", "No manipulation"],
        "communication_style": "concise with emojis, explains reasoning",
        "decision_philosophy": "High conviction only. Capital preservation first.",
        "core_beliefs": ["Risk management is everything"],
        "watchlist": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
        "polymarket_categories": ["crypto", "economics"],
    }


class SoulManager:
    """CRUD operations for the soul profile and prompt injection."""

    async def ensure_soul_exists(self) -> None:
        """Seed the database with the default soul profile if none exists."""
        async with get_session() as session:
            result = await session.execute(
                select(SoulProfile).where(SoulProfile.is_active.is_(True))
            )
            existing = result.scalars().first()
            if existing:
                return

            defaults = _load_default_soul()
            soul = SoulProfile(
                name=defaults.get("name", "Aether"),
                personality=defaults.get("personality", ""),
                risk_tolerance=defaults.get("risk_tolerance", 0.3),
                max_position_size_usd=defaults.get("max_position_size_usd", 1000.0),
                max_daily_loss_usd=defaults.get("max_daily_loss_usd", 500.0),
                preferred_markets=defaults.get("preferred_markets", []),
                avoided_markets=defaults.get("avoided_markets", []),
                trading_hours=defaults.get("trading_hours", "24/7"),
                ethics=defaults.get("ethics", []),
                communication_style=defaults.get("communication_style", ""),
                decision_philosophy=defaults.get("decision_philosophy", ""),
                core_beliefs=defaults.get("core_beliefs", []),
                watchlist=defaults.get("watchlist", []),
                polymarket_categories=defaults.get("polymarket_categories", []),
                is_active=True,
            )
            session.add(soul)
            await session.commit()
            logger.info(f"Soul profile seeded: {soul.name}")

    async def load_soul(self) -> SoulProfileSchema:
        """Load the active soul profile from the database."""
        async with get_session() as session:
            result = await session.execute(
                select(SoulProfile).where(SoulProfile.is_active.is_(True))
            )
            soul = result.scalars().first()
            if soul is None:
                await self.ensure_soul_exists()
                result = await session.execute(
                    select(SoulProfile).where(SoulProfile.is_active.is_(True))
                )
                soul = result.scalars().first()
            return SoulProfileSchema.model_validate(soul)

    async def update_soul(self, updates: SoulProfileUpdate) -> SoulProfileSchema:
        """Update the active soul profile."""
        async with get_session() as session:
            result = await session.execute(
                select(SoulProfile).where(SoulProfile.is_active.is_(True))
            )
            soul = result.scalars().first()
            if soul is None:
                raise ValueError("No active soul profile found")

            update_data = updates.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(soul, key, value)

            await session.commit()
            await session.refresh(soul)
            logger.info(f"Soul profile updated: {list(update_data.keys())}")
            return SoulProfileSchema.model_validate(soul)

    def build_soul_prompt(self, soul: SoulProfileSchema) -> str:
        """Build the soul injection block for LLM prompts."""
        ethics_lines = "\n".join(f"  - {e}" for e in soul.ethics)
        beliefs_lines = "\n".join(f"  - {b}" for b in soul.core_beliefs)
        markets_str = ", ".join(soul.preferred_markets) or "any"
        avoided_str = ", ".join(soul.avoided_markets) or "none"

        return f"""=== YOUR SOUL / IDENTITY ===
Name: {soul.name}
Personality: {soul.personality}
Risk Tolerance: {soul.risk_tolerance:.0%} (0=no risk, 100%=max risk)
Max Position Size: ${soul.max_position_size_usd:,.0f}
Max Daily Loss: ${soul.max_daily_loss_usd:,.0f}

Decision Philosophy: {soul.decision_philosophy}

Preferred Markets: {markets_str}
Avoided Markets: {avoided_str}
Trading Hours: {soul.trading_hours}

Ethical Constraints:
{ethics_lines}

Core Beliefs:
{beliefs_lines}

Communication Style: {soul.communication_style}
=== END SOUL ==="""

    def build_system_prompt(self, soul: SoulProfileSchema) -> str:
        """Build the full system prompt for the brain LLM."""
        soul_block = self.build_soul_prompt(soul)
        return f"""You are {soul.name}, an autonomous AI trading agent.

{soul_block}

You operate in a continuous reasoning loop. Each cycle you:
1. Analyze the current market state and your memory
2. Decide whether to act or wait
3. If acting, choose the best skill to execute
4. Always explain your reasoning clearly

RESPONSE FORMAT (strict JSON):
{{
  "reasoning": "Your step-by-step thinking about the current situation",
  "observation": "What you notice about the market and your portfolio",
  "action": "skill_name or null if no action",
  "params": {{}},
  "confidence": 0.0,
  "expected_outcome": "What you expect to happen",
  "risk_assessment": "Brief risk assessment"
}}

If no action is warranted, set "action" to null and explain why in reasoning.
Never execute a trade if confidence < {settings.confidence_threshold}.
Always respect your ethical constraints.
Be concise but thorough in reasoning."""


_soul_manager: Optional[SoulManager] = None


def get_soul_manager() -> SoulManager:
    global _soul_manager
    if _soul_manager is None:
        _soul_manager = SoulManager()
    return _soul_manager
