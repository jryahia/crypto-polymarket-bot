"""Reusable Flet UI components with dark theme."""

from __future__ import annotations

from typing import Any, Optional

import flet as ft


DARK_BG = "#0f1117"
DARK_SURFACE = "#1a1d27"
DARK_CARD = "#22263a"
DARK_BORDER = "#2e3350"
ACCENT = "#6366f1"
ACCENT_HOVER = "#818cf8"
GREEN = "#22c55e"
RED = "#ef4444"
YELLOW = "#f59e0b"
TEXT_PRIMARY = "#f1f5f9"
TEXT_SECONDARY = "#94a3b8"
TEXT_MUTED = "#475569"


def theme() -> ft.Theme:
    return ft.Theme(
        color_scheme_seed=ACCENT,
        color_scheme=ft.ColorScheme(
            primary=ACCENT,
            background=DARK_BG,
            surface=DARK_SURFACE,
            on_background=TEXT_PRIMARY,
            on_surface=TEXT_PRIMARY,
        ),
    )


def card(content: ft.Control, padding: int = 16) -> ft.Container:
    return ft.Container(
        content=content,
        bgcolor=DARK_CARD,
        border_radius=12,
        padding=padding,
        border=ft.border.all(1, DARK_BORDER),
    )


def stat_card(label: str, value: str, color: str = TEXT_PRIMARY, icon: Optional[str] = None) -> ft.Container:
    row_content: list[ft.Control] = []
    if icon:
        row_content.append(ft.Icon(icon, size=18, color=color))
        row_content.append(ft.Container(width=6))
    row_content.append(ft.Text(label, size=12, color=TEXT_SECONDARY))

    return card(
        ft.Column(
            [
                ft.Row(row_content),
                ft.Text(value, size=22, weight=ft.FontWeight.BOLD, color=color),
            ],
            spacing=4,
        )
    )


def section_header(title: str, subtitle: str = "") -> ft.Column:
    children: list[ft.Control] = [
        ft.Text(title, size=18, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY)
    ]
    if subtitle:
        children.append(ft.Text(subtitle, size=12, color=TEXT_SECONDARY))
    return ft.Column(children, spacing=2)


def badge(text: str, color: str = ACCENT) -> ft.Container:
    return ft.Container(
        content=ft.Text(text, size=11, color="white", weight=ft.FontWeight.W_600),
        bgcolor=color,
        border_radius=4,
        padding=ft.padding.symmetric(horizontal=8, vertical=3),
    )


def pnl_text(value: float, size: int = 14) -> ft.Text:
    color = GREEN if value >= 0 else RED
    prefix = "+" if value >= 0 else ""
    return ft.Text(f"{prefix}${value:.2f}", size=size, color=color, weight=ft.FontWeight.W_600)


def signal_badge(signal: str) -> ft.Container:
    color_map = {
        "buy": GREEN, "strong_buy": GREEN,
        "sell": RED, "strong_sell": RED,
        "hold": YELLOW, "neutral": TEXT_MUTED,
    }
    color = color_map.get(signal.lower(), TEXT_SECONDARY)
    return badge(signal.upper(), color)


def loading_spinner(message: str = "Loading...") -> ft.Column:
    return ft.Column(
        [
            ft.ProgressRing(color=ACCENT, width=32, height=32),
            ft.Text(message, size=13, color=TEXT_SECONDARY),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=12,
    )


def error_banner(message: str) -> ft.Container:
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.icons.ERROR_OUTLINE, color=RED, size=18),
                ft.Text(message, color=RED, size=13),
            ],
            spacing=8,
        ),
        bgcolor="#2d1515",
        border_radius=8,
        padding=12,
        border=ft.border.all(1, RED),
    )


def success_banner(message: str) -> ft.Container:
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.icons.CHECK_CIRCLE_OUTLINE, color=GREEN, size=18),
                ft.Text(message, color=GREEN, size=13),
            ],
            spacing=8,
        ),
        bgcolor="#0d2d17",
        border_radius=8,
        padding=12,
        border=ft.border.all(1, GREEN),
    )


def divider() -> ft.Divider:
    return ft.Divider(color=DARK_BORDER, height=1)


def nav_rail_dest(icon: str, label: str) -> ft.NavigationRailDestination:
    return ft.NavigationRailDestination(
        icon=icon,
        selected_icon=icon,
        label=label,
    )


def primary_button(text: str, on_click: Any, icon: Optional[str] = None) -> ft.ElevatedButton:
    return ft.ElevatedButton(
        text=text,
        icon=icon,
        on_click=on_click,
        bgcolor=ACCENT,
        color="white",
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8),
        ),
    )


def secondary_button(text: str, on_click: Any, icon: Optional[str] = None) -> ft.OutlinedButton:
    return ft.OutlinedButton(
        text=text,
        icon=icon,
        on_click=on_click,
        style=ft.ButtonStyle(
            side=ft.BorderSide(1, ACCENT),
            color=ACCENT,
            shape=ft.RoundedRectangleBorder(radius=8),
        ),
    )


def text_input(
    label: str,
    hint: str = "",
    value: str = "",
    on_change: Any = None,
    multiline: bool = False,
    min_lines: int = 1,
    max_lines: int = 1,
) -> ft.TextField:
    return ft.TextField(
        label=label,
        hint_text=hint,
        value=value,
        on_change=on_change,
        multiline=multiline,
        min_lines=min_lines,
        max_lines=max_lines,
        border_color=DARK_BORDER,
        focused_border_color=ACCENT,
        label_style=ft.TextStyle(color=TEXT_SECONDARY),
        text_style=ft.TextStyle(color=TEXT_PRIMARY),
        bgcolor=DARK_SURFACE,
        border_radius=8,
    )
