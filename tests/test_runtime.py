"""End-to-end automated verification test suite for CentrAlign runtime."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Generator

import pytest
import uvicorn

from core.memory import CompanyMemoryStore
from core.models import RunPhase
from core.runtime import CentrAlignRuntime
from core.seed import reset_and_seed_workspace
from portal_app.app import app


@pytest.fixture(scope="module")
def portal_server() -> Generator[str, None, None]:
    """Starts the portal server on port 8001 for test execution."""
    config = uvicorn.Config(
        app, host="127.0.0.1", port=8001, log_level="error", access_log=False
    )
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    time.sleep(1.5)

    yield "http://127.0.0.1:8001"

    server.should_exit = True


def test_end_to_end_runtime_lifecycle(portal_server: str) -> None:
    """Tests the full two-run vendor onboarding and payout workflow."""
    base_dir = Path(".").resolve()
    reset_and_seed_workspace(base_dir)

    memory_path = base_dir / "workspace" / "company_memory.json"
    memory_store = CompanyMemoryStore(memory_path)

    # -------------------------------------------------------------
    # RUN 1: inv_01_apex.json (₹84,500, hyphenated GSTIN)
    # -------------------------------------------------------------
    hitl_invoked = False

    def hitl_callback_run1(step, params, reason) -> bool:
        nonlocal hitl_invoked
        hitl_invoked = True
        return True

    runtime1 = CentrAlignRuntime(
        memory_store=memory_store,
        approval_callback=hitl_callback_run1,
    )

    goal = (
        "Process the pending vendor invoice in the dropbox folder, "
        "onboard the vendor into the finance portal if they aren't registered yet, "
        "and schedule their payout."
    )

    run1_state = runtime1.run(
        goal=goal,
        run_id="test_run_1_apex",
        target_invoice_file="inv_01_apex.json",
    )

    # Assert Run 1 succeeded completely
    assert run1_state.current_phase == RunPhase.COMPLETED, f"Run 1 ended in {run1_state.current_phase}"

    # Assert Step 3 took 2 attempts (Attempt 1 failed with hyphenated GSTIN, Attempt 2 succeeded)
    step3 = next(s for s in run1_state.plan if s.step_id == "step_3_register_vendor")
    assert step3.attempts == 2, f"Expected 2 attempts for step 3, got {step3.attempts}"
    assert len(step3.error_history) == 1
    assert "ERP-422" in step3.error_history[0] or "Field 'tax_id'" in step3.error_history[0]

    # Assert HITL was triggered and checkpoint saved
    assert hitl_invoked, "HITL policy gate should have been triggered for ₹84,500"
    checkpoint_file = Path(run1_state.evidence_dir) / "checkpoint_hitl.json"
    assert checkpoint_file.exists(), "checkpoint_hitl.json should exist"

    # Assert 1 episodic lesson was learned and saved in company_memory.json
    memory_store.reload()
    lessons = memory_store.episodic_lessons
    assert len(lessons) >= 1, "Should have learned at least 1 episodic lesson"
    assert any(
        l.transformation_rule == "strip_hyphens_and_spaces_uppercase"
        for l in lessons
    )

    # Assert all 5 verification checks passed
    assert len(run1_state.verification_checks) == 5
    for check in run1_state.verification_checks:
        assert check.passed, f"Check failed: {check.check_name} ({check.actual})"

    # Assert PNG screenshots exist
    ev_dir = Path(run1_state.evidence_dir)
    pngs = list(ev_dir.glob("*.png"))
    assert len(pngs) >= 3, f"Expected at least 3 screenshots, found {len(pngs)}: {pngs}"
    assert (ev_dir / "final_dashboard_verified.png").exists()

    # -------------------------------------------------------------
    # RUN 2: inv_02_nova.json (₹32,000, hyphenated GSTIN)
    # -------------------------------------------------------------
    hitl_invoked_run2 = False

    def hitl_callback_run2(step, params, reason) -> bool:
        nonlocal hitl_invoked_run2
        hitl_invoked_run2 = True
        return True

    runtime2 = CentrAlignRuntime(
        memory_store=memory_store,
        approval_callback=hitl_callback_run2,
    )

    run2_state = runtime2.run(
        goal=goal,
        run_id="test_run_2_nova",
        target_invoice_file="inv_02_nova.json",
    )

    # Assert Run 2 completed
    assert run2_state.current_phase == RunPhase.COMPLETED, f"Run 2 ended in {run2_state.current_phase}"

    # Assert Step 3 took ONLY 1 attempt because episodic memory pre-sanitized the GSTIN
    step3_r2 = next(s for s in run2_state.plan if s.step_id == "step_3_register_vendor")
    assert step3_r2.attempts == 1, (
        f"Expected exactly 1 attempt for Run 2 step 3 due to pre-sanitization, got {step3_r2.attempts}"
    )
    assert len(step3_r2.error_history) == 0

    # Assert episodic memory log was generated
    assert any("MEMORY_APPLIED" in e.event_type for e in run2_state.audit_log)

    # Assert HITL was NOT triggered (₹32,000 <= ₹50,000)
    assert not hitl_invoked_run2, "HITL should NOT be triggered for ₹32,000"

    # Assert all 5 verification checks passed in Run 2
    assert len(run2_state.verification_checks) == 5
    for check in run2_state.verification_checks:
        assert check.passed, f"Run 2 Check failed: {check.check_name} ({check.actual})"

    # Assert Run 2 screenshots exist
    ev_dir2 = Path(run2_state.evidence_dir)
    assert (ev_dir2 / "final_dashboard_verified.png").exists()
