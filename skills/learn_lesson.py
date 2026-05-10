"""Save a lesson or insight to the bot's long-term memory."""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.memory import get_memory_orchestrator
from src.schemas import LessonCreate

DESCRIPTION = "Save a trading lesson or market insight to long-term semantic memory for future recall"
PARAMS = {
    "title": "str — short descriptive title for the lesson",
    "content": "str — detailed lesson content",
    "lesson_type": "str — success, failure, observation, or pattern (default: observation)",
    "market_context": "str — related market or symbol (optional)",
    "importance": "int — importance score 1-10 (default: 5)",
    "tags": "list[str] — optional tags for categorization",
}
RETURNS = "dict with saved lesson ID and chroma embedding ID"


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    title = params.get("title", "")
    content = params.get("content", "")
    lesson_type = params.get("lesson_type", "observation")
    market_context = params.get("market_context")
    importance = int(params.get("importance", 5))
    tags = params.get("tags", [])

    if not title:
        return {"error": "title is required"}
    if not content:
        return {"error": "content is required"}
    if lesson_type not in ("success", "failure", "observation", "pattern"):
        lesson_type = "observation"
    importance = max(1, min(10, importance))

    lesson_data = LessonCreate(
        title=title,
        content=content,
        lesson_type=lesson_type,
        market_context=market_context,
        importance=importance,
        tags=tags if isinstance(tags, list) else [],
    )

    memory = get_memory_orchestrator()
    try:
        lesson = await memory.long_term.save_lesson(lesson_data)
    except Exception as exc:
        logger.error(f"learn_lesson: save failed: {exc}")
        return {"error": str(exc)}

    logger.info(f"learn_lesson: saved '{title}' (type={lesson_type}, importance={importance})")

    return {
        "success": True,
        "lesson_id": lesson.id,
        "chroma_id": lesson.chroma_id,
        "title": lesson.title,
        "lesson_type": lesson.lesson_type,
        "importance": lesson.importance,
        "tags": lesson.tags,
    }
