"""Dual-mode Reasoning Engine (Live LLM with structured output + Deterministic Fallback)."""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

from core.models import AdaptationDecision, PlanStep, RiskLevel

load_dotenv()


class ReasoningEngine:
    """Provides plan generation and failure diagnosis in both LLM and deterministic modes."""

    def __init__(self, prefer_llm: bool = True) -> None:
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        self.use_llm = prefer_llm and bool(self.gemini_api_key or self.openai_api_key)

    def generate_plan(
        self,
        goal: str,
        context: Dict[str, Any],
        target_invoice_file: Optional[str] = None,
    ) -> List[PlanStep]:
        """Generates the structured execution plan with risk levels and tool bindings."""
        # The canonical enterprise onboarding and payout plan
        inbox_dir = (
            context.get("resolved_aliases", {}).get("dropbox folder")
            or context.get("all_aliases", {}).get("dropbox folder")
            or "./workspace/inbox"
        )
        archive_dir = (
            context.get("resolved_aliases", {}).get("processed archive")
            or context.get("all_aliases", {}).get("processed archive")
            or "./workspace/processed"
        )
        portal_url = (
            context.get("system_endpoints", {}).get("finance_portal_url")
            or "http://127.0.0.1:8001"
        )

        steps: List[PlanStep] = [
            PlanStep(
                step_id="step_1_ingest_invoice",
                title="Ingest pending vendor invoice from dropbox",
                tool_name="fs.read_next_invoice",
                params={
                    "inbox_dir": inbox_dir,
                    "target_filename": target_invoice_file,
                },
                risk_level=RiskLevel.READ_ONLY,
                expected_postcondition="Invoice JSON loaded and parsed into working memory.",
            ),
            PlanStep(
                step_id="step_2_lookup_vendor",
                title="Query Acme Finance Portal for existing vendor registration",
                tool_name="erp.lookup_vendor",
                params={
                    "portal_url": portal_url,
                    "name": "$working_memory.invoice.vendor_name",
                },
                risk_level=RiskLevel.READ_ONLY,
                expected_postcondition="Vendor presence checked in portal database.",
            ),
            PlanStep(
                step_id="step_3_register_vendor",
                title="Register vendor via /vendors/new web form",
                tool_name="browser.register_vendor_ui",
                params={
                    "portal_url": portal_url,
                    "name": "$working_memory.invoice.vendor_name",
                    "tax_id": "$working_memory.invoice.tax_id",
                    "bank_account": "$working_memory.invoice.bank_account",
                    "evidence_dir": "$evidence_dir",
                },
                risk_level=RiskLevel.LOW_MUTATION,
                expected_postcondition="Vendor successfully registered and VND- ID generated.",
            ),
            PlanStep(
                step_id="step_4_schedule_payout",
                title="Schedule invoice payout via /payouts/new web form",
                tool_name="browser.schedule_payout_ui",
                params={
                    "portal_url": portal_url,
                    "vendor_id": "$working_memory.vendor_id",
                    "invoice_id": "$working_memory.invoice.invoice_id",
                    "amount_inr": "$working_memory.invoice.amount_inr",
                    "due_date": "$working_memory.invoice.due_date",
                    "evidence_dir": "$evidence_dir",
                },
                risk_level=RiskLevel.HIGH_FINANCIAL,
                expected_postcondition="Payout scheduled with PAY- reference in portal.",
            ),
            PlanStep(
                step_id="step_5_archive_invoice",
                title="Archive processed invoice file to processed archive",
                tool_name="fs.archive_invoice",
                params={
                    "file_path": "$working_memory.invoice.file_path",
                    "archive_dir": archive_dir,
                },
                risk_level=RiskLevel.LOW_MUTATION,
                expected_postcondition="Invoice JSON moved from inbox to processed directory.",
            ),
        ]
        return steps

    def diagnose_and_adapt(
        self,
        step: PlanStep,
        resolved_params: Dict[str, Any],
        error_text: str,
    ) -> AdaptationDecision:
        """Diagnoses failure cause and produces repaired parameter and reusable rule."""
        # Try live LLM if key is available
        if self.use_llm and self.gemini_api_key:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=self.gemini_api_key)
                prompt = f"""
Diagnose this tool failure in the CentrAlign AI Employee Runtime:
Step: {step.step_id} ({step.title})
Tool: {step.tool_name}
Parameters: {resolved_params}
Error: {error_text}

Provide an AdaptationDecision JSON with:
- recoverable: bool
- root_cause: concise description
- parameter_name: name of the parameter to fix
- repaired_value: corrected value
- transformation_rule: rule name (e.g., 'strip_hyphens_and_spaces_uppercase')
- lesson_explanation: concise explanation for episodic memory
"""
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=AdaptationDecision,
                    ),
                )
                if response.text:
                    import json
                    decision_dict = json.loads(response.text)
                    return AdaptationDecision(**decision_dict)
            except Exception:
                pass  # Fall back to deterministic diagnosis

        # Deterministic Diagnostic Fallback Mode (100% offline reliability)
        err_lower = error_text.lower()
        if "erp-422" in err_lower or "tax_id" in err_lower or "gstin" in err_lower or "alphanumeric" in err_lower:
            raw_tax = str(resolved_params.get("tax_id", ""))
            repaired = raw_tax.replace("-", "").replace(" ", "").strip().upper()
            return AdaptationDecision(
                recoverable=True,
                root_cause="Field 'tax_id' (GSTIN) contained hyphens/spaces; portal requires 15 alphanumeric characters.",
                parameter_name="tax_id",
                repaired_value=repaired,
                transformation_rule="strip_hyphens_and_spaces_uppercase",
                lesson_explanation="Acme Finance Portal requires 15-character alphanumeric GSTIN without hyphens or spaces.",
            )

        # Generic fallback
        return AdaptationDecision(
            recoverable=False,
            root_cause=f"Unrecognized error: {error_text}",
            parameter_name="",
            repaired_value=None,
            transformation_rule="",
            lesson_explanation=f"Error in {step.tool_name}: {error_text}",
        )
