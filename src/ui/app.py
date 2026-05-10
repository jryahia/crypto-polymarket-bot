"""Flet desktop application — main app shell with navigation rail."""

from __future__ import annotations

import flet as ft

from src.ui.components import (
    ACCENT, DARK_BG, DARK_CARD, DARK_BORDER, DARK_SURFACE,
    TEXT_PRIMARY, TEXT_SECONDARY, theme,
)


def build_app(page: ft.Page) -> None:
    page.title = "Aether Trading Bot"
    page.bgcolor = DARK_BG
    page.theme = theme()
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.fonts = {}
    page.window_width = 1280
    page.window_height = 820
    page.window_resizable = True

    from src.ui.dashboard import DashboardView
    from src.ui.chat_view import ChatView
    from src.ui.soul_view import SoulView
    from src.ui.skills_view import SkillsView
    from src.ui.memory_view import MemoryView
    from src.ui.scanner_view import ScannerView
    from src.ui.analytics_view import AnalyticsView

    views: list[ft.Control] = [
        DashboardView(),
        ChatView(),
        SoulView(),
        SkillsView(),
        MemoryView(),
        ScannerView(),
        AnalyticsView(),
    ]

    nav_items = [
        (ft.icons.DASHBOARD, "Dashboard"),
        (ft.icons.CHAT, "Chat"),
        (ft.icons.PSYCHOLOGY, "Soul"),
        (ft.icons.EXTENSION, "Skills"),
        (ft.icons.MEMORY, "Memory"),
        (ft.icons.RADAR, "Scanner"),
        (ft.icons.BAR_CHART, "Analytics"),
    ]

    content_area = ft.Container(
        content=views[0],
        expand=True,
        padding=20,
    )

    def on_nav_change(e: ft.ControlEvent) -> None:
        idx = e.control.selected_index
        content_area.content = views[idx]
        page.update()

    nav_rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=80,
        min_extended_width=180,
        bgcolor=DARK_CARD,
        indicator_color=ACCENT,
        on_change=on_nav_change,
        destinations=[
            ft.NavigationRailDestination(
                icon=icon,
                selected_icon=icon,
                label=label,
                padding=ft.padding.symmetric(vertical=4),
            )
            for icon, label in nav_items
        ],
        leading=ft.Container(
            content=ft.Column([
                ft.Icon(ft.icons.AUTO_AWESOME, color=ACCENT, size=28),
                ft.Text("AETHER", size=10, color=ACCENT, weight=ft.FontWeight.BOLD,
                        letter_spacing=2),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
            padding=ft.padding.symmetric(vertical=16),
        ),
    )

    status_bar = ft.Container(
        content=ft.Row([
            ft.Container(
                width=8, height=8, bgcolor="#22c55e", border_radius=4,
            ),
            ft.Text("API: localhost:8000", size=11, color=TEXT_SECONDARY),
            ft.Container(expand=True),
            ft.Text("Aether v1.0 | Dark Theme", size=11, color=TEXT_SECONDARY),
        ], spacing=6),
        bgcolor=DARK_CARD,
        padding=ft.padding.symmetric(horizontal=16, vertical=6),
        border=ft.border.only(top=ft.BorderSide(1, DARK_BORDER)),
    )

    layout = ft.Column([
        ft.Row([
            nav_rail,
            ft.VerticalDivider(color=DARK_BORDER, width=1),
            content_area,
        ], expand=True, spacing=0),
        status_bar,
    ], expand=True, spacing=0)

    page.add(layout)
    page.update()


def run_ui() -> None:
    ft.app(target=build_app)
