# tasks.md — CentrAlign Execution & Verification Checklist

> **Instructions for Antigravity Agent:**
> Work through these phases sequentially. Cross-reference `@PRD.md`, `@Rules.md`, `@Architecture.md`, and `@design.md` for exact schemas, DOM selector IDs, and business logic. Mark each task `[x]` as you complete it, and **do not proceed to the next phase until that phase's Verification Gate passes with zero errors.**

---

## Phase 1: Workspace Bootstrap, Dependencies & Seed Data
- [x] **1.1. Create Project Skeleton:** Create directories `portal_app/templates/`, `core/`, `connectors/`, `workspace/inbox/`, `workspace/processed/`, `workspace/evidence/`, and `tests/` with required `__init__.py` files.
- [x] **1.2. Create `requirements.txt`:** Include `fastapi`, `uvicorn`, `jinja2`, `python-multipart`, `playwright`, `pydantic>=2.0`, `httpx`, `rich`, `pytest`, `python-dotenv`, and `google-genai`.
- [x] **1.3. Create `.env.example`:** Include `GEMINI_API_KEY=`, `OPENAI_API_KEY=`, `PORTAL_URL=http://127.0.0.1:8001`, and `HEADLESS_BROWSER=true`.
- [x] **1.4. Install Environment & Browser Binaries:**
  - Install Python packages from `requirements.txt`.
  - Run `playwright install chromium` so headless browser execution works out of the box.
- [x] **1.5. Create Workspace Seeder Utility (`core/seed.py` or inside `core/memory.py`):**
  - Function `reset_and_seed_workspace(base_dir: Path)` that cleanly resets `./workspace/` before demo or test runs:
    - Writes `./workspace/company_memory.json` with exact `directory_aliases`, `system_endpoints`, `SOP-FIN-04`, `policies` (`max_autonomous_payout_inr: 50000.0`), and empty `episodic_lessons: []` per `design.md` Section 5.3.
    - Writes `./workspace/inbox/inv_01_apex.json` (`INV-2026-0891`, `Apex Cloud Solutions Pvt Ltd`, `tax_id: "27-AABCA-1234-F1Z5"`, `amount_inr: 84500.00`).
    - Writes `./workspace/inbox/inv_02_nova.json` (`INV-2026-0942`, `Nova Data Systems LLP`, `tax_id: "29-GGGGG-1314-R9Z6"`, `amount_inr: 32000.00`).
    - Clears `./workspace/processed/` and initializes `./workspace/portal_db.json` with `{"vendors": {}, "payouts": {}}`.
- [x] **Phase 1 Verification Gate:** Run a quick Python one-liner to execute `reset_and_seed_workspace()` and confirm all JSON files exist and parse cleanly.

---

## Phase 2: Core Domain Schemas & Persistent Organizational Memory
- [x] **2.1. Implement `core/models.py`:**
  - Define `RunPhase(str, Enum)`: `GOAL`, `UNDERSTAND`, `PLAN`, `EXECUTE`, `OBSERVE`, `ADAPT`, `WAITING_FOR_APPROVAL`, `VERIFY`, `COMPLETED`, `FAILED`.
  - Define `RiskLevel(str, Enum)`: `READ_ONLY`, `LOW_MUTATION`, `HIGH_FINANCIAL`.
  - Define Pydantic v2 models: `EpisodicLesson`, `PlanStep`, `AdaptationDecision`, `VerificationCheck`, `AuditEvent`, and `TaskRunState`.
- [x] **2.2. Implement `core/memory.py` (`CompanyMemoryStore`):**
  - Load and save `./workspace/company_memory.json`.
  - Implement `resolve_context(raw_goal: str) -> Dict[str, Any]` to map aliases (`"dropbox folder"` -> `"./workspace/inbox"`), attach `SOP-FIN-04`, load active policies, and load existing `episodic_lessons`.
  - Implement `apply_episodic_lessons(tool_name: str, params: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]` supporting transformation rules (`"strip_hyphens_and_spaces_uppercase"`, `"trim_whitespace"`, `"uppercase"`).
  - Implement `record_lesson(lesson: EpisodicLesson) -> None` with deduplication so learned rules persist across runs.
- [x] **Phase 2 Verification Gate:** Verify `CompanyMemoryStore` round-trips an `EpisodicLesson` to disk and pre-sanitizes `"29-GGGGG-1314-R9Z6"` into `"29GGGGG1314R9Z6"`.

---

## Phase 3: Target Enterprise Web System — Acme Finance Portal (`portal_app/`)
- [x] **3.1. Implement `portal_app/app.py`:**
  - Mount static/evidence directory `/evidence` -> `./workspace/evidence` so screenshots can be viewed in the browser console.
  - Implement JSON database helpers reading/writing `./workspace/portal_db.json`.
  - **`GET /`:** Render dashboard with KPIs (`#kpi-vendor-count`, `#kpi-payout-count`, `#kpi-payout-volume`), `#vendors-table`, and `#payouts-table`.
  - **`GET /vendors/new` & `POST /vendors/new`:**
    - Render form with exact IDs: `#vendor-name`, `#vendor-tax-id`, `#vendor-bank`, `#submit-vendor-btn`.
    - Validate `tax_id`: if `"-"` in `tax_id` or `" "` in `tax_id` or `len(tax_id) != 15` or not `tax_id.isalnum()`, render `#error-banner` with `data-error-code="INVALID_TAX_ID"` and message: `"Validation Error [ERP-422]: Field 'tax_id' must be exactly 15 alphanumeric characters without hyphens or spaces."` Keep submitted form values populated in the inputs for the failure screenshot.
    - On valid input, generate `VND-XXXXXX`, persist to `portal_db.json`, and render `#success-banner` with `data-vendor-id="{{ vendor_id }}"`.
  - **`GET /payouts/new` & `POST /payouts/new`:**
    - Render form with exact IDs: `#payout-vendor-id`, `#payout-invoice-id`, `#payout-amount`, `#payout-due-date`, `#submit-payout-btn`.
    - Validate `vendor_id` exists in `portal_db.json`. If valid, generate `PAY-XXXXXX` with `state="SCHEDULED"`, persist, and render `#payout-success-banner` with `data-payout-id="{{ payout_id }}"`.
  - **`GET /api/lookup_vendor`:** Query by `name` (case-insensitive) and return `{"found": bool, "vendor": ...}`.
  - **`GET /api/verify/state`:** Return full `{"vendors": ..., "payouts": ...}` JSON state.
  - **`POST /api/reset`:** Reset `portal_db.json` to empty state.
  - **`GET /console`:** Render the CentrAlign Operator Console displaying learned `episodic_lessons` from `company_memory.json`, run reports from `./workspace/evidence/*/report.json`, verification badges, and embedded evidence screenshots.
- [x] **3.2. Implement `portal_app/templates/index.html` (or modular Jinja templates):**
  - Apply the exact CSS design tokens from `design.md` Section 2.1 so every page looks like a modern enterprise finance app (`1280x800` clean layout, high-contrast emerald/red banners, monospace ID pills).
- [x] **Phase 3 Verification Gate:** Use `fastapi.testclient.TestClient` to test `GET /`, `POST /vendors/new` (confirming hyphenated GSTIN returns `#error-banner` and clean 15-char GSTIN returns `#success-banner`), `POST /payouts/new`, and `GET /api/verify/state`.

---

## Phase 4: Reusable Tool & Connector Abstractions (`connectors/`)
- [x] **4.1. Implement `connectors/base.py`:**
  - Define `ToolResult(BaseModel)` with `success`, `data`, `error`, `error_code`, and `screenshot_path`.
  - Define `BaseConnector` interface and `ToolRegistry`.
- [x] **4.2. Implement `connectors/file_connector.py` (`FileConnector`):**
  - `fs.read_next_invoice(inbox_dir: str, target_filename: Optional[str] = None) -> ToolResult`
  - `fs.archive_invoice(file_path: str, archive_dir: str) -> ToolResult`
- [x] **4.3. Implement `connectors/erp_api_connector.py` (`ERPConnector`):**
  - `erp.lookup_vendor(portal_url: str, name: str) -> ToolResult`
  - `erp.fetch_system_state(portal_url: str) -> ToolResult`
- [x] **4.4. Implement `connectors/browser_connector.py` (`BrowserConnector`):**
  - Use Playwright Chromium (`viewport={"width": 1280, "height": 800}`).
  - `browser.register_vendor_ui(...)`: Navigate to `/vendors/new`, fill `#vendor-name`, `#vendor-tax-id`, `#vendor-bank`, click `#submit-vendor-btn`, save screenshot `{evidence_dir}/{step_id}_attempt_{attempt}.png`, inspect `#error-banner` vs. `#success-banner`, and return `ToolResult`.
  - `browser.schedule_payout_ui(...)`: Navigate to `/payouts/new`, fill `#payout-vendor-id`, `#payout-invoice-id`, `#payout-amount`, `#payout-due-date`, click `#submit-payout-btn`, save screenshot `{evidence_dir}/{step_id}_attempt_{attempt}.png`, inspect `#payout-success-banner`, and return `ToolResult`.
  - `browser.capture_dashboard_receipt(...)`: Navigate to `/`, verify `payout_id` appears inside `#payouts-table`, save `{evidence_dir}/final_dashboard_verified.png`, and return `ToolResult`.
- [x] **Phase 4 Verification Gate:** Start `portal_app` on a local test port and verify `BrowserConnector` captures real PNG screenshots for both a failed vendor registration (`#error-banner`) and a succeeded registration (`#success-banner`).

---

## Phase 5: Reasoning, Policy Gate & Independent Verifier (`core/`)
- [x] **5.1. Implement `core/llm.py` (`ReasoningEngine`):**
  - Implement `generate_plan(goal, context, target_invoice_file)` returning the 5-step `List[PlanStep]` (`step_1_ingest_invoice`, `step_2_lookup_vendor`, `step_3_register_vendor`, `step_4_schedule_payout`, `step_5_archive_invoice`) with late-bound `$working_memory.*` references.
  - Implement `diagnose_and_adapt(step, resolved_params, error_text) -> AdaptationDecision`:
    - Support live Gemini/OpenAI structured output when API key is configured.
    - Include deterministic fallback diagnosis for `ERP-422` / `INVALID_TAX_ID` that strips hyphens/spaces from `tax_id`, returns `repaired_value`, and specifies `transformation_rule="strip_hyphens_and_spaces_uppercase"`.
- [x] **5.2. Implement `core/policy.py` (`PolicyEngine`):**
  - Implement `requires_approval(step: PlanStep, resolved_params: Dict[str, Any], policies: Dict[str, Any]) -> Tuple[bool, str]`.
  - Trigger HITL requirement when `step.risk_level == RiskLevel.HIGH_FINANCIAL` and `float(resolved_params.get("amount_inr", 0)) > float(policies.get("max_autonomous_payout_inr", 50000))`.
  - Implement checkpoint serialization to `{evidence_dir}/checkpoint_hitl.json`.
- [x] **5.3. Implement `core/verifier.py` (`OutcomeVerifier`):**
  - Implement the 5 independent post-condition checks specified in `Architecture.md` Section 7:
    1. `vendor_persisted` (via `/api/verify/state`)
    2. `payout_scheduled` (via `/api/verify/state`)
    3. `amount_integrity` (DB payout amount == source invoice `amount_inr`)
    4. `file_lifecycle` (source file removed from `inbox/` and exists in `processed/`)
    5. `visual_dom_receipt` (Playwright check on `/` `#payouts-table` + `final_dashboard_verified.png`)

---

## Phase 6: The Autonomous State Machine Runtime (`core/runtime.py`)
- [x] **6.1. Implement `CentrAlignRuntime`:**
  - Orchestrate the full lifecycle: `GOAL → UNDERSTAND → PLAN → EXECUTE → OBSERVE → ADAPT → VERIFY → COMPLETE`.
  - Implement `_resolve_params()` for `$working_memory.*` pointers.
  - Before executing each step, invoke `CompanyMemoryStore.apply_episodic_lessons()` and log `[MEMORY APPLIED]` when a parameter is pre-sanitized.
  - Evaluate `PolicyEngine.requires_approval()`; when triggered, transition to `WAITING_FOR_APPROVAL`, write `checkpoint_hitl.json`, and invoke the approval callback.
  - Handle step outputs:
    - If `step_2_lookup_vendor` finds an existing vendor, store `vendor_id` and mark `step_3_register_vendor` as `SKIPPED`.
    - If a step fails (`ToolResult.success == False`), transition to `OBSERVE` -> `ADAPT`, invoke `ReasoningEngine.diagnose_and_adapt()`, persist the new `EpisodicLesson` via `CompanyMemoryStore.record_lesson()`, mutate the step parameter, and retry (up to `max_attempts = 3`).
  - After all steps complete, transition to `VERIFY`, run `OutcomeVerifier.verify()`, and set final phase to `COMPLETED` (if all 5 checks pass) or `FAILED`.
  - Persist `{evidence_dir}/report.json` containing the full `TaskRunState`.

---

## Phase 7: Turnkey Demo Runner & Automated Test Suite
- [x] **7.1. Implement `run_demo.py`:**
  - Support CLI flags `--auto-approve` (default `True` for turnkey runs) and `--interactive`.
  - Automatically start the FastAPI `portal_app` server in a background thread/process on `127.0.0.1:8001` and poll `/api/verify/state` until ready.
  - Call `reset_and_seed_workspace()` so every demo starts clean.
  - Execute **Run 1 (`inv_01_apex.json` — ₹84,500, hyphenated GSTIN `27-AABCA-1234-F1Z5`)** with rich console panels/tables showing:
    - Attempt 1 failing on `/vendors/new` with screenshot captured
    - Self-healing adaptation stripping hyphens and saving `LSN-001` to `company_memory.json`
    - Attempt 2 succeeding
    - Policy Gate pausing on ₹84,500 (> ₹50,000 limit), saving `checkpoint_hitl.json`, and obtaining approval
    - All 5 Independent Verification checks passing.
  - Execute **Run 2 (`inv_02_nova.json` — ₹32,000, hyphenated GSTIN `29-GGGGG-1314-R9Z6`)** showing:
    - Episodic memory `LSN-001` pre-sanitizing the GSTIN *before* Attempt 1 (succeeds on Attempt 1 with zero browser errors!)
    - Policy Gate auto-clearing ₹32,000 (<= ₹50,000 limit) without human interruption
    - All 5 Independent Verification checks passing.
  - Render the final **Run 1 vs. Run 2 Comparative Summary Table** from `design.md` Section 4.
- [x] **7.2. Implement `tests/test_runtime.py`:**
  - End-to-end `pytest` suite asserting:
    - Run 1 completes with `current_phase == RunPhase.COMPLETED`, `step_3_register_vendor.attempts == 2`, HITL checkpoint created, 1 episodic lesson saved in `company_memory.json`, all 5 verification checks `True`, and PNG screenshots present on disk.
    - Run 2 completes with `current_phase == RunPhase.COMPLETED`, `step_3_register_vendor.attempts == 1` (proving episodic memory reuse), no HITL interruption triggered, and all 5 verification checks `True`.
- [x] **Phase 7 Verification Gate:**
  - Run `pytest -v` and confirm 100% pass rate.
  - Run `python run_demo.py --auto-approve` and confirm clean exit code `0`.

---

## Phase 8: Founding Engineer Submission Documentation (`README.md`)
- [x] **8.1. Write `README.md`:**
  - Executive overview of CentrAlign's architecture (`Probabilistic Reasoning + Deterministic Runtime Guarantees`).
  - ASCII architecture diagram and explanation of the `Goal → Understand → Plan → Execute → Observe → Adapt → Verify → Complete` state machine.
  - Walkthrough of the **Two-Run Vendor Onboarding & Payout Proof of Concept** (Self-Healing + HITL Gate in Run 1 -> Episodic Memory Pre-Sanitization in Run 2).
  - Exact 3-command Quickstart (`pip install -r requirements.txt && playwright install chromium && python run_demo.py --auto-approve`).
  - Notes on how the prototype maps to a multi-tenant production stack (Temporal/pgmq durable execution, ephemeral microVM sandboxes, pgvector hybrid memory).
- [x] **Final Acceptance Gate:** Verify all checkboxes in `tasks.md` are marked `[x]`, `pytest` passes, and `./workspace/evidence/` contains full reports and PNG screenshots for both runs.