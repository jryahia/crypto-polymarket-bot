"""Scanner view — scan markets for trading opportunities and Polymarket bets."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import flet as ft
import httpx

from src.ui.components import (
    ACCENT, DARK_BORDER, DARK_CARD, DARK_SURFACE, GREEN, RED, TEXT_MUTED,
    TEXT_PRIMARY, TEXT_SECONDARY, YELLOW, badge, card, divider,
    loading_spinner, primary_button, secondary_button, section_header,
    signal_badge,
)

API_BASE = "http://localhost:8000"


class ScannerView(ft.Column):
    def __init__(self) -> None:
        super().__init__(expand=True, spacing=16, scroll=ft.ScrollMode.AUTO)
        self._crypto_opps: list[dict[str, Any]] = []
        self._poly_opps: list[dict[str, Any]] = []
        self._scanning = False
        self._scanning_poly = False
        self._interval_dd = ft.Dropdown(
            value="1h",
            options=[
                ft.dropdown.Option("15m", "15m"),
                ft.dropdown.Option("1h", "1h"),
                ft.dropdown.Option("4h", "4h"),
                ft.dropdown.Option("1d", "1d"),
            ],
            bgcolor=DARK_SURFACE,
            border_color=DARK_BORDER,
            color=TEXT_PRIMARY,
            width=100,
        )
        self._category_dd = ft.Dropdown(
            value="",
            options=[
                ft.dropdown.Option("", "All Categories"),
                ft.dropdown.Option("crypto", "Crypto"),
                ft.dropdown.Option("economics", "Economics"),
                ft.dropdown.Option("science", "Science"),
                ft.dropdown.Option("politics", "Politics"),
            ],
            bgcolor=DARK_SURFACE,
            border_color=DARK_BORDER,
            color=TEXT_PRIMARY,
            width=160,
        )

    def build(self) -> ft.Column:
        self._rebuild()
        return self

    def _rebuild(self) -> None:
        scan_controls = ft.Row([
            ft.Icon(ft.icons.RADAR, color=ACCENT, size=20),
            section_header("Market Scanner"),
            ft.Container(expand=True),
            ft.Text("Interval:", size=12, color=TEXT_SECONDARY),
            self._interval_dd,
            primary_button(
                "Scan Crypto" if not self._scanning else "Scanning...",
                self._on_scan_crypto,
                ft.icons.SEARCH,
            ),
        ], spacing=8, wrap=True)

        poly_controls = ft.Row([
            ft.Icon(ft.icons.CASINO, color="#7c3aed", size=20),
            section_header("Polymarket Scanner"),
            ft.Container(expand=True),
            ft.Text("Category:", size=12, color=TEXT_SECONDARY),
            self._category_dd,
            primary_button(
                "Scan Markets" if not self._scanning_poly else "Scanning...",
                self._on_scan_poly,
                ft.icons.SEARCH,
            ),
        ], spacing=8, wrap=True)

        crypto_section = ft.Column([
            ft.Row([
                ft.Text("Crypto Opportunities", size=14, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                ft.Container(expand=True),
                ft.Text(f"{len(self._crypto_opps)} signals", size=11, color=TEXT_SECONDARY),
            ]),
        ], spacing=8)

        if self._scanning:
            crypto_section.controls.append(loading_spinner("Scanning..."))
        elif self._crypto_opps:
            for opp in self._crypto_opps:
                signal = opp.get("signal", "hold")
                score = opp.get("score", 0)
                score_color = GREEN if score > 0.6 else (YELLOW if score > 0.3 else TEXT_SECONDARY)
                crypto_section.controls.append(
                    card(ft.Column([
                        ft.Row([
                            ft.Text(opp.get("symbol", ""), size=14,
                                    weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                            ft.Container(width=8),
                            signal_badge(signal),
                            ft.Container(expand=True),
                            ft.Text(f"Score: {score:.3f}", size=12, color=score_color,
                                    weight=ft.FontWeight.W_600),
                        ], spacing=4),
                        ft.Row([
                            ft.Text(f"Price: ${opp.get('current_price', 0):.4f}", size=12, color=TEXT_SECONDARY),
                            ft.Container(width=12),
                            ft.Text(f"RSI: {opp.get('rsi', 0):.1f}", size=12,
                                    color=GREEN if opp.get('rsi', 50) < 35 else (RED if opp.get('rsi', 50) > 65 else TEXT_SECONDARY)),
                            ft.Container(width=12),
                            ft.Text(f"Support: ${opp.get('support', 0):.4f}", size=11, color=TEXT_SECONDARY),
                            ft.Container(width=8),
                            ft.Text(f"Resist: ${opp.get('resistance', 0):.4f}", size=11, color=TEXT_SECONDARY),
                        ], spacing=0),
                        ft.Row([
                            ft.Text(f"Dist. to support: {opp.get('dist_to_support_pct', 0):.2f}%",
                                    size=11, color=TEXT_SECONDARY),
                            ft.Container(width=12),
                            ft.Text(f"Dist. to resistance: {opp.get('dist_to_resistance_pct', 0):.2f}%",
                                    size=11, color=TEXT_SECONDARY),
                        ]),
                        secondary_button(
                            "Quick Trade",
                            lambda e, o=opp: self._quick_trade(o),
                            ft.icons.FLASH_ON,
                        ),
                    ], spacing=6))
                )
        else:
            crypto_section.controls.append(
                ft.Text("Click 'Scan Crypto' to find opportunities.", size=13,
                        color=TEXT_SECONDARY, italic=True)
            )

        poly_section = ft.Column([
            ft.Row([
                ft.Text("Polymarket Opportunities", size=14, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                ft.Container(expand=True),
                ft.Text(f"{len(self._poly_opps)} markets", size=11, color=TEXT_SECONDARY),
            ]),
        ], spacing=8)

        if self._scanning_poly:
            poly_section.controls.append(loading_spinner("Scanning Polymarket..."))
        elif self._poly_opps:
            for opp in self._poly_opps:
                edge = opp.get("edge_score", 0)
                rec = opp.get("recommendation", "skip")
                yes_price = opp.get("yes_price", 0.5)
                edge_color = GREEN if edge > 0.5 else (YELLOW if edge > 0.1 else TEXT_MUTED)
                poly_section.controls.append(
                    card(ft.Column([
                        ft.Row([
                            badge(rec.upper(), GREEN if "yes" in rec else (RED if "no" in rec else TEXT_SECONDARY)),
                            ft.Container(expand=True),
                            ft.Text(f"Edge: {edge:.3f}", size=12, color=edge_color,
                                    weight=ft.FontWeight.W_600),
                        ], spacing=4),
                        ft.Text(opp.get("question", "")[:120], size=13, color=TEXT_PRIMARY),
                        ft.Row([
                            ft.Text(f"YES: {yes_price:.0%}", size=12,
                                    color=GREEN if yes_price > 0.6 else TEXT_SECONDARY),
                            ft.Container(width=12),
                            ft.Text(f"NO: {opp.get('no_price', 0):.0%}", size=12,
                                    color=RED if opp.get('no_price', 0.5) > 0.6 else TEXT_SECONDARY),
                            ft.Container(width=12),
                            ft.Text(f"Vol: ${opp.get('volume', 0):,.0f}", size=11, color=TEXT_SECONDARY),
                            ft.Container(width=8),
                            ft.Text(f"Liq: ${opp.get('liquidity', 0):,.0f}", size=11, color=TEXT_SECONDARY),
                        ]),
                        secondary_button(
                            f"Bet {opp.get('suggested_side', 'YES').upper()}",
                            lambda e, o=opp: self._quick_bet(o),
                            ft.icons.CASINO,
                        ),
                    ], spacing=6))
                )
        else:
            poly_section.controls.append(
                ft.Text("Click 'Scan Markets' to find Polymarket opportunities.", size=13,
                        color=TEXT_SECONDARY, italic=True)
            )

        self.controls = [
            scan_controls,
            card(crypto_section),
            divider(),
            poly_controls,
            card(poly_section),
        ]
        if self.page:
            self.page.update()

    def _on_scan_crypto(self, e: ft.ControlEvent) -> None:
        asyncio.create_task(self._scan_crypto())

    async def _scan_crypto(self) -> None:
        self._scanning = True
        self._rebuild()
        try:
            async with httpx.AsyncClient(timeout=60.0) as http:
                r = await http.post(
                    f"{API_BASE}/api/skills/scan_opportunities/execute",
                    json={"interval": self._interval_dd.value, "top_n": 10},
                )
                if r.status_code == 200:
                    data = r.json()
                    self._crypto_opps = data.get("opportunities", [])
        except Exception:
            self._crypto_opps = []
        self._scanning = False
        self._rebuild()

    def _on_scan_poly(self, e: ft.ControlEvent) -> None:
        asyncio.create_task(self._scan_poly())

    async def _scan_poly(self) -> None:
        self._scanning_poly = True
        self._rebuild()
        try:
            params: dict[str, Any] = {"limit": 20, "min_volume": 500}
            cat = self._category_dd.value
            if cat:
                params["category"] = cat
            async with httpx.AsyncClient(timeout=30.0) as http:
                r = await http.post(
                    f"{API_BASE}/api/skills/check_polymarket/execute",
                    json=params,
                )
                if r.status_code == 200:
                    data = r.json()
                    self._poly_opps = data.get("top_opportunities", data.get("markets", []))[:10]
        except Exception:
            self._poly_opps = []
        self._scanning_poly = False
        self._rebuild()

    def _quick_trade(self, opp: dict[str, Any]) -> None:
        pass  # Would open a trade dialog

    def _quick_bet(self, opp: dict[str, Any]) -> None:
        pass  # Would open a bet dialog
