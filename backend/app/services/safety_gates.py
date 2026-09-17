from __future__ import annotations

from datetime import UTC, datetime

from app.models.governance import SafetyGateDecision, SafetyMetrics


class SafetyGateEvaluator:
    """Non-bypassable production autonomy gates."""

    def evaluate(self, metrics: SafetyMetrics) -> SafetyGateDecision:
        reasons: list[str] = []
        if metrics.sample_size < 100:
            reasons.append("insufficient_sample_size")
        if metrics.lockout_count != 0:
            reasons.append("lockouts_detected")
        if metrics.restore_success_rate < 1.0:
            reasons.append("restore_drill_below_100_percent")
        if metrics.recommendation_precision < 0.95:
            reasons.append("recommendation_precision_below_95_percent")
        if metrics.audit_chain_success_rate < 1.0:
            reasons.append("audit_integrity_below_100_percent")
        if metrics.canary_success_rate < 0.99:
            reasons.append("canary_success_below_99_percent")
        return SafetyGateDecision(
            autonomous_remediation_enabled=not reasons,
            reasons=reasons,
            evaluated_at=datetime.now(UTC),
        )
