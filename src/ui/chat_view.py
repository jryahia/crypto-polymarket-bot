"""Chat view — real-time conversation with the bot's soul."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import flet as ft
import httpx

from src.ui.components import (
    ACCENT, DARK_CARD, DARK_SURFACE, GREEN, TEXT_PRIMARY, TEXT_SECONDARY,
    DARK_BG, DARK_BORDER, card, primary_button, text_input,
)

API_BASE = "http://localhost:8000"


class ChatView(ft.Column):
    def __init__(self) -> None:
        super().__init__(expand=True, spacing=0)
        self._session_id = str(uuid.uuid4())
        self._messages: list[dict[str, Any]] = []
        self._input = ft.TextField(
            hint_text="Ask Aether anything...",
            border_color=DARK_BORDER,
            focused_border_color=ACCENT,
            text_style=ft.TextStyle(color=TEXT_PRIMARY),
            bgcolor=DARK_SURFACE,
            border_radius=8,
            expand=True,
            on_submit=self._on_send,
            shift_enter=True,
            multiline=True,
            min_lines=1,
            max_lines=4,
        )
        self._messages_col = ft.Column(
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )
        self._sending = False

    def build(self) -> ft.Column:
        header = ft.Container(
            content=ft.Row([
                ft.Icon(ft.icons.PSYCHOLOGY, color=ACCENT, size=20),
                ft.Text("Chat with Aether", size=16, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
                ft.Container(expand=True),
                ft.Text(f"Session: {self._session_id[:8]}...", size=11, color=TEXT_SECONDARY),
            ], spacing=8),
            padding=ft.padding.all(16),
            bgcolor=DARK_CARD,
            border_radius=ft.border_radius.only(top_left=12, top_right=12),
        )

        messages_container = ft.Container(
            content=self._messages_col,
            expand=True,
            padding=16,
        )

        input_row = ft.Container(
            content=ft.Row([
                self._input,
                ft.Container(width=8),
                ft.IconButton(
                    icon=ft.icons.SEND,
                    icon_color=ACCENT,
                    on_click=self._on_send,
                    tooltip="Send message",
                ),
            ], spacing=0),
            padding=12,
            bgcolor=DARK_CARD,
            border_radius=ft.border_radius.only(bottom_left=12, bottom_right=12),
            border=ft.border.only(top=ft.BorderSide(1, DARK_BORDER)),
        )

        self.controls = [header, messages_container, input_row]
        return self

    def _build_message_bubble(self, role: str, content: str) -> ft.Container:
        is_user = role == "user"
        bgcolor = ACCENT if is_user else DARK_CARD
        text_color = "white" if is_user else TEXT_PRIMARY
        align = ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START

        bubble = ft.Container(
            content=ft.Column([
                ft.Text(
                    "You" if is_user else "Aether",
                    size=11,
                    color="white" if is_user else ACCENT,
                    weight=ft.FontWeight.W_600,
                ),
                ft.Text(content, size=13, color=text_color, selectable=True),
            ], spacing=4),
            bgcolor=bgcolor,
            border_radius=12,
            padding=12,
            max_width=560,
        )

        return ft.Row([bubble], alignment=align)

    def _on_send(self, e: ft.ControlEvent) -> None:
        msg = self._input.value.strip()
        if not msg or self._sending:
            return
        self._input.value = ""
        self._input.update()
        asyncio.create_task(self._send_message(msg))

    async def _send_message(self, message: str) -> None:
        self._sending = True
        self._messages.append({"role": "user", "content": message})
        self._messages_col.controls.append(self._build_message_bubble("user", message))

        typing_indicator = ft.Container(
            content=ft.Row([
                ft.ProgressRing(width=16, height=16, color=ACCENT),
                ft.Text("Aether is thinking...", size=12, color=TEXT_SECONDARY, italic=True),
            ], spacing=8),
            padding=ft.padding.symmetric(vertical=4),
        )
        self._messages_col.controls.append(typing_indicator)
        if self.page:
            self.page.update()

        try:
            async with httpx.AsyncClient(timeout=60.0) as http:
                resp = await http.post(
                    f"{API_BASE}/api/chat",
                    json={"message": message, "session_id": self._session_id},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    reply = data.get("response", "")
                else:
                    reply = f"Error {resp.status_code}: {resp.text[:200]}"
        except Exception as exc:
            reply = f"Connection error: {exc}"

        self._messages_col.controls.remove(typing_indicator)
        self._messages.append({"role": "assistant", "content": reply})
        self._messages_col.controls.append(self._build_message_bubble("assistant", reply))
        self._sending = False

        if self.page:
            self.page.update()
            self._messages_col.scroll_to(offset=-1, animate=True)

    def did_mount(self) -> None:
        welcome = (
            "Hello! I'm Aether, your autonomous trading agent. "
            "I'm analyzing markets and managing your portfolio. "
            "Ask me about my current strategy, market conditions, recent trades, or anything else."
        )
        self._messages_col.controls.append(self._build_message_bubble("assistant", welcome))
