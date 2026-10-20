"""CentrAlign Autonomous AI Employee Runtime State Machine."""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from connectors.base import ToolRegistry, ToolResult
from connectors.browser_connector import BrowserConnector
from connectors.erp_api_connector import ERPConnector
from connectors.file_connector import FileConnector
from core.llm import ReasoningEngine
from core.memory import CompanyMemoryStore
from core.models import (
    AuditEvent,
    EpisodicLesson,
    PlanStep,
    RiskLevel,
    RunPhase,
    TaskRunState,
    VerificationCheck,
)
from core.policy import PolicyEngine
from core.verifier import OutcomeVerifier


class CentrAlignRuntime:
    """Executes business goals through the explicit state machine:
    GOAL -> UNDERSTAND -> PLAN -> EXECUTE -> OBSERVE -> ADAPT -> VERIFY -> COMPLETE.
    """

    def __init__(
        self,
        memory_store: CompanyMemoryStore,
        reasoning_engine: Optional[ReasoningEngine] = None,
        tool_registry: Optional[ToolRegistry] = None,
        policy_engine: Optional[PolicyEngine] = None,
        outcome_verifier: Optional[OutcomeVerifier] = None,
        approval_callback: Optional[Callable[[PlanStep, Dict[str, Any], str], bool]] = None,
        on_phase_change: Optional[Callable[[RunPhase, TaskRunState], None]] = None,
        on_step_event: Optional[Callable[[str, PlanStep, Dict[str, Any]], None]] = None,
    ) -> None:
        self.memory_store = memory_store
        self.reasoning = reasoning_engine or ReasoningEngine()
        self.policy = policy_engine or PolicyEngine()
        self.browser_connector = BrowserConnector()
        self.verifier = outcome_verifier or OutcomeVerifier(self.browser_connector)
        self.approval_callback = approval_callback or (lambda step, params, reason: True)
        self.on_phase_change = on_phase_change
        self.on_step_event = on_step_event

        # Initialize Tool Registry with standard tools
        self.registry = tool_registry or self._build_default_registry()

    def _build_default_registry(self) -> ToolRegistry:
        reg = ToolRegistry()
        reg.register("fs.read_next_invoice", FileConnector.read_next_invoice)
        reg.register("fs.archive_invoice", FileConnector.archive_invoice)
        reg.register("erp.lookup_vendor", ERPConnector.lookup_vendor)
        reg.register("erp.fetch_system_state", ERPConnector.fetch_system_state)
        reg.register("browser.register_vendor_ui", self.browser_connector.register_vendor_ui)
        reg.register("browser.schedule_payout_ui", self.browser_connector.schedule_payout_ui)
        reg.register(
            "browser.capture_dashboard_receipt",
            self.browser_connector.capture_dashboard_receipt,
        )
        return reg

    def _log_event(
        self,
        state: TaskRunState,
        event_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        event = AuditEvent(
            phase=state.current_phase.value,
            event_type=event_type,
            message=message,
            details=details,
        )
        state.audit_log.append(event)
        if self.on_step_event:
            # Notify observer
            pass

    def _set_phase(self, state: TaskRunState, phase: RunPhase) -> None:
        state.current_phase = phase
        self._log_event(state, "PHASE_TRANSITION", f"Transitioned to phase {phase.value}")
        if self.on_phase_change:
            self.on_phase_change(phase, state)

    def _resolve_param_value(
        self, val: Any, state: TaskRunState
    ) -> Any:
        if not isinstance(val, str):
            return val

        if val == "$evidence_dir":
            return state.evidence_dir

        if val.startswith("$working_memory."):
            path = val[len("$working_memory."):].split(".")
            curr = state.working_memory
            for p in path:
                if isinstance(curr, dict):
                    curr = curr.get(p)
                else:
                    return None
            return curr

        if val.startswith("$resolved_context."):
            path = val[len("$resolved_context."):].split(".")
            curr = state.resolved_context
            for p in path:
                if isinstance(curr, dict):
                    curr = curr.get(p)
                else:
                    return None
            return curr

        return val

    def _resolve_params(
        self, params: Dict[str, Any], state: TaskRunState
    ) -> Dict[str, Any]:
        resolved: Dict[str, Any] = {}
        for k, v in params.items():
            if isinstance(v, dict):
                resolved[k] = self._resolve_params(v, state)
            else:
                resolved[k] = self._resolve_param_value(v, state)
        return resolved

    def run(
        self,
        goal: str,
        run_id: Optional[str] = None,
        target_invoice_file: Optional[str] = None,
    ) -> TaskRunState:
        """Executes a full run from GOAL to COMPLETION/FAILURE."""
        rid = run_id or f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:4]}"
        evidence_dir = str(Path(f"./workspace/evidence/{rid}").resolve())
        Path(evidence_dir).mkdir(parents=True, exist_ok=True)

        state = TaskRunState(
            run_id=rid,
            goal=goal,
            current_phase=RunPhase.GOAL,
            evidence_dir=evidence_dir,
        )
        self._log_event(state, "INITIALIZED", f"Starting run '{rid}' with goal: {goal}")

        # --- 1. UNDERSTAND ---
        self._set_phase(state, RunPhase.UNDERSTAND)
        self.memory_store.reload()
        context = self.memory_store.resolve_context(goal)
        state.resolved_context = context
        self._log_event(
            state,
            "CONTEXT_RESOLVED",
            f"Resolved aliases: {list(context.get('resolved_aliases', {}).keys())}, "
            f"Loaded SOP: {context.get('sop', {}).get('sop_id') if context.get('sop') else 'None'}, "
            f"Prior episodic lessons: {context.get('episodic_lessons_count', 0)}",
            details=context,
        )

        # --- 2. PLAN ---
        self._set_phase(state, RunPhase.PLAN)
        plan_steps = self.reasoning.generate_plan(
            goal=goal,
            context=context,
            target_invoice_file=target_invoice_file,
        )
        state.plan = plan_steps
        self._log_event(
            state,
            "PLAN_GENERATED",
            f"Generated {len(plan_steps)} steps with bounded risk levels",
            details={"steps": [s.step_id for s in plan_steps]},
        )

        # --- 3. EXECUTE LOOP ---
        self._set_phase(state, RunPhase.EXECUTE)
        portal_url = (
            context.get("system_endpoints", {}).get("finance_portal_url")
            or "http://127.0.0.1:8001"
        )

        max_step_retries = 3

        for step in state.plan:
            if step.status in ("COMPLETED", "SKIPPED"):
                continue

            step_success = False

            while step.attempts < max_step_retries and not step_success:
                step.status = "IN_PROGRESS"
                step.attempts += 1

                # 3a. Resolve parameters from working memory & context
                resolved_params = self._resolve_params(step.params, state)
                resolved_params["step_id"] = step.step_id
                resolved_params["attempt"] = step.attempts

                # 3b. Pre-Execution Sanitization via Episodic Lessons
                sanitized_params, memory_logs = self.memory_store.apply_episodic_lessons(
                    step.tool_name, resolved_params
                )
                for log_msg in memory_logs:
                    self._log_event(state, "MEMORY_APPLIED", log_msg)
                    if self.on_step_event:
                        self.on_step_event("MEMORY_APPLIED", step, {"log": log_msg})
                resolved_params = sanitized_params

                # 3c. Policy & Risk Gate (HITL)
                requires_hitl, reason = self.policy.requires_approval(
                    step, resolved_params, self.memory_store.policies
                )
                if requires_hitl:
                    self._set_phase(state, RunPhase.WAITING_FOR_APPROVAL)
                    checkpoint_path = self.policy.save_checkpoint(state, state.evidence_dir)
                    self._log_event(
                        state,
                        "POLICY_GATE_TRIGGERED",
                        f"Step '{step.step_id}' paused for HITL approval: {reason}",
                        details={"checkpoint": checkpoint_path},
                    )
                    if self.on_step_event:
                        self.on_step_event(
                            "HITL_TRIGGERED",
                            step,
                            {"reason": reason, "checkpoint": checkpoint_path},
                        )

                    approved = self.approval_callback(step, resolved_params, reason)
                    if not approved:
                        step.status = "ABORTED"
                        self._log_event(state, "HITL_REJECTED", "Operator rejected action.")
                        self._set_phase(state, RunPhase.FAILED)
                        self._save_report(state)
                        return state

                    self._log_event(state, "HITL_APPROVED", "Operator granted authorization.")
                    self._set_phase(state, RunPhase.EXECUTE)

                # 3d. Tool Invocation
                self._log_event(
                    state,
                    "TOOL_INVOCATION",
                    f"Executing {step.tool_name} (attempt {step.attempts})",
                    details=resolved_params,
                )
                if self.on_step_event:
                    self.on_step_event("TOOL_INVOKING", step, resolved_params)

                result: ToolResult = self.registry.execute(step.tool_name, **resolved_params)

                if result.screenshot_path and result.screenshot_path not in step.screenshot_paths:
                    step.screenshot_paths.append(result.screenshot_path)

                # 3e. Success Handling
                if result.success:
                    step.status = "COMPLETED"
                    step.output = result.data
                    step_success = True
                    self._log_event(
                        state,
                        "TOOL_SUCCESS",
                        f"Step '{step.step_id}' completed successfully.",
                        details=result.data,
                    )

                    # Update working memory
                    if "invoice" in result.data:
                        state.working_memory["invoice"] = result.data["invoice"]
                    if "vendor_id" in result.data:
                        state.working_memory["vendor_id"] = result.data["vendor_id"]
                    if "payout_id" in result.data:
                        state.working_memory["payout_id"] = result.data["payout_id"]

                    # Check if lookup found an existing vendor
                    if step.step_id == "step_2_lookup_vendor" and result.data.get("found"):
                        found_vendor_id = result.data.get("vendor_id")
                        state.working_memory["vendor_id"] = found_vendor_id
                        # Skip registration step
                        for subsequent_step in state.plan:
                            if subsequent_step.step_id == "step_3_register_vendor":
                                subsequent_step.status = "SKIPPED"
                                self._log_event(
                                    state,
                                    "STEP_SKIPPED",
                                    f"Vendor already registered ({found_vendor_id}); skipped step_3.",
                                )

                    if self.on_step_event:
                        self.on_step_event("TOOL_SUCCEEDED", step, result.data)

                # 3f. Failure & Adaptation Handling
                else:
                    self._set_phase(state, RunPhase.OBSERVE)
                    error_msg = result.error or "Unknown error"
                    step.error_history.append(error_msg)
                    self._log_event(
                        state,
                        "TOOL_FAILURE",
                        f"Step '{step.step_id}' failed: {error_msg}",
                        details={
                            "error_code": result.error_code,
                            "screenshot": result.screenshot_path,
                        },
                    )
                    if self.on_step_event:
                        self.on_step_event(
                            "TOOL_FAILED",
                            step,
                            {"error": error_msg, "screenshot": result.screenshot_path},
                        )

                    if step.attempts < max_step_retries:
                        self._set_phase(state, RunPhase.ADAPT)
                        decision = self.reasoning.diagnose_and_adapt(
                            step=step,
                            resolved_params=resolved_params,
                            error_text=error_msg,
                        )

                        if decision.recoverable:
                            # 1. Record new lesson in episodic memory
                            lesson_id = f"LSN-{uuid4().hex[:4].upper()}"
                            lesson = EpisodicLesson(
                                lesson_id=lesson_id,
                                tool_name=step.tool_name,
                                error_signature=result.error_code or "ERROR",
                                parameter_name=decision.parameter_name,
                                transformation_rule=decision.transformation_rule,
                                explanation=decision.lesson_explanation,
                            )
                            self.memory_store.record_lesson(lesson)
                            self._log_event(
                                state,
                                "LESSON_LEARNED",
                                f"Recorded Episodic Lesson {lesson_id}: {decision.transformation_rule}",
                                details=lesson.model_dump(),
                            )

                            # 2. Mutate working memory and step params
                            if decision.parameter_name in step.params:
                                step.params[decision.parameter_name] = decision.repaired_value
                            # If invoice field in working memory, update it
                            if "invoice" in state.working_memory and decision.parameter_name in state.working_memory["invoice"]:
                                state.working_memory["invoice"][decision.parameter_name] = decision.repaired_value

                            self._log_event(
                                state,
                                "PARAMETER_ADAPTED",
                                f"Adapted '{decision.parameter_name}' to '{decision.repaired_value}'",
                            )
                            if self.on_step_event:
                                self.on_step_event("ADAPTED", step, decision.model_dump())

                            # Return to EXECUTE phase for retry
                            self._set_phase(state, RunPhase.EXECUTE)
                        else:
                            step.status = "FAILED"
                            self._log_event(
                                state,
                                "UNRECOVERABLE_ERROR",
                                f"Diagnosis concluded failure is unrecoverable: {decision.root_cause}",
                            )
                            break
                    else:
                        step.status = "FAILED"
                        self._log_event(
                            state,
                            "RETRIES_EXHAUSTED",
                            f"Step '{step.step_id}' exceeded max attempts ({max_step_retries}).",
                        )
                        break

            if not step_success and step.status != "SKIPPED":
                self._set_phase(state, RunPhase.FAILED)
                self._save_report(state)
                return state

        # --- 4. VERIFY ---
        self._set_phase(state, RunPhase.VERIFY)
        checks = self.verifier.verify(
            portal_url=portal_url,
            working_memory=state.working_memory,
            evidence_dir=state.evidence_dir,
        )
        state.verification_checks = checks

        all_passed = all(c.passed for c in checks)
        for check in checks:
            self._log_event(
                state,
                "VERIFICATION_CHECK",
                f"Check '{check.check_name}': {'PASSED' if check.passed else 'FAILED'}",
                details=check.model_dump(),
            )

        if all_passed:
            self._set_phase(state, RunPhase.COMPLETED)
            self._log_event(
                state,
                "TASK_COMPLETED",
                "All 5 independent verification checks passed. Task complete.",
            )
        else:
            self._set_phase(state, RunPhase.FAILED)
            self._log_event(
                state,
                "VERIFICATION_FAILED",
                "One or more independent verification checks failed.",
            )

        self._save_report(state)
        return state

    def _save_report(self, state: TaskRunState) -> None:
        report_file = Path(state.evidence_dir) / "report.json"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(state.model_dump_json(indent=2))
