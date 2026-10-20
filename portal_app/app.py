"""Acme Finance Portal — Simulated Internal Enterprise Web System."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Acme Finance Portal", version="2.4")

# Database path
DB_PATH = Path(os.environ.get("PORTAL_DB_PATH", "./workspace/portal_db.json"))
MEMORY_PATH = Path(os.environ.get("MEMORY_PATH", "./workspace/company_memory.json"))
EVIDENCE_DIR = Path(os.environ.get("EVIDENCE_DIR", "./workspace/evidence"))

# Templates
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Mount evidence directory for serving screenshots
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/evidence", StaticFiles(directory=str(EVIDENCE_DIR)), name="evidence")


def _read_db() -> Dict[str, Any]:
    if DB_PATH.exists():
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"vendors": {}, "payouts": {}}


def _write_db(data: Dict[str, Any]) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    db = _read_db()
    vendors = db.get("vendors", {})
    payouts = db.get("payouts", {})
    total_volume = sum(float(p.get("amount_inr", 0)) for p in payouts.values())
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "page": "dashboard",
            "vendors": vendors,
            "payouts": payouts,
            "kpi_vendor_count": len(vendors),
            "kpi_payout_count": len(payouts),
            "kpi_payout_volume": total_volume,
        },
    )


@app.get("/vendors/new", response_class=HTMLResponse)
async def vendor_form_get(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "page": "vendor_form",
            "error_banner": None,
            "success_banner": None,
            "form_name": "",
            "form_tax_id": "",
            "form_bank": "",
        },
    )


@app.post("/vendors/new", response_class=HTMLResponse)
async def vendor_form_post(
    request: Request,
    name: str = Form(...),
    tax_id: str = Form(...),
    bank_account: str = Form(...),
) -> HTMLResponse:
    # Validation: tax_id must be exactly 15 alphanumeric chars, no hyphens/spaces
    if "-" in tax_id or " " in tax_id or len(tax_id) != 15 or not tax_id.isalnum():
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "page": "vendor_form",
                "error_banner": {
                    "code": "INVALID_TAX_ID",
                    "message": "Validation Error [ERP-422]: Field 'tax_id' must be exactly 15 alphanumeric characters without hyphens or spaces.",
                },
                "success_banner": None,
                "form_name": name,
                "form_tax_id": tax_id,
                "form_bank": bank_account,
            },
        )

    # Generate vendor ID and persist
    vendor_id = f"VND-{uuid4().hex[:6].upper()}"
    db = _read_db()
    db["vendors"][vendor_id] = {
        "vendor_id": vendor_id,
        "name": name,
        "tax_id": tax_id,
        "bank_account": bank_account,
        "status": "ACTIVE",
    }
    _write_db(db)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "page": "vendor_form",
            "error_banner": None,
            "success_banner": {"vendor_id": vendor_id},
            "form_name": name,
            "form_tax_id": tax_id,
            "form_bank": bank_account,
        },
    )


@app.get("/payouts/new", response_class=HTMLResponse)
async def payout_form_get(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "page": "payout_form",
            "error_banner": None,
            "payout_success_banner": None,
            "form_vendor_id": "",
            "form_invoice_id": "",
            "form_amount": "",
            "form_due_date": "",
        },
    )


@app.post("/payouts/new", response_class=HTMLResponse)
async def payout_form_post(
    request: Request,
    vendor_id: str = Form(...),
    invoice_id: str = Form(...),
    amount_inr: float = Form(...),
    due_date: str = Form(...),
) -> HTMLResponse:
    db = _read_db()
    # Validate vendor exists
    if vendor_id not in db.get("vendors", {}):
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "page": "payout_form",
                "error_banner": {
                    "code": "INVALID_PAYOUT",
                    "message": f"Validation Error: Vendor ID '{vendor_id}' not found in the system.",
                },
                "payout_success_banner": None,
                "form_vendor_id": vendor_id,
                "form_invoice_id": invoice_id,
                "form_amount": amount_inr,
                "form_due_date": due_date,
            },
        )

    payout_id = f"PAY-{uuid4().hex[:6].upper()}"
    db["payouts"][payout_id] = {
        "payout_id": payout_id,
        "vendor_id": vendor_id,
        "invoice_id": invoice_id,
        "amount_inr": amount_inr,
        "due_date": due_date,
        "state": "SCHEDULED",
    }
    _write_db(db)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "page": "payout_form",
            "error_banner": None,
            "payout_success_banner": {"payout_id": payout_id},
            "form_vendor_id": vendor_id,
            "form_invoice_id": invoice_id,
            "form_amount": amount_inr,
            "form_due_date": due_date,
        },
    )


@app.get("/api/lookup_vendor")
async def api_lookup_vendor(name: str = "") -> JSONResponse:
    db = _read_db()
    for vid, vendor in db.get("vendors", {}).items():
        if vendor.get("name", "").lower() == name.lower():
            return JSONResponse({"found": True, "vendor": vendor})
    return JSONResponse({"found": False, "vendor": None})


@app.get("/api/verify/state")
async def api_verify_state() -> JSONResponse:
    return JSONResponse(_read_db())


@app.post("/api/reset")
async def api_reset() -> JSONResponse:
    _write_db({"vendors": {}, "payouts": {}})
    return JSONResponse({"status": "reset", "message": "Database cleared."})


@app.get("/console", response_class=HTMLResponse)
async def console_view(request: Request) -> HTMLResponse:
    # Load episodic lessons from company memory
    lessons = []
    if MEMORY_PATH.exists():
        with open(MEMORY_PATH, "r", encoding="utf-8") as f:
            memory = json.load(f)
            lessons = memory.get("episodic_lessons", [])

    # Load run reports from evidence directories
    runs = []
    if EVIDENCE_DIR.exists():
        for run_dir in sorted(EVIDENCE_DIR.iterdir()):
            if run_dir.is_dir():
                report_path = run_dir / "report.json"
                if report_path.exists():
                    with open(report_path, "r", encoding="utf-8") as f:
                        report = json.load(f)
                    # Collect screenshot filenames
                    screenshots = [
                        f"/evidence/{run_dir.name}/{img.name}"
                        for img in run_dir.glob("*.png")
                    ]
                    runs.append({
                        "report": report,
                        "screenshots": screenshots,
                        "run_dir_name": run_dir.name,
                    })

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "page": "console",
            "lessons": lessons,
            "runs": runs,
        },
    )
