"""Policy & Blast-Radius Engine for CentrAlign runtime."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from core.models import PlanStep, RiskLevel, TaskRunState


class PolicyEngine:
    """Evaluates risk tiers, enforces organizational limits, and manages HITL pauses."""

    @staticmethod
    def requires_approval(
        step: PlanStep, resolved_params: Dict[str, Any], policies: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Determines if a step requires Human-in-the-Loop approval before execution.

        Returns:
            Tuple of (requires_approval: bool, reason: str).
        """
        if step.risk_level == RiskLevel.HIGH_FINANCIAL:
            max_limit = float(policies.get("max_autonomous_payout_inr", 50000.0))
            amount_inr = float(resolved_params.get("amount_inr", 0.0))

            if policies.get("require_human_approval_above_limit", True) and amount_inr > max_limit:
                reason = (
                    f"Payout amount ₹{amount_inr:,.2f} exceeds autonomous authorization "
                    f"limit of ₹{max_limit:,.2f} (SOP-FIN-04 policy requirement)."
                )
                return True, reason

        return False, ""

    @staticmethod
    def save_checkpoint(state: TaskRunState, evidence_dir: str) -> str:
        """Serializes current TaskRunState to checkpoint_hitl.json."""
        ev_path = Path(evidence_dir)
        ev_path.mkdir(parents=True, exist_ok=True)
        checkpoint_file = ev_path / "checkpoint_hitl.json"
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            f.write(state.model_dump_json(indent=2))
        return str(checkpoint_file.resolve())
