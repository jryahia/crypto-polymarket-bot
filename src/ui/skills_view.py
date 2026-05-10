"""Skills view — list, run, and install bot skills."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import flet as ft
import httpx

from src.ui.components import (
    ACCENT, DARK_CARD, DARK_BORDER, DARK_SURFACE, GREEN, RED, TEXT_PRIMARY,
    TEXT_SECONDARY, YELLOW, badge, card, divider, error_banner,
    loading_spinner, primary_button, secondary_button, section_header,
    success_banner, text_input,
)

API_BASE = "http://localhost:8000"


class SkillsView(ft.Column):
    def __init__(self) -> None:
        super().__init__(expand=True, spacing=16, scroll=ft.ScrollMode.AUTO)
        self._skills: list[dict[str, Any]] = []
        self._selected_skill: dict[str, Any] | None = None
        self._params_input = text_input(
            "Params (JSON)", '{"symbol": "BTCUSDT"}', multiline=True, min_lines=3, max_lines=8
        )
        self._result_text = ft.Text("", size=12, color=TEXT_SECONDARY, selectable=True)
        self._feedback: ft.Control | None = None
        self._install_name = text_input("Skill Name", "my_skill")
        self._install_code = text_input(
            "Skill Code (Python)", "DESCRIPTION = '...'\nasync def execute(params):\n    return {}",
            multiline=True, min_lines=8, max_lines=20,
        )
        self._show_install = False

    def build(self) -> ft.Column:
        self.controls = [loading_spinner("Loading skills...")]
        return self

    async def _load(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                r = await http.get(f"{API_BASE}/api/skills")
                self._skills = r.json() if r.status_code == 200 else []
        except Exception as exc:
            self._skills = []
        self._rebuild()

    def _rebuild(self) -> None:
        skill_cards: list[ft.Control] = []
        for skill in self._skills:
            is_selected = (
                self._selected_skill is not None
                and self._selected_skill.get("name") == skill.get("name")
            )
            skill_cards.append(
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.icons.EXTENSION, color=ACCENT, size=16),
                            ft.Text(
                                skill.get("name", ""),
                                size=14,
                                weight=ft.FontWeight.BOLD,
                                color=TEXT_PRIMARY,
                            ),
                            ft.Container(expand=True),
                            badge(
                                "ENABLED" if skill.get("is_enabled") else "DISABLED",
                                GREEN if skill.get("is_enabled") else RED,
                            ),
                        ], spacing=8),
                        ft.Text(skill.get("description", ""), size=12, color=TEXT_SECONDARY),
                        ft.Row([
                            ft.Text(f"Runs: {skill.get('execution_count', 0)}", size=11, color=TEXT_SECONDARY),
                        ]),
                    ], spacing=6),
                    bgcolor=DARK_CARD if not is_selected else "#1e2a4a",
                    border_radius=8,
                    padding=12,
                    border=ft.border.all(1, ACCENT if is_selected else DARK_BORDER),
                    on_click=lambda e, s=skill: self._select_skill(s),
                    ink=True,
                )
            )

        run_panel: list[ft.Control] = []
        if self._selected_skill:
            run_panel = [
                divider(),
                section_header(
                    f"Run: {self._selected_skill.get('name', '')}",
                    self._selected_skill.get("description", ""),
                ),
                ft.Container(height=4),
                ft.Text("Parameters", size=12, color=TEXT_SECONDARY),
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row([
                                ft.Text(k, size=11, color=ACCENT, weight=ft.FontWeight.W_600),
                                ft.Text(" — ", size=11, color=TEXT_SECONDARY),
                                ft.Text(v, size=11, color=TEXT_SECONDARY),
                            ], spacing=2)
                            for k, v in self._selected_skill.get("params", {}).items()
                        ],
                        spacing=4,
                    ),
                    bgcolor=DARK_SURFACE,
                    border_radius=8,
                    padding=10,
                ),
                self._params_input,
                primary_button("Execute Skill", self._on_execute, ft.icons.PLAY_ARROW),
                ft.Container(height=4),
                ft.Text("Result:", size=12, color=TEXT_SECONDARY),
                ft.Container(
                    content=self._result_text,
                    bgcolor=DARK_SURFACE,
                    border_radius=8,
                    padding=12,
                    expand=True,
                ),
            ]

        install_panel: list[ft.Control] = []
        if self._show_install:
            install_panel = [
                divider(),
                section_header("Install New Skill", "Add a custom skill module"),
                self._install_name,
                self._install_code,
                ft.Row([
                    primary_button("Install", self._on_install, ft.icons.UPLOAD),
                    secondary_button("Cancel", lambda e: self._toggle_install()),
                ], spacing=12),
            ]

        controls: list[ft.Control] = [
            ft.Row([
                section_header("Skills", f"{len(self._skills)} loaded"),
                ft.Container(expand=True),
                secondary_button(
                    "Install New Skill" if not self._show_install else "Cancel Install",
                    lambda e: self._toggle_install(),
                    ft.icons.ADD,
                ),
                ft.IconButton(
                    icon=ft.icons.REFRESH,
                    icon_color=ACCENT,
                    on_click=lambda e: asyncio.create_task(self._load()),
                    tooltip="Reload skills",
                ),
            ], spacing=8),
            ft.GridView(
                controls=skill_cards,
                max_extent=300,
                runs_count=3,
                spacing=8,
                run_spacing=8,
            ),
            *run_panel,
            *install_panel,
        ]

        if self._feedback:
            controls.append(self._feedback)

        self.controls = controls
        if self.page:
            self.page.update()

    def _select_skill(self, skill: dict[str, Any]) -> None:
        if self._selected_skill and self._selected_skill.get("name") == skill.get("name"):
            self._selected_skill = None
        else:
            self._selected_skill = skill
            params = skill.get("params", {})
            example = {k: "" for k in params}
            self._params_input.value = json.dumps(example, indent=2)
        self._result_text.value = ""
        self._rebuild()

    def _on_execute(self, e: ft.ControlEvent) -> None:
        asyncio.create_task(self._execute())

    async def _execute(self) -> None:
        if not self._selected_skill:
            return
        name = self._selected_skill.get("name", "")
        try:
            params = json.loads(self._params_input.value or "{}")
        except json.JSONDecodeError as exc:
            self._result_text.value = f"Invalid JSON params: {exc}"
            if self.page:
                self.page.update()
            return

        try:
            async with httpx.AsyncClient(timeout=60.0) as http:
                r = await http.post(f"{API_BASE}/api/skills/{name}/execute", json=params)
                result = r.json()
                self._result_text.value = json.dumps(result, indent=2, default=str)
        except Exception as exc:
            self._result_text.value = f"Error: {exc}"

        if self.page:
            self.page.update()

    def _toggle_install(self) -> None:
        self._show_install = not self._show_install
        self._rebuild()

    def _on_install(self, e: ft.ControlEvent) -> None:
        asyncio.create_task(self._install())

    async def _install(self) -> None:
        name = self._install_name.value.strip()
        code = self._install_code.value.strip()
        if not name or not code:
            self._feedback = error_banner("Name and code are required")
            self._rebuild()
            return
        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                r = await http.post(
                    f"{API_BASE}/api/skills/install",
                    params={"name": name, "code": code},
                )
                data = r.json()
                if data.get("success"):
                    self._feedback = success_banner(f"Skill '{name}' installed successfully")
                    self._show_install = False
                    await self._load()
                    return
                else:
                    self._feedback = error_banner(f"Install failed: {data}")
        except Exception as exc:
            self._feedback = error_banner(str(exc))
        self._rebuild()

    def did_mount(self) -> None:
        asyncio.create_task(self._load())
