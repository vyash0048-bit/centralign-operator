"""Workspace seeding utilities for CentrAlign."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


def reset_and_seed_workspace(base_dir: Path) -> None:
    """Create (or clear) the workspace directories and populate seed data files.

    Args:
        base_dir: The project root directory under which ``workspace/`` lives.
    """
    workspace = base_dir / "workspace"

    # --- 1. Create / clear workspace sub-directories ---
    for sub in ("inbox", "processed", "evidence"):
        target = workspace / sub
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)

    # --- 2. company_memory.json ---
    company_memory: dict = {
        "organization_name": "Acme Corp India Pvt Ltd",
        "directory_aliases": {
            "dropbox folder": "./workspace/inbox",
            "processed archive": "./workspace/processed",
        },
        "system_endpoints": {
            "finance_portal_url": "http://127.0.0.1:8001",
        },
        "sops": {
            "SOP-FIN-04": {
                "title": "Standard Vendor Onboarding & Invoice Payout Procedure",
                "steps": [
                    "1. Ingest the targeted or oldest pending JSON invoice from the resolved inbox directory.",
                    "2. Query the Acme Finance Portal lookup endpoint to check if the vendor is already registered.",
                    "3. If the vendor is not registered, onboard them via the /vendors/new web form using Playwright.",
                    "4. Schedule the invoice payout via the /payouts/new web form using the registered vendor_id.",
                    "5. Move the processed invoice file from the inbox directory to the processed archive directory.",
                    "6. Run independent verification checks against the portal state API, filesystem, and live dashboard DOM.",
                ],
            },
        },
        "policies": {
            "max_autonomous_payout_inr": 50000.00,
            "require_human_approval_above_limit": True,
        },
        "episodic_lessons": [],
    }
    _write_json(workspace / "company_memory.json", company_memory)

    # --- 3. Seed invoice files ---
    inv_01_apex: dict = {
        "invoice_id": "INV-2026-0891",
        "vendor_name": "Apex Cloud Solutions Pvt Ltd",
        "tax_id": "27-AABCA-1234-F1Z5",
        "bank_account": "HDFC0001234_9988776655",
        "amount_inr": 84500.00,
        "due_date": "2026-11-15",
        "currency": "INR",
        "description": "Enterprise GPU Cluster Hosting - Q4",
    }
    _write_json(workspace / "inbox" / "inv_01_apex.json", inv_01_apex)

    inv_02_nova: dict = {
        "invoice_id": "INV-2026-0942",
        "vendor_name": "Nova Data Systems LLP",
        "tax_id": "29-GGGGG-1314-R9Z6",
        "bank_account": "ICIC0005678_1122334455",
        "amount_inr": 32000.00,
        "due_date": "2026-11-20",
        "currency": "INR",
        "description": "Annual Security Audit & Penetration Testing",
    }
    _write_json(workspace / "inbox" / "inv_02_nova.json", inv_02_nova)

    # --- 4. Portal database seed ---
    portal_db: dict = {"vendors": {}, "payouts": {}}
    _write_json(workspace / "portal_db.json", portal_db)


def _write_json(path: Path, data: dict) -> None:
    """Write a Python dict to *path* as pretty-printed JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
