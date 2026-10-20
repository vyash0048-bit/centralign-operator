"""Independent post-condition outcome verifier for CentrAlign runtime."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple
import httpx

from connectors.browser_connector import BrowserConnector
from core.models import VerificationCheck


class OutcomeVerifier:
    """Verifies all external effects against systems of record independently."""

    def __init__(self, browser_connector: BrowserConnector | None = None) -> None:
        self.browser = browser_connector or BrowserConnector()

    def verify(
        self,
        portal_url: str,
        working_memory: Dict[str, Any],
        evidence_dir: str,
    ) -> List[VerificationCheck]:
        """Runs the 5 canonical independent post-condition verification checks."""
        checks: List[VerificationCheck] = []

        invoice = working_memory.get("invoice", {})
        vendor_id = working_memory.get("vendor_id", "")
        payout_id = working_memory.get("payout_id", "")
        original_file_path = invoice.get("file_path", "")
        invoice_amount = float(invoice.get("amount_inr", 0.0))

        # Query portal state API
        db_state: Dict[str, Any] = {"vendors": {}, "payouts": {}}
        state_api_url = f"{portal_url.rstrip('/')}/api/verify/state"
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(state_api_url)
                if resp.status_code == 200:
                    db_state = resp.json()
        except Exception:
            pass

        vendors_db = db_state.get("vendors", {})
        payouts_db = db_state.get("payouts", {})

        # Check 1: vendor_persisted
        vendor_record = vendors_db.get(vendor_id)
        v_passed = False
        v_actual = None
        if vendor_record:
            tax_id = vendor_record.get("tax_id", "")
            if len(tax_id) == 15 and tax_id.isalnum():
                v_passed = True
            v_actual = f"Found: {vendor_id} (tax_id: {tax_id})"
        else:
            v_actual = f"Vendor '{vendor_id}' not found in portal DB"

        checks.append(
            VerificationCheck(
                check_name="vendor_persisted",
                passed=v_passed,
                expected=f"Vendor '{vendor_id}' with 15-char alphanumeric tax_id",
                actual=v_actual,
                evidence_source=f"GET {state_api_url}",
            )
        )

        # Check 2: payout_scheduled
        payout_record = payouts_db.get(payout_id)
        p_passed = False
        p_actual = None
        if payout_record and payout_record.get("state") == "SCHEDULED":
            p_passed = True
            p_actual = f"Found: {payout_id} (state: {payout_record.get('state')})"
        else:
            p_actual = f"Payout '{payout_id}' not found or state != SCHEDULED"

        checks.append(
            VerificationCheck(
                check_name="payout_scheduled",
                passed=p_passed,
                expected=f"Payout '{payout_id}' with state == 'SCHEDULED'",
                actual=p_actual,
                evidence_source=f"GET {state_api_url}",
            )
        )

        # Check 3: amount_integrity
        db_amount = float(payout_record.get("amount_inr", 0.0)) if payout_record else -1.0
        amount_passed = (abs(db_amount - invoice_amount) < 0.01) and (invoice_amount > 0)
        checks.append(
            VerificationCheck(
                check_name="amount_integrity",
                passed=amount_passed,
                expected=f"₹{invoice_amount:,.2f}",
                actual=f"₹{db_amount:,.2f}",
                evidence_source="Reconciliation: Source Invoice vs. Portal DB Record",
            )
        )

        # Check 4: file_lifecycle
        file_name = Path(original_file_path).name if original_file_path else ""
        inbox_exists = False
        processed_exists = False
        if file_name:
            # Check inbox
            inbox_candidate = Path("./workspace/inbox") / file_name
            inbox_exists = inbox_candidate.exists()
            # Check processed
            processed_candidate = Path("./workspace/processed") / file_name
            processed_exists = processed_candidate.exists()

        file_passed = (not inbox_exists) and processed_exists
        checks.append(
            VerificationCheck(
                check_name="file_lifecycle",
                passed=file_passed,
                expected=f"File '{file_name}' removed from inbox/ and present in processed/",
                actual=f"inbox={inbox_exists}, processed={processed_exists}",
                evidence_source="Local FileSystem Inspection (workspace/)",
            )
        )

        # Check 5: visual_dom_receipt
        receipt_result = self.browser.capture_dashboard_receipt(
            portal_url=portal_url,
            payout_id=payout_id,
            evidence_dir=evidence_dir,
        )
        checks.append(
            VerificationCheck(
                check_name="visual_dom_receipt",
                passed=receipt_result.success,
                expected=f"Payout ID '{payout_id}' visible in #payouts-table and screenshot saved",
                actual=f"Rendered in DOM: {receipt_result.success}. Screenshot: {receipt_result.screenshot_path}",
                evidence_source="Playwright Chromium DOM Inspection (GET /)",
            )
        )

        return checks
