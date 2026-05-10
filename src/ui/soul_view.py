"""Soul view — display and edit the bot's personality profile."""

from __future__ import annotations

import asyncio
from typing import Any

import flet as ft
import httpx

from src.ui.components import (
    ACCENT, DARK_CARD, DARK_BORDER, DARK_SURFACE, GREEN, RED, TEXT_PRIMARY,
    TEXT_SECONDARY, YELLOW, badge, card, divider, loading_spinner,
    primary_button, secondary_button, section_header, text_input,
)

API_BASE = "http://localhost:8000"


class SoulView(ft.Column):
    def __init__(self) -> None:
        super().__init__(expand=True, spacing=16, scroll=ft.ScrollMode.AUTO)
        self._soul: dict[str, Any] = {}
        self._editing = False
        self._feedback: ft.Control | None = None

        self._name_field = text_input("Name", "Bot name")
        self._personality_field = text_input("Personality", "Describe personality traits", multiline=True, min_lines=2, max_lines=4)
        self._philosophy_field = text_input("Decision Philosophy", "Trading philosophy", multiline=True, min_lines=2, max_lines=4)
        self._risk_field = text_input("Risk Tolerance", "0.0 to 1.0")
        self._max_pos_field = text_input("Max Position Size (USD)", "e.g. 1000")
        self._max_loss_field = text_input("Max Daily Loss (USD)", "e.g. 500")

    def build(self) -> ft.Column:
        self.controls = [loading_spinner("Loading soul profile...")]
        return self

    async def _load(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                r = await http.get(f"{API_BASE}/api/soul")
                if r.status_code == 200:
                    self._soul = r.json()
        except Exception as exc:
            self._soul = {"error": str(exc)}
        self._rebuild()

    def _rebuild(self) -> None:
        soul = self._soul
        if not soul or soul.get("error"):
            self.controls = [ft.Text("Failed to load soul profile", color=RED)]
            if self.page:
                self.page.update()
            return

        risk = soul.get("risk_tolerance", 0.3)
        risk_color = GREEN if risk < 0.4 else (RED if risk > 0.7 else YELLOW)

        header_card = card(ft.Column([
            ft.Row([
                ft.Icon(ft.icons.PSYCHOLOGY, color=ACCENT, size=28),
                ft.Column([
                    ft.Text(soul.get("name", "Aether"), size=22,
                            weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                    ft.Text(soul.get("personality", ""), size=13, color=TEXT_SECONDARY),
                ], spacing=2, expand=True),
                ft.Container(expand=True),
                badge("ACTIVE" if soul.get("is_active") else "INACTIVE",
                      GREEN if soul.get("is_active") else RED),
            ], spacing=12),
        ]))

        metrics_row = ft.Row([
            card(ft.Column([
                ft.Text("Risk Tolerance", size=11, color=TEXT_SECONDARY),
                ft.Text(f"{risk:.0%}", size=20, weight=ft.FontWeight.BOLD, color=risk_color),
                ft.ProgressBar(
                    value=risk, width=120, height=6,
                    bgcolor=DARK_BORDER, color=risk_color,
                ),
            ], spacing=6)),
            card(ft.Column([
                ft.Text("Max Position", size=11, color=TEXT_SECONDARY),
                ft.Text(f"${soul.get('max_position_size_usd', 0):,.0f}",
                        size=20, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            ], spacing=6)),
            card(ft.Column([
                ft.Text("Max Daily Loss", size=11, color=TEXT_SECONDARY),
                ft.Text(f"${soul.get('max_daily_loss_usd', 0):,.0f}",
                        size=20, weight=ft.FontWeight.BOLD, color=RED),
            ], spacing=6)),
        ], spacing=12, wrap=True)

        philosophy_card = card(ft.Column([
            ft.Text("Decision Philosophy", size=13, weight=ft.FontWeight.W_600, color=TEXT_SECONDARY),
            ft.Text(soul.get("decision_philosophy", ""), size=13, color=TEXT_PRIMARY, italic=True),
        ], spacing=8))

        ethics_items = [
            ft.Row([
                ft.Icon(ft.icons.SHIELD, size=14, color=GREEN),
                ft.Text(e, size=12, color=TEXT_PRIMARY),
            ], spacing=6)
            for e in soul.get("ethics", [])
        ]

        beliefs_items = [
            ft.Row([
                ft.Icon(ft.icons.LIGHTBULB_OUTLINE, size=14, color=ACCENT),
                ft.Text(b, size=12, color=TEXT_PRIMARY),
            ], spacing=6)
            for b in soul.get("core_beliefs", [])
        ]

        watchlist_chips = ft.Row(
            [badge(s, ACCENT) for s in soul.get("watchlist", [])],
            wrap=True, spacing=6,
        )

        categories_chips = ft.Row(
            [badge(c, "#7c3aed") for c in soul.get("polymarket_categories", [])],
            wrap=True, spacing=6,
        )

        edit_btn = primary_button(
            "Edit Soul" if not self._editing else "Cancel",
            self._toggle_edit,
            ft.icons.EDIT if not self._editing else ft.icons.CLOSE,
        )

        controls: list[ft.Control] = [
            section_header("Soul Profile", "Your bot's identity and decision framework"),
            header_card,
            metrics_row,
            philosophy_card,
            ft.Row([
                card(ft.Column([
                    ft.Text("Ethics", size=13, weight=ft.FontWeight.W_600, color=TEXT_SECONDARY),
                    *ethics_items,
                ], spacing=6)),
                card(ft.Column([
                    ft.Text("Core Beliefs", size=13, weight=ft.FontWeight.W_600, color=TEXT_SECONDARY),
                    *beliefs_items,
                ], spacing=6)),
            ], spacing=12, wrap=True),
            card(ft.Column([
                ft.Text("Crypto Watchlist", size=13, weight=ft.FontWeight.W_600, color=TEXT_SECONDARY),
                watchlist_chips,
                ft.Container(height=8),
                ft.Text("Polymarket Categories", size=13, weight=ft.FontWeight.W_600, color=TEXT_SECONDARY),
                categories_chips,
            ], spacing=8)),
            edit_btn,
        ]

        if self._editing:
            self._name_field.value = soul.get("name", "")
            self._personality_field.value = soul.get("personality", "")
            self._philosophy_field.value = soul.get("decision_philosophy", "")
            self._risk_field.value = str(soul.get("risk_tolerance", 0.3))
            self._max_pos_field.value = str(soul.get("max_position_size_usd", 1000))
            self._max_loss_field.value = str(soul.get("max_daily_loss_usd", 500))

            edit_card = card(ft.Column([
                ft.Text("Edit Soul Profile", size=16, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                self._name_field,
                self._personality_field,
                self._philosophy_field,
                ft.Row([self._risk_field, self._max_pos_field, self._max_loss_field], spacing=12),
                ft.Row([
                    primary_button("Save Changes", self._on_save, ft.icons.SAVE),
                    secondary_button("Cancel", self._toggle_edit),
                ], spacing=12),
            ], spacing=12))
            controls.append(edit_card)

        if self._feedback:
            controls.append(self._feedback)

        self.controls = controls
        if self.page:
            self.page.update()

    def _toggle_edit(self, e: ft.ControlEvent) -> None:
        self._editing = not self._editing
        self._rebuild()

    def _on_save(self, e: ft.ControlEvent) -> None:
        asyncio.create_task(self._save())

    async def _save(self) -> None:
        updates: dict[str, Any] = {}
        if self._name_field.value:
            updates["name"] = self._name_field.value
        if self._personality_field.value:
            updates["personality"] = self._personality_field.value
        if self._philosophy_field.value:
            updates["decision_philosophy"] = self._philosophy_field.value
        try:
            updates["risk_tolerance"] = float(self._risk_field.value or 0.3)
            updates["max_position_size_usd"] = float(self._max_pos_field.value or 1000)
            updates["max_daily_loss_usd"] = float(self._max_loss_field.value or 500)
        except ValueError:
            pass

        try:
            async with httpx.AsyncClient(timeout=10.0) as http:
                r = await http.post(f"{API_BASE}/api/soul/update", json=updates)
                if r.status_code == 200:
                    self._soul = r.json()
                    self._editing = False
                    from src.ui.components import success_banner
                    self._feedback = success_banner("Soul profile updated successfully")
                else:
                    from src.ui.components import error_banner
                    self._feedback = error_banner(f"Update failed: {r.text[:100]}")
        except Exception as exc:
            from src.ui.components import error_banner
            self._feedback = error_banner(str(exc))

        self._rebuild()

    def did_mount(self) -> None:
        asyncio.create_task(self._load())
