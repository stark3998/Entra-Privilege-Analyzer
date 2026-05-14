# backend/app/services/alert_delivery.py
"""Outbound alert delivery via email (Graph sendMail), Teams webhook, or
generic HMAC-signed webhook.

Each delivery method is isolated behind a private async helper so failures
in one channel never affect others.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from app.models.alert_rules import AlertChannel, AlertChannelType, AlertRule

logger = logging.getLogger(__name__)

# Type alias for the async callable that returns a Graph bearer token.
GraphTokenProvider = Callable[[], Awaitable[str]]


class AlertDeliveryService:
    """Delivers alerts via email, Teams, or webhook channels."""

    def __init__(self, graph_token_provider: GraphTokenProvider | None = None) -> None:
        self._graph_token_provider = graph_token_provider

    async def deliver(
        self,
        rule: AlertRule,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Deliver an alert based on the rule's channel configuration.

        Returns a dict with keys ``success``, ``channel``, and ``error``.
        """
        channel = rule.channel
        try:
            if channel.channel_type == AlertChannelType.EMAIL:
                await self._send_email(channel, rule, payload)
            elif channel.channel_type == AlertChannelType.TEAMS:
                await self._send_teams(channel, payload)
            elif channel.channel_type == AlertChannelType.WEBHOOK:
                await self._send_webhook(channel, payload)
            else:
                return {
                    "success": False,
                    "channel": channel.channel_type,
                    "error": f"Unsupported channel type: {channel.channel_type}",
                }

            logger.info(
                "Alert delivered: rule=%s channel=%s",
                rule.id,
                channel.channel_type,
            )
            return {"success": True, "channel": channel.channel_type, "error": None}

        except Exception as exc:
            logger.exception("Alert delivery failed: rule=%s", rule.id)
            return {
                "success": False,
                "channel": channel.channel_type,
                "error": str(exc),
            }

    # ------------------------------------------------------------------
    # Email — Microsoft Graph sendMail
    # ------------------------------------------------------------------

    async def _send_email(
        self,
        channel: AlertChannel,
        rule: AlertRule,
        payload: dict[str, Any],
    ) -> None:
        """Send alert via Microsoft Graph ``/me/sendMail`` endpoint."""
        if self._graph_token_provider is None:
            raise RuntimeError("Graph token provider not configured for email alerts")

        token = await self._graph_token_provider()
        recipients = channel.config.get("recipients", [])
        if not recipients:
            raise ValueError("No email recipients configured")

        # recipients may be a single string or a list — normalise.
        if isinstance(recipients, str):
            recipients = [recipients]

        subject = f"[Entra Analyzer] {payload.get('title', 'Security Alert')}"
        body_content = self._format_email_body(payload)

        message: dict[str, Any] = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": body_content},
                "toRecipients": [
                    {"emailAddress": {"address": r}} for r in recipients
                ],
            },
            "saveToSentItems": "false",
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://graph.microsoft.com/v1.0/me/sendMail",
                json=message,
                headers={"Authorization": f"Bearer {token}"},
                timeout=30.0,
            )
            resp.raise_for_status()

    # ------------------------------------------------------------------
    # Teams — Incoming Webhook connector
    # ------------------------------------------------------------------

    async def _send_teams(
        self,
        channel: AlertChannel,
        payload: dict[str, Any],
    ) -> None:
        """Send alert to a Microsoft Teams channel via incoming webhook."""
        webhook_url = channel.config.get("webhook_url")
        if not webhook_url:
            raise ValueError("Teams webhook URL not configured")

        card: dict[str, Any] = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": self._severity_color(payload.get("severity", "medium")),
            "summary": payload.get("title", "Security Alert"),
            "sections": [
                {
                    "activityTitle": payload.get("title", "Security Alert"),
                    "activitySubtitle": (
                        f"Entra Permissions Analyzer -- "
                        f"{datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}"
                    ),
                    "facts": [
                        {"name": "Severity", "value": payload.get("severity", "unknown")},
                        {"name": "Type", "value": payload.get("alert_type", "unknown")},
                        {"name": "Details", "value": payload.get("description", "")},
                    ],
                    "markdown": True,
                }
            ],
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                str(webhook_url),
                json=card,
                timeout=30.0,
            )
            resp.raise_for_status()

    # ------------------------------------------------------------------
    # Generic Webhook — POST with HMAC-SHA256 signature
    # ------------------------------------------------------------------

    async def _send_webhook(
        self,
        channel: AlertChannel,
        payload: dict[str, Any],
    ) -> None:
        """POST alert payload to a generic endpoint with HMAC-SHA256 signature."""
        webhook_url = channel.config.get("webhook_url")
        if not webhook_url:
            raise ValueError("Webhook URL not configured")

        body = json.dumps(payload, default=str, sort_keys=True)
        secret = channel.config.get("secret", "")
        if isinstance(secret, list):
            secret = secret[0] if secret else ""
        signature = hmac.new(
            str(secret).encode(),
            body.encode(),
            hashlib.sha256,
        ).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-Signature-256": f"sha256={signature}",
            "X-Timestamp": datetime.now(UTC).isoformat(),
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                str(webhook_url),
                content=body,
                headers=headers,
                timeout=30.0,
            )
            resp.raise_for_status()

    # ------------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_email_body(payload: dict[str, Any]) -> str:
        """Build an HTML email body from the alert payload."""
        title = payload.get("title", "Security Alert")
        severity = payload.get("severity", "unknown")
        description = payload.get("description", "")
        details: list[dict[str, str]] = payload.get("details", [])

        details_html = ""
        if details:
            rows = "".join(
                f"<tr>"
                f"<td style='padding:4px 8px;border:1px solid #ddd;'>{d.get('label', '')}</td>"
                f"<td style='padding:4px 8px;border:1px solid #ddd;'>{d.get('value', '')}</td>"
                f"</tr>"
                for d in details
            )
            details_html = (
                f"<table style='border-collapse:collapse;margin-top:12px;'>{rows}</table>"
            )

        return (
            "<div style=\"font-family:Segoe UI,sans-serif;max-width:600px;\">"
            f"<h2 style=\"color:#0078d4;\">{title}</h2>"
            f"<p><strong>Severity:</strong> {severity.upper()}</p>"
            f"<p>{description}</p>"
            f"{details_html}"
            "<hr style=\"margin-top:20px;border:none;border-top:1px solid #eee;\" />"
            "<p style=\"color:#888;font-size:12px;\">"
            "Generated by Entra Permissions Analyzer"
            "</p>"
            "</div>"
        )

    @staticmethod
    def _severity_color(severity: str) -> str:
        """Map severity level to a hex colour for the Teams MessageCard theme."""
        return {
            "critical": "FF0000",
            "high": "FF6600",
            "medium": "FFB800",
            "low": "00AA00",
        }.get(severity.lower(), "0078D4")
