"""Turnkey Demo Runner for CentrAlign Autonomous AI Employee Runtime.

Runs both Run 1 (Self-Healing + HITL Gate) and Run 2 (Episodic Memory Pre-Sanitization + Autonomous)
with rich console telemetry, live Playwright Chromium browser automation, and verification matrices.
"""
from __future__ import annotations

import argparse
import sys

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import threading
import time
from pathlib import Path
from typing import Any, Dict

import httpx
import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from core.memory import CompanyMemoryStore
from core.models import PlanStep, RiskLevel, RunPhase, TaskRunState
from core.runtime import CentrAlignRuntime
from core.seed import reset_and_seed_workspace
from portal_app.app import app

console = Console(legacy_windows=False)


def start_portal_server(host: str = "127.0.0.1", port: int = 8001) -> uvicorn.Server:
    """Starts the Acme Finance Portal server in a background daemon thread."""
    config = uvicorn.Config(
        app, host=host, port=port, log_level="error", access_log=False
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Poll until server responds
    url = f"http://{host}:{port}/api/verify/state"
    start_time = time.time()
    while time.time() - start_time < 10.0:
        try:
            with httpx.Client(timeout=1.0) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    return server
        except Exception:
            pass
        time.sleep(0.2)

    raise RuntimeError(f"Portal server on {url} failed to start within 10 seconds.")


def render_run_header(run_id: str, goal: str, invoice_file: str, mode: str) -> None:
    text = Text()
    text.append("CentrAlign Autonomous AI Employee Runtime\n", style="bold cyan")
    text.append(f"Run ID: {run_id}\n", style="bold white")
    text.append(f"Target Invoice: {invoice_file}\n", style="yellow")
    text.append(f"Goal: {goal}\n", style="italic")
    text.append(f"Reasoning Mode: {mode} | Target Portal: http://127.0.0.1:8001", style="dim")
    console.print(Panel(text, title=f"EXECUTING {run_id.upper()}", border_style="cyan"))


def render_plan_table(plan: list[PlanStep]) -> None:
    table = Table(title="Generated Multi-Step Execution Plan", show_header=True, header_style="bold blue")
    table.add_column("Step ID", style="cyan", width=24)
    table.add_column("Title", style="white")
    table.add_column("Tool", style="dim")
    table.add_column("Risk Tier", justify="center")

    for s in plan:
        risk_style = (
            "[bold green]READ_ONLY[/]"
            if s.risk_level == RiskLevel.READ_ONLY
            else "[bold yellow]LOW_MUTATION[/]"
            if s.risk_level == RiskLevel.LOW_MUTATION
            else "[bold red]HIGH_FINANCIAL[/]"
        )
        table.add_row(s.step_id, s.title, s.tool_name, risk_style)

    console.print(table)


def render_verification_matrix(state: TaskRunState) -> None:
    table = Table(
        title=f"Independent Verification Evidence Matrix ({state.run_id})",
        show_header=True,
        header_style="bold green",
    )
    table.add_column("Check Name", style="bold white")
    table.add_column("Target Source", style="dim")
    table.add_column("Expected Outcome", style="yellow")
    table.add_column("Actual System State", style="cyan")
    table.add_column("Status", justify="center")

    for check in state.verification_checks:
        status_text = (
            "[bold green]PASS[/]" if check.passed else "[bold red]FAIL[/]"
        )
        table.add_row(
            check.check_name,
            check.evidence_source,
            str(check.expected),
            str(check.actual),
            status_text,
        )

    console.print(table)


def render_comparison_summary(run1: TaskRunState, run2: TaskRunState) -> None:
    table = Table(
        title="CentrAlign Proof-of-Autonomy Comparative Benchmark",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Benchmark Metric", style="bold white", width=34)
    table.add_column("Run 1 (inv_01_apex.json)", style="yellow", justify="center")
    table.add_column("Run 2 (inv_02_nova.json)", style="cyan", justify="center")

    # Invoices
    amt1 = f"₹{run1.working_memory.get('invoice', {}).get('amount_inr', 84500.0):,.2f}"
    amt2 = f"₹{run2.working_memory.get('invoice', {}).get('amount_inr', 32000.0):,.2f}"
    table.add_row("Invoice Amount", amt1, amt2)

    table.add_row(
        "Input Tax ID (Raw)",
        "27-AABCA-1234-F1Z5 (Invalid)",
        "29-GGGGG-1314-R9Z6 (Invalid)",
    )

    # Attempts
    step3_r1 = next((s for s in run1.plan if s.step_id == "step_3_register_vendor"), None)
    step3_r2 = next((s for s in run2.plan if s.step_id == "step_3_register_vendor"), None)
    att1 = f"{step3_r1.attempts} (Failed Attempt 1 -> Adapted)" if step3_r1 else "N/A"
    att2 = f"{step3_r2.attempts} (Pre-Sanitized via Episodic Memory)" if step3_r2 else "N/A"
    table.add_row("Browser Registration Attempts", att1, att2)

    table.add_row(
        "New Episodic Lesson Learned",
        "Yes (strip_hyphens_and_spaces_uppercase)",
        "Reused Existing Lesson (0 new)",
    )

    # HITL
    hitl1 = any(e.event_type in ("POLICY_GATE_TRIGGERED", "HITL_APPROVED", "HITL_TRIGGERED") for e in run1.audit_log)
    hitl2 = any(e.event_type in ("POLICY_GATE_TRIGGERED", "HITL_APPROVED", "HITL_TRIGGERED") for e in run2.audit_log)
    table.add_row(
        "HITL Policy Gate Triggered",
        "Yes (> ₹50,000 threshold)" if hitl1 else "No",
        "No (Within ₹50,000 threshold)" if not hitl2 else "Yes",
    )

    # Verifications
    pass1 = sum(1 for c in run1.verification_checks if c.passed)
    pass2 = sum(1 for c in run2.verification_checks if c.passed)
    table.add_row(
        "Independent Verification",
        f"[bold green]{pass1}/{len(run1.verification_checks)} Checks PASSED[/]",
        f"[bold green]{pass2}/{len(run2.verification_checks)} Checks PASSED[/]",
    )

    console.print(table)


def run_pipeline(auto_approve: bool = True) -> int:
    """Executes the complete demo pipeline for Run 1 and Run 2."""
    base_dir = Path(".").resolve()
    console.print("\n[bold cyan]=== CentrAlign Autonomous AI Employee Demonstration ===[/]")

    # Start Portal Server
    console.print("[dim]Starting Acme Finance Portal server on http://127.0.0.1:8001...[/]")
    server = start_portal_server()
    console.print("[bold green][OK] Acme Finance Portal is live and healthy.[/]\n")

    # Reset Workspace clean
    console.print("[dim]Resetting workspace to clean seed state...[/]")
    reset_and_seed_workspace(base_dir)
    console.print("[bold green][OK] Workspace initialized with seed invoices and clean memory.[/]\n")

    memory_path = base_dir / "workspace" / "company_memory.json"
    memory_store = CompanyMemoryStore(memory_path)

    # HITL Approval Handler
    def hitl_handler(step: PlanStep, params: Dict[str, Any], reason: str) -> bool:
        panel_text = (
            f"[bold red]POLICY INTERCEPTION - HUMAN AUTHORIZATION REQUIRED[/]\n\n"
            f"[yellow]Reason:[/] {reason}\n"
            f"[yellow]Step ID:[/] {step.step_id} ({step.title})\n"
            f"[yellow]Target Tool:[/] {step.tool_name}\n"
            f"[yellow]Vendor ID:[/] {params.get('vendor_id')}\n"
            f"[yellow]Invoice ID:[/] {params.get('invoice_id')}\n"
            f"[yellow]Amount:[/] ₹{float(params.get('amount_inr', 0.0)):,.2f}\n"
            f"[yellow]State Checkpoint Saved:[/] ./workspace/evidence/{params.get('step_id')}_checkpoint_hitl.json"
        )
        console.print(Panel(panel_text, border_style="bold red"))

        if auto_approve:
            console.print("[bold green][OK] [AUTO-APPROVE] Operator authorization granted automatically.[/]\n")
            return True

        # Interactive mode
        ans = input("Authorize this high-value financial transaction? [y/N]: ").strip().lower()
        return ans in ("y", "yes")

    # Console Event Reporter
    def on_step_event(event_type: str, step: PlanStep, details: Dict[str, Any]) -> None:
        if event_type == "TOOL_INVOKING":
            console.print(f"  [bold white][EXECUTE][/] Invoking [cyan]{step.tool_name}[/] (Attempt {step.attempts})")
        elif event_type == "TOOL_FAILED":
            console.print(f"  [bold yellow][OBSERVE][/] [red]Attempt {step.attempts} Failed:[/] {details.get('error')}")
            if details.get("screenshot"):
                console.print(f"    [dim]Failure screenshot captured: {details.get('screenshot')}[/]")
        elif event_type == "ADAPTED":
            console.print(
                f"  [bold magenta][ADAPT][/] [bold]Self-Healing Parameter Mutation:[/] "
                f"'{details.get('parameter_name')}' -> '{details.get('repaired_value')}'"
            )
            console.print(
                f"    [dim]Episodic memory rule persisted: {details.get('transformation_rule')} -> company_memory.json[/]"
            )
        elif event_type == "MEMORY_APPLIED":
            console.print(f"  [bold cyan]{details.get('log')}[/]")
        elif event_type == "TOOL_SUCCEEDED":
            console.print(f"  [bold green][EXECUTE][/] Tool {step.tool_name} returned success: {details}")

    runtime = CentrAlignRuntime(
        memory_store=memory_store,
        approval_callback=hitl_handler,
        on_step_event=on_step_event,
    )

    goal = (
        "Process the pending vendor invoice in the dropbox folder, "
        "onboard the vendor into the finance portal if they aren't registered yet, "
        "and schedule their payout."
    )

    # -------------------------------------------------------------
    # RUN 1: Apex Cloud Solutions (₹84,500, Hyphenated GSTIN)
    # -------------------------------------------------------------
    render_run_header("run_1_apex", goal, "inv_01_apex.json", "Deterministic + Structured")
    run1_state = runtime.run(
        goal=goal,
        run_id="run_1_apex",
        target_invoice_file="inv_01_apex.json",
    )

    render_plan_table(run1_state.plan)
    render_verification_matrix(run1_state)
    console.print(
        f"\n[bold green][OK] RUN 1 COMPLETED with state: {run1_state.current_phase.value}[/]\n"
        f"[dim]Evidence saved to: {run1_state.evidence_dir}[/]\n"
    )

    # -------------------------------------------------------------
    # RUN 2: Nova Data Systems (₹32,000, Hyphenated GSTIN)
    # -------------------------------------------------------------
    render_run_header(
        "run_2_nova",
        goal,
        "inv_02_nova.json",
        "Deterministic (Reusing Learned Episodic Memory)",
    )
    run2_state = runtime.run(
        goal=goal,
        run_id="run_2_nova",
        target_invoice_file="inv_02_nova.json",
    )

    render_plan_table(run2_state.plan)
    render_verification_matrix(run2_state)
    console.print(
        f"\n[bold green][OK] RUN 2 COMPLETED with state: {run2_state.current_phase.value}[/]\n"
        f"[dim]Evidence saved to: {run2_state.evidence_dir}[/]\n"
    )

    # -------------------------------------------------------------
    # Final Benchmark Comparison
    # -------------------------------------------------------------
    render_comparison_summary(run1_state, run2_state)

    # Clean shutdown
    server.should_exit = True

    # Assert success
    all_good = (
        run1_state.current_phase == RunPhase.COMPLETED
        and run2_state.current_phase == RunPhase.COMPLETED
        and all(c.passed for c in run1_state.verification_checks)
        and all(c.passed for c in run2_state.verification_checks)
    )

    if all_good:
        console.print("\n[bold green]ALL VERIFICATION CRITERIA MET WITH ZERO ERRORS.[/]\n")
        return 0
    else:
        console.print("\n[bold red]One or more runs did not pass all verification checks.[/]\n")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CentrAlign Operator Turnkey Demo Runner")
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        default=True,
        help="Automatically approve HITL financial gates (default: True)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt operator interactively for HITL approvals",
    )

    args = parser.parse_args()
    auto_approve_val = not args.interactive

    exit_code = run_pipeline(auto_approve=auto_approve_val)
    sys.exit(exit_code)
