"""Alert management system — price alerts, RSI alerts, and notifications."""

from __future__ import annotations

import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

from loguru import logger
from sqlalchemy import select

from src.config import get_settings
from src.database import get_session
from src.models import Alert
from src.schemas import AlertCreate, AlertSchema

settings = get_settings()


class AlertManager:
    """Manages alert lifecycle: creation, evaluation, and notification delivery."""

    async def create_alert(self, data: AlertCreate) -> AlertSchema:
        async with get_session() as session:
            alert = Alert(
                alert_type=data.alert_type,
                symbol=data.symbol,
                condition=data.condition,
                threshold=data.threshold,
                message=data.message,
                is_active=True,
            )
            session.add(alert)
            await session.commit()
            await session.refresh(alert)
            logger.info(f"Alert created: {alert.symbol} {alert.condition} {alert.threshold}")
            return AlertSchema.model_validate(alert)

    async def get_active_alerts(self) -> list[AlertSchema]:
        async with get_session() as session:
            result = await session.execute(
                select(Alert).where(Alert.is_active.is_(True))
            )
            alerts = result.scalars().all()
            return [AlertSchema.model_validate(a) for a in alerts]

    async def disable_alert(self, alert_id: str) -> bool:
        async with get_session() as session:
            result = await session.execute(select(Alert).where(Alert.id == alert_id))
            alert = result.scalars().first()
            if not alert:
                return False
            alert.is_active = False
            await session.commit()
            return True

    async def check_price_alerts(self, market_prices: dict[str, float]) -> list[dict[str, Any]]:
        """Evaluate all active price alerts against current market prices."""
        alerts = await self.get_active_alerts()
        triggered: list[dict[str, Any]] = []

        for alert in alerts:
            if alert.alert_type not in ("price", "rsi", "volume"):
                continue

            current = market_prices.get(alert.symbol)
            if current is None:
                continue

            fired = False
            if alert.condition == "above" and current > alert.threshold:
                fired = True
            elif alert.condition == "below" and current < alert.threshold:
                fired = True

            if fired:
                triggered.append({
                    "alert_id": alert.id,
                    "symbol": alert.symbol,
                    "condition": alert.condition,
                    "threshold": alert.threshold,
                    "current": current,
                    "message": alert.message or f"{alert.symbol} {alert.condition} {alert.threshold}",
                })
                await self._mark_triggered(alert.id)
                await self._send_notification(
                    subject=f"🚨 Alert: {alert.symbol} {alert.condition} ${alert.threshold}",
                    body=f"{alert.symbol} is at ${current:.4f}, which is {alert.condition} your alert of ${alert.threshold:.4f}",
                )

        return triggered

    async def _mark_triggered(self, alert_id: str) -> None:
        async with get_session() as session:
            result = await session.execute(select(Alert).where(Alert.id == alert_id))
            alert = result.scalars().first()
            if alert:
                alert.triggered_count += 1
                alert.last_triggered = datetime.utcnow()
                # Deactivate one-shot alerts
                if alert.alert_type == "price":
                    alert.is_active = False
                await session.commit()

    async def _send_notification(self, subject: str, body: str) -> None:
        """Send email notification if SMTP is configured."""
        if not all([settings.smtp_username, settings.smtp_password, settings.alert_email]):
            logger.debug(f"Email not configured, skipping notification: {subject}")
            return

        try:
            msg = MIMEMultipart()
            msg["From"] = settings.smtp_username
            msg["To"] = settings.alert_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(settings.smtp_username, settings.smtp_password)
                server.sendmail(settings.smtp_username, settings.alert_email, msg.as_string())

            logger.info(f"Notification sent: {subject}")
        except Exception as exc:
            logger.error(f"Failed to send notification: {exc}")

    async def send_report(self, subject: str, body: str) -> bool:
        """Send a performance report via email."""
        try:
            await self._send_notification(subject=subject, body=body)
            return True
        except Exception:
            return False


_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager
