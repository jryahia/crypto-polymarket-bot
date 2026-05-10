"""Memory view — search semantic memory and browse lessons."""

from __future__ import annotations

import asyncio
from typing import Any

import flet as ft
import httpx

from src.ui.components import (
    ACCENT, DARK_BORDER, DARK_CARD, DARK_SURFACE, GREEN, RED, TEXT_PRIMARY,
    TEXT_SECONDARY, YELLOW, badge, card, divider, error_banner,
    loading_spinner, primary_button, section_header, text_input,
)

API_BASE = "http://localhost:8000"

LESSON_TYPE_COLORS = {
    "success": GREEN,
    "failure": RED,
    "observation": ACCENT,
    "pattern": YELLOW,
}


class MemoryView(ft.Column):
    def __init__(self) -> None:
        super().__init__(expand=True, spacing=16, scroll=ft.ScrollMode.AUTO)
        self._lessons: list[dict[str, Any]] = []
        self._search_results: list[dict[str, Any]] = []
        self._search_input = ft.TextField(
            hint_text="Search semantic memory...",
            border_color=DARK_BORDER,
            focused_border_color=ACCENT,
            text_style=ft.TextStyle(color=TEXT_PRIMARY),
            bgcolor=DARK_SURFACE,
            border_radius=8,
            expand=True,
            on_submit=self._on_search,
            suffix_icon=ft.icons.SEARCH,
        )
        self._collection_dd = ft.Dropdown(
            value="lessons",
            options=[
                ft.dropdown.Option("lessons", "Lessons"),
                ft.dropdown.Option("trades", "Trade Outcomes"),
                ft.dropdown.Option("observations", "Market Observations"),
            ],
            bgcolor=DARK_SURFACE,
            border_color=DARK_BORDER,
            color=TEXT_PRIMARY,
            width=180,
        )
        self._tab_idx = 0

    def build(self) -> ft.Column:
        self.controls = [loading_spinner("Loading memory...")]
        return self

    async def _load_lessons(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                r = await http.get(f"{API_BASE}/api/lessons?limit=30")
                self._lessons = r.json() if r.status_code == 200 else []
        except Exception:
            self._lessons = []
        self._rebuild()

    def _rebuild(self) -> None:
        search_bar = ft.Row([
            self._search_input,
            ft.Container(width=8),
            self._collection_dd,
            ft.Container(width=8),
            primary_button("Search", self._on_search, ft.icons.SEARCH),
        ], spacing=0)

        lessons_col = ft.Column(spacing=10)
        if self._lessons:
            for l in self._lessons:
                ltype = l.get("lesson_type", "observation")
                color = LESSON_TYPE_COLORS.get(ltype, ACCENT)
                importance = l.get("importance", 5)
                tags = l.get("tags", [])

                lessons_col.controls.append(
                    card(ft.Column([
                        ft.Row([
                            badge(ltype.upper(), color),
                            ft.Container(expand=True),
                            ft.Row(
                                [ft.Icon(ft.icons.STAR, size=12, color=YELLOW)] * min(importance, 5),
                                spacing=2,
                            ),
                            ft.Text(f"recalled {l.get('times_recalled', 0)}x", size=10, color=TEXT_SECONDARY),
                        ], spacing=6),
                        ft.Text(
                            l.get("title", ""),
                            size=14,
                            weight=ft.FontWeight.BOLD,
                            color=TEXT_PRIMARY,
                        ),
                        ft.Text(l.get("content", "")[:300], size=12, color=TEXT_SECONDARY),
                        ft.Row([
                            *[badge(t, DARK_BORDER) for t in tags[:4]],
                            ft.Container(expand=True),
                            ft.Text(
                                l.get("market_context", "") or "",
                                size=10,
                                color=TEXT_SECONDARY,
                            ),
                        ], spacing=4, wrap=True),
                    ], spacing=6))
                )
        else:
            lessons_col.controls.append(
                ft.Text("No lessons stored yet — the bot learns from each trade.", size=13,
                        color=TEXT_SECONDARY, italic=True)
            )

        search_results_col = ft.Column(spacing=10)
        if self._search_results:
            for i, r in enumerate(self._search_results):
                relevance = 1.0 - r.get("distance", 0.5)
                search_results_col.controls.append(
                    card(ft.Column([
                        ft.Row([
                            badge(r.get("collection", "?").upper(), ACCENT),
                            ft.Container(expand=True),
                            ft.Text(
                                f"relevance: {relevance:.0%}",
                                size=11,
                                color=GREEN if relevance > 0.7 else TEXT_SECONDARY,
                            ),
                        ], spacing=6),
                        ft.Text(r.get("content", "")[:400], size=12, color=TEXT_PRIMARY, selectable=True),
                        ft.Text(
                            str(r.get("metadata", {}))[:200],
                            size=10, color=TEXT_SECONDARY,
                        ),
                    ], spacing=6))
                )

        tabs = ft.Tabs(
            selected_index=self._tab_idx,
            animation_duration=200,
            on_change=self._on_tab_change,
            tabs=[
                ft.Tab(
                    text=f"Lessons ({len(self._lessons)})",
                    icon=ft.icons.MENU_BOOK,
                    content=ft.Container(
                        content=lessons_col,
                        padding=ft.padding.only(top=16),
                    ),
                ),
                ft.Tab(
                    text=f"Search Results ({len(self._search_results)})",
                    icon=ft.icons.SEARCH,
                    content=ft.Container(
                        content=search_results_col
                        if self._search_results
                        else ft.Text("Use the search bar above to query semantic memory.",
                                     size=13, color=TEXT_SECONDARY, italic=True),
                        padding=ft.padding.only(top=16),
                    ),
                ),
            ],
            expand=True,
        )

        self.controls = [
            section_header("Memory", "Search semantic memory and browse lessons"),
            search_bar,
            tabs,
        ]
        if self.page:
            self.page.update()

    def _on_tab_change(self, e: ft.ControlEvent) -> None:
        self._tab_idx = e.control.selected_index

    def _on_search(self, e: ft.ControlEvent) -> None:
        asyncio.create_task(self._search())

    async def _search(self) -> None:
        query = self._search_input.value.strip()
        if not query:
            return
        collection = self._collection_dd.value or "lessons"
        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                r = await http.post(
                    f"{API_BASE}/api/memory/search",
                    json={"query": query, "n_results": 10, "collection": collection},
                )
                if r.status_code == 200:
                    data = r.json()
                    self._search_results = data.get("results", [])
                    for item in self._search_results:
                        item["collection"] = collection
                else:
                    self._search_results = []
        except Exception as exc:
            self._search_results = []

        self._tab_idx = 1
        self._rebuild()

    def did_mount(self) -> None:
        asyncio.create_task(self._load_lessons())
