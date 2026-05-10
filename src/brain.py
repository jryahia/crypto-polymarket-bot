"""LLM reasoning cycle orchestrator — the core brain loop."""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any, Optional

from loguru import logger

from src.config import get_settings
from src.llm_provider import get_llm_provider
from src.memory import get_memory_orchestrator
from src.soul_manager import get_soul_manager
from src.schemas import LessonCreate

settings = get_settings()


class Brain:
    """Orchestrates the LLM reasoning cycle."""

    def __init__(self) -> None:
        self._cycle_count = 0
        self._last_cycle_at: Optional[datetime] = None
        self._current_action: Optional[str] = None
        self._start_time = time.monotonic()

    async def run_cycle(self) -> dict[str, Any]:
        """Execute one full LLM reasoning cycle."""
        t0 = time.monotonic()
        self._cycle_count += 1
        cycle_num = self._cycle_count
        cycle_id = str(uuid.uuid4())

        logger.info(f"Brain cycle #{cycle_num} starting...")

        try:
            soul_manager = get_soul_manager()
            soul = await soul_manager.load_soul()
            system_prompt = soul_manager.build_system_prompt(soul)

            memory = get_memory_orchestrator()
            context = await memory.get_context_for_cycle(soul.watchlist)
            memory_text = memory.format_context_for_llm(context)

            from skills.loader import get_skill_loader
            skill_loader = get_skill_loader()
            skills = skill_loader.get_skill_list()
            skills_text = "\n".join(
                f"  - {s['name']}: {s['description']}"
                for s in skills
            )

            user_prompt = (
                f"{memory_text}\n\n"
                f"=== AVAILABLE SKILLS ===\n{skills_text}\n=== END SKILLS ===\n\n"
                f"Cycle #{cycle_num}. Timestamp: {datetime.utcnow().isoformat()}Z\n\n"
                "Analyze the current situation and decide what to do. "
                "Choose one skill to execute, or null if no action is warranted. "
                "Always provide your full reasoning."
            )

            llm = get_llm_provider()
            response = await llm.generate(
                messages=[{"role": "user", "content": user_prompt}],
                system=system_prompt,
                json_mode=True,
            )

            parsed = response.parse_json()
            reasoning = parsed.get("reasoning", "")
            action = parsed.get("action")
            params = parsed.get("params", {}) or {}
            confidence = float(parsed.get("confidence", 0.0))
            expected_outcome = parsed.get("expected_outcome", "")
            risk_assessment_text = parsed.get("risk_assessment", "")

            logger.info(f"Cycle #{cycle_num}: action={action}, confidence={confidence:.2f}")

            memory.short_term.add_reasoning(f"[#{cycle_num}] {reasoning[:200]}")
            memory.short_term.set("last_cycle_at", datetime.utcnow().isoformat())
            memory.short_term.set("cycle_count", cycle_num)

            action_result: dict[str, Any] = {}
            executed = False

            if action and confidence >= settings.confidence_threshold:
                self._current_action = action
                try:
                    action_result = await skill_loader.execute_skill(action, params)
                    executed = True
                    logger.info(f"Skill '{action}' executed successfully")
                except Exception as skill_exc:
                    logger.error(f"Skill execution failed: {skill_exc}")
                    action_result = {"error": str(skill_exc)}
                finally:
                    self._current_action = None
            elif action and confidence < settings.confidence_threshold:
                logger.info(
                    f"Skipping '{action}' — confidence {confidence:.2f} < threshold {settings.confidence_threshold}"
                )
                action_result = {
                    "skipped": f"confidence {confidence:.2f} < threshold {settings.confidence_threshold}"
                }

            duration_ms = int((time.monotonic() - t0) * 1000)
            self._last_cycle_at = datetime.utcnow()

            try:
                await memory.long_term.save_brain_cycle({
                    "id": cycle_id,
                    "cycle_number": cycle_num,
                    "soul_snapshot": {"name": soul.name, "risk_tolerance": soul.risk_tolerance},
                    "market_context": context.get("short_term", {}).get("market_prices", {}),
                    "memories_used": [
                        m.get("content", "")[:100]
                        for m in context.get("relevant_memories", [])
                    ],
                    "llm_prompt": user_prompt[:2000],
                    "llm_response": response.content[:2000],
                    "reasoning": reasoning,
                    "action_taken": action,
                    "action_params": params,
                    "action_result": action_result,
                    "confidence": confidence,
                    "executed": executed,
                    "llm_provider_used": response.provider,
                    "tokens_used": response.tokens_used,
                    "duration_ms": duration_ms,
                    "started_at": datetime.utcnow(),
                    "completed_at": datetime.utcnow(),
                })
            except Exception as db_exc:
                logger.warning(f"Failed to save brain cycle to DB: {db_exc}")

            if executed and action_result and not action_result.get("error"):
                await self._auto_learn(action, params, action_result, reasoning, soul.watchlist)

            return {
                "cycle_id": cycle_id,
                "cycle_number": cycle_num,
                "reasoning": reasoning,
                "action": action,
                "params": params,
                "confidence": confidence,
                "executed": executed,
                "result": action_result,
                "duration_ms": duration_ms,
                "tokens_used": response.tokens_used,
                "provider": response.provider,
                "expected_outcome": expected_outcome,
                "risk_assessment": risk_assessment_text,
            }

        except Exception as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.error(f"Brain cycle #{cycle_num} failed: {exc}", exc_info=True)
            self._current_action = None
            return {
                "cycle_id": cycle_id,
                "cycle_number": cycle_num,
                "reasoning": f"Cycle failed: {exc}",
                "action": None,
                "params": {},
                "confidence": 0.0,
                "executed": False,
                "result": {"error": str(exc)},
                "duration_ms": duration_ms,
                "tokens_used": 0,
                "provider": "none",
                "error": str(exc),
            }

    async def _auto_learn(
        self,
        action: str,
        params: dict[str, Any],
        result: dict[str, Any],
        reasoning: str,
        watchlist: list[str],
    ) -> None:
        try:
            memory = get_memory_orchestrator()
            content = (
                f"Action: {action}\nParams: {params}\n"
                f"Result: {result}\nReasoning: {reasoning}"
            )
            lesson = LessonCreate(
                title=f"Auto-observation: {action}",
                content=content[:500],
                lesson_type="observation",
                market_context=", ".join(watchlist[:3]),
                importance=3,
                tags=[action, "auto-observation"],
            )
            await memory.long_term.save_lesson(lesson)
        except Exception as exc:
            logger.debug(f"Auto-learn skipped: {exc}")

    def get_status(self) -> dict[str, Any]:
        return {
            "cycle_count": self._cycle_count,
            "last_cycle_at": self._last_cycle_at.isoformat() if self._last_cycle_at else None,
            "current_action": self._current_action,
            "uptime_seconds": time.monotonic() - self._start_time,
        }


_brain: Optional[Brain] = None


def get_brain() -> Brain:
    global _brain
    if _brain is None:
        _brain = Brain()
    return _brain
