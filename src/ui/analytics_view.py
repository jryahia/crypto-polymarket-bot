"""Analytics view — performance stats, trade history, and P&L charts."""

from __future__ import annotations

import asyncio
from typing import Any

import flet as ft
import httpx

from src.ui.components import (
    ACCENT, DARK_BORDER, DARK_CARD, DARK_SURFACE, GREEN, RED, TEXT_PRIMARY,
    TEXT_SECONDARY, YELLOW, badge, card, divider, loading_spinner,
    primary_button, section_header, pnl_text,
)

API_BASE = "http://localhost:8000"


class AnalyticsView(ft.Column):
    def __init__(self) -> None:
        super().__init__(expand=True, spacing=16, scroll=ft.ScrollMode.AUTO)
        self._trades: list[dict[str, Any]] = []
        self._portfolio: dict[str, Any] = {}
        self._cycles: list[dict[str, Any]] = []

    def build(self) -> ft.Column:
        self.controls = [loading_spinner("Loading analytics...")]
        return self

    async def _load(self) -> None:
        async with httpx.AsyncClient(timeout=15.0) as http:
            try:
                r = await http.get(f"{API_BASE}/api/trades?limit=100")
                self._trades = r.json() if r.status_code == 200 else []
            except Exception:
                self._trades = []
            try:
                r = await http.get(f"{API_BASE}/api/portfolio")
                self._portfolio = r.json() if r.status_code == 200 else {}
            except Exception:
                self._portfolio = {}
            try:
                r = await http.get(f"{API_BASE}/api/brain/cycles?limit=50")
                self._cycles = r.json() if r.status_code == 200 else []
            except Exception:
                self._cycles = []
        self._rebuild()

    def _rebuild(self) -> None:
        perf = self._portfolio.get("performance", {})
        total_trades = perf.get("total_trades", len(self._trades))
        closed = [t for t in self._trades if t.get("status") == "closed"]
        pnls = [t.get("pnl_usd") or 0 for t in closed if t.get("pnl_usd") is not None]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        win_rate = len(wins) / len(pnls) if pnls else 0.0
        total_pnl = sum(pnls)
        gross_profit = sum(wins) if wins else 0.0
        gross_loss = abs(sum(losses)) if losses else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")
        best = max(pnls) if pnls else 0.0
        worst = min(pnls) if pnls else 0.0

        metrics = ft.Row([
            card(ft.Column([
                ft.Text("Total Trades", size=11, color=TEXT_SECONDARY),
                ft.Text(str(total_trades), size=24, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            ], spacing=4)),
            card(ft.Column([
                ft.Text("Win Rate", size=11, color=TEXT_SECONDARY),
                ft.Text(f"{win_rate:.1%}", size=24, weight=ft.FontWeight.BOLD,
                        color=GREEN if win_rate >= 0.5 else RED),
                ft.ProgressBar(value=win_rate, width=120, height=6,
                               bgcolor=DARK_BORDER, color=GREEN if win_rate >= 0.5 else RED),
            ], spacing=4)),
            card(ft.Column([
                ft.Text("Total P&L", size=11, color=TEXT_SECONDARY),
                pnl_text(total_pnl, 24),
            ], spacing=4)),
            card(ft.Column([
                ft.Text("Profit Factor", size=11, color=TEXT_SECONDARY),
                ft.Text(
                    f"{profit_factor:.2f}" if profit_factor != float("inf") else "∞",
                    size=24, weight=ft.FontWeight.BOLD,
                    color=GREEN if profit_factor > 1.5 else (YELLOW if profit_factor > 1 else RED),
                ),
            ], spacing=4)),
            card(ft.Column([
                ft.Text("Best Trade", size=11, color=TEXT_SECONDARY),
                pnl_text(best, 20),
            ], spacing=4)),
            card(ft.Column([
                ft.Text("Worst Trade", size=11, color=TEXT_SECONDARY),
                pnl_text(worst, 20),
            ], spacing=4)),
        ], spacing=12, wrap=True)

        exchange_dist = {}
        for t in self._trades:
            ex = t.get("exchange", "unknown")
            exchange_dist[ex] = exchange_dist.get(ex, 0) + 1

        dist_bars = ft.Column([
            ft.Text("Trades by Exchange", size=13, weight=ft.FontWeight.W_600, color=TEXT_SECONDARY),
            *[
                ft.Column([
                    ft.Row([
                        ft.Text(ex, size=12, color=TEXT_PRIMARY, width=100),
                        ft.ProgressBar(
                            value=count / max(exchange_dist.values()) if exchange_dist else 0,
                            width=200,
                            height=8,
                            bgcolor=DARK_BORDER,
                            color=ACCENT,
                        ),
                        ft.Text(str(count), size=12, color=TEXT_SECONDARY),
                    ], spacing=8),
                ], spacing=4)
                for ex, count in exchange_dist.items()
            ],
        ], spacing=8)

        skill_dist: dict[str, int] = {}
        for t in self._trades:
            sk = t.get("skill_used") or "manual"
            skill_dist[sk] = skill_dist.get(sk, 0) + 1

        skill_bars = ft.Column([
            ft.Text("Trades by Skill", size=13, weight=ft.FontWeight.W_600, color=TEXT_SECONDARY),
            *[
                ft.Row([
                    ft.Text(sk, size=12, color=TEXT_PRIMARY, width=140),
                    ft.ProgressBar(
                        value=count / max(skill_dist.values()) if skill_dist else 0,
                        width=180,
                        height=8,
                        bgcolor=DARK_BORDER,
                        color="#7c3aed",
                    ),
                    ft.Text(str(count), size=12, color=TEXT_SECONDARY),
                ], spacing=8)
                for sk, count in sorted(skill_dist.items(), key=lambda x: x[1], reverse=True)
            ],
        ], spacing=6)

        trades_header = ft.Row([
            ft.Text("Symbol", size=12, color=TEXT_SECONDARY, width=100),
            ft.Text("Exchange", size=12, color=TEXT_SECONDARY, width=90),
            ft.Text("Side", size=12, color=TEXT_SECONDARY, width=50),
            ft.Text("Entry", size=12, color=TEXT_SECONDARY, width=90),
            ft.Text("Exit", size=12, color=TEXT_SECONDARY, width=90),
            ft.Text("P&L", size=12, color=TEXT_SECONDARY, width=80),
            ft.Text("Status", size=12, color=TEXT_SECONDARY, width=70),
        ])

        trade_rows = [trades_header, ft.Divider(color=DARK_BORDER, height=1)]
        for t in self._trades[:50]:
            pnl = t.get("pnl_usd") or 0
            status = t.get("status", "open")
            status_color = GREEN if status == "closed" and pnl >= 0 else (
                RED if status == "closed" and pnl < 0 else YELLOW
            )
            trade_rows.append(ft.Row([
                ft.Text(t.get("symbol", ""), size=12, color=TEXT_PRIMARY, width=100),
                ft.Text(t.get("exchange", ""), size=12, color=TEXT_SECONDARY, width=90),
                ft.Text(
                    t.get("side", "").upper(),
                    size=12,
                    color=GREEN if t.get("side", "").lower() in ("buy", "yes") else RED,
                    width=50,
                ),
                ft.Text(f"${t.get('entry_price', 0):.4f}", size=12, color=TEXT_SECONDARY, width=90),
                ft.Text(
                    f"${t.get('exit_price', 0):.4f}" if t.get("exit_price") else "—",
                    size=12, color=TEXT_SECONDARY, width=90,
                ),
                ft.Text(
                    f"{'+'if pnl>=0 else ''}${pnl:.2f}" if t.get("status") == "closed" else "—",
                    size=12, color=GREEN if pnl >= 0 else RED, width=80,
                ),
                badge(status.upper(), status_color),
            ]))

        cycle_stats_col = ft.Column([
            ft.Text("Brain Cycle Stats", size=14, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            ft.Row([
                card(ft.Column([
                    ft.Text("Total Cycles", size=11, color=TEXT_SECONDARY),
                    ft.Text(str(len(self._cycles)), size=20, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                ], spacing=4)),
                card(ft.Column([
                    ft.Text("Executed Actions", size=11, color=TEXT_SECONDARY),
                    ft.Text(
                        str(sum(1 for c in self._cycles if c.get("executed"))),
                        size=20, weight=ft.FontWeight.BOLD, color=GREEN,
                    ),
                ], spacing=4)),
                card(ft.Column([
                    ft.Text("Avg Confidence", size=11, color=TEXT_SECONDARY),
                    ft.Text(
                        f"{sum(c.get('confidence') or 0 for c in self._cycles) / max(len(self._cycles), 1):.0%}",
                        size=20, weight=ft.FontWeight.BOLD, color=ACCENT,
                    ),
                ], spacing=4)),
                card(ft.Column([
                    ft.Text("Total Tokens", size=11, color=TEXT_SECONDARY),
                    ft.Text(
                        f"{sum(c.get('tokens_used', 0) for c in self._cycles):,}",
                        size=20, weight=ft.FontWeight.BOLD, color=TEXT_SECONDARY,
                    ),
                ], spacing=4)),
            ], spacing=12, wrap=True),
        ], spacing=12)

        self.controls = [
            ft.Row([
                section_header("Analytics", f"{len(self._trades)} total trades"),
                ft.Container(expand=True),
                primary_button("Refresh", lambda e: asyncio.create_task(self._load()), ft.icons.REFRESH),
            ], spacing=8),
            metrics,
            divider(),
            ft.Row([
                card(dist_bars),
                card(skill_bars),
            ], spacing=12, wrap=True),
            divider(),
            cycle_stats_col,
            divider(),
            section_header("Trade History", f"Last {min(50, len(self._trades))} trades"),
            card(ft.Column(trade_rows, spacing=6)),
        ]
        if self.page:
            self.page.update()

    def did_mount(self) -> None:
        asyncio.create_task(self._load())
