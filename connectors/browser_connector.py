"""Playwright browser connector for Acme Finance Portal interactions."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional
from playwright.sync_api import sync_playwright

from connectors.base import BaseConnector, ToolResult


class BrowserConnector(BaseConnector):
    """Automates web interactions on Acme Finance Portal using Playwright Chromium."""

    def __init__(self, headless: Optional[bool] = None) -> None:
        if headless is None:
            env_val = os.environ.get("HEADLESS_BROWSER", "true").lower()
            self.headless = env_val not in ("false", "0", "no")
        else:
            self.headless = headless

    def register_vendor_ui(
        self,
        portal_url: str,
        name: str,
        tax_id: str,
        bank_account: str,
        evidence_dir: str,
        step_id: str = "step_3_register_vendor",
        attempt: int = 1,
    ) -> ToolResult:
        """Navigates to /vendors/new, submits form, and returns outcome + screenshot."""
        ev_dir = Path(evidence_dir)
        ev_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = str((ev_dir / f"{step_id}_attempt_{attempt}.png").resolve())

        url = f"{portal_url.rstrip('/')}/vendors/new"

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                page.goto(url, wait_until="networkidle")

                # Fill form fields
                page.fill("#vendor-name", str(name))
                page.fill("#vendor-tax-id", str(tax_id))
                page.fill("#vendor-bank", str(bank_account))

                # Click submit
                page.click("#submit-vendor-btn")
                page.wait_for_load_state("networkidle")

                # Capture full-page screenshot
                page.screenshot(path=screenshot_path, full_page=True)

                # Check for error banner
                error_banner = page.locator("#error-banner")
                if error_banner.count() > 0 and error_banner.first.is_visible():
                    error_text = error_banner.first.inner_text().strip()
                    error_code = error_banner.first.get_attribute("data-error-code") or "VALIDATION_ERROR"
                    browser.close()
                    return ToolResult(
                        success=False,
                        error=error_text,
                        error_code=error_code,
                        screenshot_path=screenshot_path,
                    )

                # Check for success banner
                success_banner = page.locator("#success-banner")
                if success_banner.count() > 0 and success_banner.first.is_visible():
                    vendor_id = success_banner.first.get_attribute("data-vendor-id") or ""
                    browser.close()
                    return ToolResult(
                        success=True,
                        data={"vendor_id": vendor_id},
                        screenshot_path=screenshot_path,
                    )

                browser.close()
                return ToolResult(
                    success=False,
                    error="Neither success nor error banner appeared after form submission.",
                    error_code="UNEXPECTED_STATE",
                    screenshot_path=screenshot_path,
                )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Browser automation failed on register_vendor_ui: {str(exc)}",
                error_code="BROWSER_ERROR",
                screenshot_path=screenshot_path if Path(screenshot_path).exists() else None,
            )

    def schedule_payout_ui(
        self,
        portal_url: str,
        vendor_id: str,
        invoice_id: str,
        amount_inr: float,
        due_date: str,
        evidence_dir: str,
        step_id: str = "step_4_schedule_payout",
        attempt: int = 1,
    ) -> ToolResult:
        """Navigates to /payouts/new, submits form, and returns outcome + screenshot."""
        ev_dir = Path(evidence_dir)
        ev_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = str((ev_dir / f"{step_id}_attempt_{attempt}.png").resolve())

        url = f"{portal_url.rstrip('/')}/payouts/new"

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                page.goto(url, wait_until="networkidle")

                # Fill form fields
                page.fill("#payout-vendor-id", str(vendor_id))
                page.fill("#payout-invoice-id", str(invoice_id))
                page.fill("#payout-amount", str(amount_inr))
                page.fill("#payout-due-date", str(due_date))

                # Click submit
                page.click("#submit-payout-btn")
                page.wait_for_load_state("networkidle")

                # Capture full-page screenshot
                page.screenshot(path=screenshot_path, full_page=True)

                # Check for error banner
                error_banner = page.locator("#error-banner")
                if error_banner.count() > 0 and error_banner.first.is_visible():
                    error_text = error_banner.first.inner_text().strip()
                    error_code = error_banner.first.get_attribute("data-error-code") or "VALIDATION_ERROR"
                    browser.close()
                    return ToolResult(
                        success=False,
                        error=error_text,
                        error_code=error_code,
                        screenshot_path=screenshot_path,
                    )

                # Check for payout success banner
                success_banner = page.locator("#payout-success-banner")
                if success_banner.count() > 0 and success_banner.first.is_visible():
                    payout_id = success_banner.first.get_attribute("data-payout-id") or ""
                    browser.close()
                    return ToolResult(
                        success=True,
                        data={"payout_id": payout_id},
                        screenshot_path=screenshot_path,
                    )

                browser.close()
                return ToolResult(
                    success=False,
                    error="Neither payout success nor error banner appeared after submission.",
                    error_code="UNEXPECTED_STATE",
                    screenshot_path=screenshot_path,
                )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Browser automation failed on schedule_payout_ui: {str(exc)}",
                error_code="BROWSER_ERROR",
                screenshot_path=screenshot_path if Path(screenshot_path).exists() else None,
            )

    def capture_dashboard_receipt(
        self,
        portal_url: str,
        payout_id: str,
        evidence_dir: str,
    ) -> ToolResult:
        """Navigates to /, verifies payout_id in #payouts-table, and saves final_dashboard_verified.png."""
        ev_dir = Path(evidence_dir)
        ev_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = str((ev_dir / "final_dashboard_verified.png").resolve())

        url = f"{portal_url.rstrip('/')}/"

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                page = browser.new_page(viewport={"width": 1280, "height": 800})
                page.goto(url, wait_until="networkidle")

                # Wait for payouts table
                page.wait_for_selector("#payouts-table")

                # Check if payout_id text exists inside payouts table
                table_text = page.locator("#payouts-table").inner_text()
                found = payout_id in table_text

                # Capture full-page screenshot
                page.screenshot(path=screenshot_path, full_page=True)
                browser.close()

                if found:
                    return ToolResult(
                        success=True,
                        data={"verified": True, "payout_id": payout_id},
                        screenshot_path=screenshot_path,
                    )
                return ToolResult(
                    success=False,
                    error=f"Payout ID '{payout_id}' not found inside #payouts-table.",
                    error_code="RECEIPT_NOT_FOUND",
                    screenshot_path=screenshot_path,
                )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Browser verification failed on dashboard: {str(exc)}",
                error_code="BROWSER_ERROR",
                screenshot_path=screenshot_path if Path(screenshot_path).exists() else None,
            )
