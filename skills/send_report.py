"""Generate and send a performance report via email."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger

from src.alerts import get_alert_manager
from src.memory import get_memory_orchestrator

DESCRIPTION = "Generate and email a portfolio performance report with P&L, win rate, and recent trades"
PARAMS = {
    "period": "str — reporting period: daily, weekly, monthly (default: daily)",
    "include_trades": "bool — include trade list in report (default: true)",
}
RETURNS = "dict with report content and delivery status"


async def execute(params: dict[str, Any]) -> dict[str, Any]:
    period = params.get("period", "daily")
    include_trades = params.get("include_trades", True)

    memory = get_memory_orchestrator()
    stats = await memory.long_term.compute_performance_stats()
    open_positions = await memory.long_term.get_open_positions()
    recent_trades = await memory.long_term.get_recent_trades(20 if include_trades else 0)
    state = memory.short_term.get_state_snapshot()

    now = datetime.utcnow()
    report_lines = [
        f"=== Aether Trading Bot — {period.title()} Report ===",
        f"Generated: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        "--- PERFORMANCE SUMMARY ---",
        f"Total Trades:    {stats.get('total_trades', 0)}",
        f"Win Rate:        {stats.get('win_rate', 0):.1%}",
        f"Total P&L:       ${stats.get('total_pnl_usd', 0):+.2f}",
        f"Avg P&L/Trade:   ${stats.get('avg_pnl_usd', 0):+.2f}",
        f"Best Trade:      ${stats.get('best_trade_usd', 0):+.2f}",
        f"Worst Trade:     ${stats.get('worst_trade_usd', 0):+.2f}",
        f"Profit Factor:   {stats.get('profit_factor', 0):.2f}",
        "",
        "--- CURRENT STATE ---",
        f"Daily P&L:       ${state.get('daily_pnl', 0):+.2f}",
        f"Open Positions:  {len(open_positions)}",
        f"Brain Cycles:    {state.get('cycle_count', 0)}",
        f"Bot Status:      {state.get('bot_status', 'unknown')}",
        "",
    ]

    if open_positions:
        report_lines.append("--- OPEN POSITIONS ---")
        for pos in open_positions:
            pnl = pos.get("unrealized_pnl", 0)
            report_lines.append(
                f"  {pos['symbol']} {pos['side'].upper()} "
                f"qty={pos['quantity']:.4f} entry=${pos['entry_price']:.4f} "
                f"pnl={pnl:+.2f}$"
            )
        report_lines.append("")

    if include_trades and recent_trades:
        report_lines.append("--- RECENT TRADES ---")
        for t in recent_trades[:10]:
            pnl = t.get("pnl_usd", 0) or 0
            report_lines.append(
                f"  {t.get('symbol')} {t.get('side','?').upper()} "
                f"pnl={pnl:+.2f}$ [{t.get('status','?')}]"
            )
        report_lines.append("")

    report_lines.append("=== END REPORT ===")
    report_body = "\n".join(report_lines)

    subject = f"Aether Bot — {period.title()} Report {now.strftime('%Y-%m-%d')}"

    alert_manager = get_alert_manager()
    delivered = await alert_manager.send_report(subject=subject, body=report_body)

    logger.info(f"send_report: {period} report generated, delivered={delivered}")

    return {
        "success": True,
        "period": period,
        "subject": subject,
        "report": report_body,
        "delivered_via_email": delivered,
        "stats": stats,
        "generated_at": now.isoformat(),
    }
