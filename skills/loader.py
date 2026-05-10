"""Skill discovery, loader, and executor for the bot."""

from __future__ import annotations

import importlib.util
import inspect
import os
import time
from datetime import datetime
from typing import Any, Optional

from loguru import logger

from src.config import get_settings

settings = get_settings()


class SkillLoader:
    """Dynamically discovers and loads skill modules from the skills/ directory."""

    def __init__(self) -> None:
        self._skills: dict[str, dict[str, Any]] = {}
        self._execution_counts: dict[str, int] = {}
        self._last_executed: dict[str, datetime] = {}
        self._skills_dir = settings.skills_dir
        self._load_all()

    def _load_all(self) -> None:
        if not os.path.isdir(self._skills_dir):
            logger.warning(f"Skills directory not found: {self._skills_dir}")
            return
        for fname in sorted(os.listdir(self._skills_dir)):
            if fname.startswith("_") or not fname.endswith(".py"):
                continue
            self._load_skill(fname[:-3])
        logger.info(f"Loaded {len(self._skills)} skills: {list(self._skills.keys())}")

    def _load_skill(self, name: str) -> bool:
        path = os.path.join(self._skills_dir, f"{name}.py")
        if not os.path.exists(path):
            return False
        try:
            spec = importlib.util.spec_from_file_location(f"skills.{name}", path)
            if spec is None or spec.loader is None:
                return False
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[attr-defined]
            if not hasattr(module, "execute"):
                logger.warning(f"Skill '{name}' missing execute(), skipping")
                return False
            self._skills[name] = {
                "name": name,
                "description": getattr(module, "DESCRIPTION", f"Skill: {name}"),
                "params": getattr(module, "PARAMS", {}),
                "returns": getattr(module, "RETURNS", "dict"),
                "module": module,
                "is_enabled": True,
                "path": path,
            }
            return True
        except Exception as exc:
            logger.error(f"Failed to load skill '{name}': {exc}")
            return False

    def reload(self) -> None:
        self._skills.clear()
        self._load_all()
        logger.info("Skills hot-reloaded")

    def reload_skill(self, name: str) -> bool:
        return self._load_skill(name)

    def get_skill_list(self) -> list[dict[str, Any]]:
        return [
            {
                "name": s["name"],
                "description": s["description"],
                "params": s["params"],
                "returns": s["returns"],
                "is_enabled": s["is_enabled"],
                "last_executed": self._last_executed.get(s["name"]),
                "execution_count": self._execution_counts.get(s["name"], 0),
            }
            for s in self._skills.values()
        ]

    def get_skill(self, name: str) -> Optional[dict[str, Any]]:
        s = self._skills.get(name)
        if s is None:
            return None
        return {k: v for k, v in s.items() if k != "module"}

    async def execute_skill(self, name: str, params: dict[str, Any]) -> dict[str, Any]:
        skill = self._skills.get(name)
        if skill is None:
            raise ValueError(f"Skill '{name}' not found. Available: {list(self._skills.keys())}")
        if not skill["is_enabled"]:
            raise ValueError(f"Skill '{name}' is disabled")

        execute_fn = skill["module"].execute
        t0 = time.monotonic()
        try:
            if inspect.iscoroutinefunction(execute_fn):
                result = await execute_fn(params)
            else:
                result = execute_fn(params)
            duration_ms = int((time.monotonic() - t0) * 1000)
            self._execution_counts[name] = self._execution_counts.get(name, 0) + 1
            self._last_executed[name] = datetime.utcnow()
            logger.info(f"Skill '{name}' completed in {duration_ms}ms")
            return result if isinstance(result, dict) else {"result": result}
        except Exception as exc:
            logger.error(f"Skill '{name}' failed: {exc}")
            raise

    def enable_skill(self, name: str) -> bool:
        if name in self._skills:
            self._skills[name]["is_enabled"] = True
            return True
        return False

    def disable_skill(self, name: str) -> bool:
        if name in self._skills:
            self._skills[name]["is_enabled"] = False
            return True
        return False

    def install_skill(self, name: str, code: str) -> bool:
        path = os.path.join(self._skills_dir, f"{name}.py")
        try:
            with open(path, "w") as f:
                f.write(code)
            return self._load_skill(name)
        except Exception as exc:
            logger.error(f"Failed to install skill '{name}': {exc}")
            return False


_skill_loader: Optional[SkillLoader] = None


def get_skill_loader() -> SkillLoader:
    global _skill_loader
    if _skill_loader is None:
        _skill_loader = SkillLoader()
    return _skill_loader
