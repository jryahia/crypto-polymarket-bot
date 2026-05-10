"""Dashboard view — real-time portfolio overview and brain cycle status."""

from __future__ import annotations

import asyncio
from typing import Any

import flet as ft
import httpx

from src.ui.components import (
    ACCENT, DARK_BG, DARK_CARD, DARK_SURFACE, GREEN, RED, TEXT_PRIMARY,
    TEXT_SECONDARY, YELLOW, badge, card, divider, pnl_text, primary_button,
    section_header, stat_card, loading_spinner,
)


API_BASE = "http://localhost:8000"


class DashboardView(ft.Column):
    def __init__(self) -> None:
        super().__init__(expand=True, spacing=16, scroll=ft.ScrollMode.AUTO)
        self._status: dict[str, Any] = {}
        self._portfolio: dict[str, Any] = {}
        self._cycles: list[dict[str, Any]] = []
        self._loading = True

    def build(self) -> ft.Column:
        self.controls = [loading_spinner("Loading dashboard...")]
        return self

    async def load_data(self) -> None:
        async with httpx.AsyncClient(timeout=10.0) as http:
            try:
                r = await http.get(f"{API_BASE}/api/status")
                self._status = r.json() if r.status_code == 200 else {}
            except Exception:
                self._status = {}

            try:
                r = await http.get(f"{API_BASE}/api/portfolio")
                self._portfolio = r.json() if r.status_code == 200 else {}
            except Exception:
                self._portfolio = {}

            try:
                r = await http.get(f"{API_BASE}/api/brain/cycles?limit=5")
                self._cycles = r.json() if r.status_code == 200 else []
            except Exception:
                self._cycles = []

        self._loading = False
        self._rebuild()

    def _rebuild(self) -> None:
        status = self._status
        portfolio = self._portfolio
        cycles = self._cycles

        bot_status = status.get("status", "unknown")
        status_color = GREEN if bot_status == "running" else (RED if bot_status == "error" else YELLOW)

        total_val = portfolio.get("total_value_usd", 0)
        daily_pnl = status.get("daily_pnl_usd", 0)
        open_pos = status.get("positions_count", 0)
        cycle_count = status.get("cycle_count", 0)
        uptime = int(status.get("uptime_seconds", 0))
        uptime_str = f"{uptime // 3600}h {(uptime % 3600) // 60}m"

        stat_row = ft.Row(
            [
                stat_card("Total Portfolio", f"${total_val:,.2f}", TEXT_PRIMARY, ft.icons.ACCOUNT_BALANCE_WALLET),
                stat_card("Daily P&L", f"{'+'if daily_pnl>=0 else ''}${daily_pnl:.2f}",
                          GREEN if daily_pnl >= 0 else RED, ft.icons.TRENDING_UP),
                stat_card("Open Positions", str(open_pos), ACCENT, ft.icons.SHOW_CHART),
                stat_card("Brain Cycles", str(cycle_count), ACCENT, ft.icons.PSYCHOLOGY),
                stat_card("Uptime", uptime_str, TEXT_SECONDARY, ft.icons.TIMER),
            ],
            spacing=12,
            wrap=True,
        )

        status_card = card(
            ft.Column([
                ft.Row([
                    ft.Container(
                        width=10, height=10,
                        bgcolor=status_color,
                        border_radius=5,
                    ),
                    ft.Text(f"Bot Status: {bot_status.upper()}", size=14,
                            color=status_color, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    primary_button("Run Cycle Now", self._on_run_cycle, ft.icons.PLAY_ARROW),
                ], spacing=8),
                ft.Container(height=8),
                ft.Row([
                    ft.Text("Live Trading:", size=12, color=TEXT_SECONDARY),
                    badge(
                        "ENABLED" if status.get("live_trading_enabled") else "PAPER",
                        GREEN if status.get("live_trading_enabled") else YELLOW,
                    ),
                    ft.Container(width=16),
                    ft.Text(f"Next cycle: {status.get('next_cycle_at', 'N/A')}", size=12, color=TEXT_SECONDARY),
                ], spacing=8),
            ], spacing=4)
        )

        positions_section = ft.Column([
            section_header("Open Positions", f"{open_pos} active"),
            ft.Container(height=8),
        ])

        pos_list = portfolio.get("open_positions", [])
        if pos_list:
            for pos in pos_list[:10]:
                pnl = pos.get("unrealized_pnl", 0)
                pnl_pct = pos.get("unrealized_pnl_pct", 0)
                positions_section.controls.append(
                    card(ft.Row([
                        ft.Column([
                            ft.Text(pos.get("symbol", ""), size=14,
                                    weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                            ft.Text(pos.get("exchange", ""), size=11, color=TEXT_SECONDARY),
                        ], spacing=2),
                        ft.Column([
                            ft.Text(pos.get("side", "").upper(), size=12, color=ACCENT),
                            ft.Text(f"qty: {pos.get('quantity', 0):.4f}", size=11, color=TEXT_SECONDARY),
                        ], spacing=2),
                        ft.Column([
                            ft.Text(f"Entry: ${pos.get('entry_price', 0):.4f}", size=12, color=TEXT_SECONDARY),
                            ft.Text(f"Now: ${pos.get('current_price', 0):.4f}", size=12, color=TEXT_PRIMARY),
                        ], spacing=2),
                        ft.Container(expand=True),
                        ft.Column([
                            pnl_text(pnl, 14),
                            ft.Text(f"{pnl_pct:+.2f}%", size=11,
                                    color=GREEN if pnl >= 0 else RED),
                        ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.END),
                    ], spacing=16))
                )
        else:
            positions_section.controls.append(
                ft.Text("No open positions", size=13, color=TEXT_SECONDARY, italic=True)
            )

        cycles_section = ft.Column([
            section_header("Recent Brain Cycles"),
            ft.Container(height=8),
        ])

        for c in cycles:
            action = c.get("action_taken") or "no action"
            conf = c.get("confidence") or 0
            executed = c.get("executed", False)
            error = c.get("error")
            cycles_section.controls.append(
                card(ft.Column([
                    ft.Row([
                        ft.Text(f"Cycle #{c.get('cycle_number', 0)}", size=13,
                                weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                        ft.Container(expand=True),
                        badge(
                            "EXECUTED" if executed else ("ERROR" if error else "SKIPPED"),
                            GREEN if executed else (RED if error else YELLOW),
                        ),
                        ft.Text(f"conf={conf:.2f}", size=11, color=TEXT_SECONDARY),
                    ], spacing=8),
                    ft.Text(f"Action: {action}", size=12, color=ACCENT),
                    ft.Text(
                        (c.get("reasoning") or "")[:200],
                        size=11, color=TEXT_SECONDARY,
                    ),
                ], spacing=4), padding=12)
            )

        self.controls = [
            stat_row,
            status_card,
            divider(),
            positions_section,
            divider(),
            cycles_section,
        ]
        if self.page:
            self.page.update()

    def _on_run_cycle(self, e: ft.ControlEvent) -> None:
        async def _do() -> None:
            try:
                async with httpx.AsyncClient(timeout=120.0) as http:
                    await http.post(f"{API_BASE}/api/cycle/run")
                await self.load_data()
            except Exception as exc:
                pass
        asyncio.create_task(_do())

    def did_mount(self) -> None:
        asyncio.create_task(self.load_data())
