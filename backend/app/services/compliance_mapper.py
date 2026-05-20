"""E1/E2: Maps best-practice violations to compliance framework controls."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.models.best_practice import BestPracticeViolation

logger = logging.getLogger(__name__)

_FRAMEWORKS_DIR = Path(__file__).resolve().parents[3] / "shared" / "compliance_frameworks"


class ControlResult:
    __slots__ = ("control_id", "title", "section", "passed", "violation_ids")

    def __init__(self, control_id: str, title: str, section: str) -> None:
        self.control_id = control_id
        self.title = title
        self.section = section
        self.passed = True
        self.violation_ids: list[str] = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "control_id": self.control_id,
            "title": self.title,
            "section": self.section,
            "passed": self.passed,
            "violation_count": len(self.violation_ids),
            "violation_ids": self.violation_ids,
        }


class ComplianceMapper:
    """Loads compliance framework JSON mappings and scores violations against them."""

    def __init__(self) -> None:
        self._frameworks: dict[str, dict[str, Any]] = {}
        self._load_all()

    def _load_all(self) -> None:
        if not _FRAMEWORKS_DIR.is_dir():
            logger.warning("Compliance frameworks directory not found: %s", _FRAMEWORKS_DIR)
            return

        for path in _FRAMEWORKS_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                key = path.stem
                self._frameworks[key] = data
                logger.info("Loaded compliance framework '%s' (%s)", data.get("framework", key), key)
            except (json.JSONDecodeError, OSError):
                logger.exception("Failed to load compliance framework from %s", path)

    @property
    def available_frameworks(self) -> list[dict[str, str]]:
        return [
            {"key": key, "name": data.get("framework", key), "version": data.get("version", "")}
            for key, data in self._frameworks.items()
        ]

    def evaluate(
        self,
        framework_key: str,
        violations: list[BestPracticeViolation],
    ) -> dict[str, Any]:
        fw = self._frameworks.get(framework_key)
        if fw is None:
            return {"error": f"Unknown framework: {framework_key}"}

        violation_types_present: dict[str, list[str]] = defaultdict(list)
        for v in violations:
            violation_types_present[v.violation_type.value].append(v.id)

        controls: dict[str, ControlResult] = {}
        for control_id, control_def in fw.get("controls", {}).items():
            section = control_def.get("section") or control_def.get("family") or control_def.get("category", "")
            cr = ControlResult(control_id, control_def["title"], section)
            mapped_types = control_def.get("violation_types", [])

            for vt in mapped_types:
                if vt in violation_types_present:
                    cr.passed = False
                    cr.violation_ids.extend(violation_types_present[vt])

            controls[control_id] = cr

        total = len(controls)
        passed = sum(1 for c in controls.values() if c.passed)

        return {
            "framework": fw.get("framework", framework_key),
            "version": fw.get("version", ""),
            "total_controls": total,
            "controls_passed": passed,
            "controls_failed": total - passed,
            "score_pct": round((passed / total) * 100, 1) if total else 0.0,
            "controls": [c.to_dict() for c in controls.values()],
        }

    def evaluate_all(
        self,
        violations: list[BestPracticeViolation],
    ) -> list[dict[str, Any]]:
        return [self.evaluate(key, violations) for key in self._frameworks]
