# PRD: CentrAlign — Autonomous AI Employee Runtime & Proof of Concept

## 1. Executive Summary & Product Vision
CentrAlign is an autonomous AI Employee runtime designed to take short, underspecified business requests and turn them into **verified, completed work** across files, web browsers, and internal company systems.

Unlike standard chat assistants or brittle prompt chains, CentrAlign separates **probabilistic reasoning** (understanding intent, planning, diagnosing unexpected errors) from **deterministic runtime guarantees** (organizational memory lookup, policy/permission enforcement, Human-in-the-Loop pauses, and independent post-condition verification).

### Core Execution Loop
Every task executes as an explicit, inspectable state machine:
`GOAL → UNDERSTAND → PLAN → EXECUTE → OBSERVE → ADAPT → VERIFY → COMPLETE`

---

## 2. Target Demonstration Scenario (The "Golden Path")
To prove genuine autonomy over surface-level breadth, this prototype implements an end-to-end **Enterprise Vendor Onboarding & Payout Workflow** operating across a local filesystem and a realistic internal web application (**Acme Finance Portal**) via a real headless/headed Chromium browser (Playwright).

### User Prompt Given to the Operator
> *"Process the pending vendor invoice in the dropbox folder, onboard the vendor into the finance portal if they aren't registered yet, and schedule their payout."*

### What the Runtime Must Demonstrate across Two Consecutive Runs

1. **Context Hydration (`UNDERSTAND`):**
   - Queries persistent **Company Memory** (`company_memory.json`) to resolve `"dropbox folder"` to `./workspace/inbox/`, retrieve Standard Operating Procedure `SOP-FIN-04`, and load the company policy stating that **payouts exceeding ₹50,000 require Human-in-the-Loop (HITL) Finance Approval**.
2. **Dynamic Planning (`PLAN`):**
   - Generates a structured multi-step execution plan with tool bindings, risk classifications (`READ_ONLY`, `LOW_MUTATION`, `HIGH_FINANCIAL`), and verification predicates.
3. **Multi-Tool Execution (`EXECUTE`):**
   - Uses `FileConnector` to parse the invoice (`./workspace/inbox/inv_01_apex.json` for *Apex Cloud Solutions*, Amount: `₹84,500`, GSTIN/Tax ID: `27-AABCA-1234-F1Z5`).
   - Uses `BrowserConnector` (Playwright) to open the internal **Acme Finance Portal** (`http://127.0.0.1:8001`), search for the vendor, and navigate to the Vendor Registration form (`/vendors/new`).
4. **Failure Observation & Self-Healing (`OBSERVE → ADAPT`):**
   - On **Run 1**, submitting `27-AABCA-1234-F1Z5` into the portal triggers a realistic UI error banner (`#error-banner`): *"Validation Error: Tax ID (GSTIN) must be 15 alphanumeric characters without hyphens or spaces."*
   - The runtime captures a failure screenshot, extracts the DOM error text, adapts the parameter to `27AABCA1234F1Z5`, retries the form submission successfully, and **persists an episodic memory lesson** (`company_memory.json`) so future runs never repeat this mistake.
5. **Policy Interception & Human-in-the-Loop (`WAITING_FOR_APPROVAL`):**
   - Before submitting the `₹84,500` payout on `/payouts/new`, the **Policy Engine** intercepts the step because `84500 > 50000` (autonomous limit).
   - The runtime checkpoints its state to disk and pauses for human approval (via CLI prompt or Operator UI button) displaying the vendor details, invoice ID, and exact payout amount.
6. **Independent Verification & Evidence Bundle (`VERIFY → COMPLETE`):**
   - After human approval and form submission, an **Independent Verifier** queries the portal's read-only verification API (`GET /api/verify/state`), checks the DOM confirmation receipt, captures a final verification screenshot, moves the invoice file to `./workspace/processed/`, and writes a comprehensive **Evidence Pack** (`./workspace/evidence/<run_id>/report.json` + PNG screenshots).
7. **Second-Run Learning Proof (`Run 2`):**
   - When run on a second invoice (`inv_02_nova.json`, GSTIN `29-GGGGG-1314-R9Z6`, Amount: `₹32,000`), the agent retrieves the episodic lesson learned in Run 1, **pre-emptively strips the hyphens before Attempt 1** (zero browser errors), bypasses human approval because `₹32,000 <= ₹50,000`, and completes autonomously in one pass.

---

## 3. Technical Stack & Requirements
- **Language:** Python 3.11+
- **Web Framework (Target Portal & Operator Console):** FastAPI, Uvicorn, Jinja2
- **Browser Automation / Computer Use:** Playwright (`playwright` async/sync Python API, Chromium)
- **LLM Integration:** Dual-mode reasoning adapter (`core/llm.py`):
  - **Live LLM Mode:** Uses `google-genai` (`gemini-2.5-flash`) or `openai` (`gpt-4o-mini`) with Pydantic structured outputs when `GEMINI_API_KEY` or `OPENAI_API_KEY` is present in `.env`.
  - **Deterministic Fallback Mode:** Built-in rule/heuristic planner and error healer so the repository runs 100% out-of-the-box during evaluation even without API keys.
- **Data Validation & State Serialization:** Pydantic v2
- **Terminal Output & CLI UX:** `rich` (for live state machine tables, step spinners, and colored audit logs)
- **Testing:** `pytest`, `httpx`

---

## 4. Repository Directory Structure
Antigravity must create the following exact file structure:

```text
centralign-operator/
├── PRD.md
├── README.md
├── requirements.txt
├── .env.example
├── portal_app/                     # Simulated Internal Enterprise Web System
│   ├── __init__.py
│   ├── app.py                      # FastAPI server running on port 8001
│   └── templates/
│       └── index.html              # Clean internal Finance Portal UI (Vendors + Payouts)
├── core/                           # CentrAlign AI Employee Runtime
│   ├── __init__.py
│   ├── models.py                   # Pydantic schemas for State, Plan, Memory, Evidence
│   ├── memory.py                   # Semantic (SOPs/Policies) + Episodic (Learned Lessons) store
│   ├── llm.py                      # LLM Structured Output adapter + deterministic fallback
│   ├── policy.py                   # Permission & blast-radius evaluator + HITL gate
│   ├── verifier.py                 # Independent post-condition outcome verifier
│   └── runtime.py                  # Core state machine (Goal -> Understand -> Plan -> Execute -> Adapt -> Verify)
├── connectors/                     # Reusable Tool & Connector Abstractions
│   ├── __init__.py
│   ├── base.py                     # Abstract BaseConnector & ToolResult schema
│   ├── file_connector.py           # Workspace filesystem operations
│   ├── browser_connector.py        # Playwright computer/browser operator with screenshot evidence
│   └── erp_api_connector.py        # Direct read-only API connector for independent verification
├── workspace/                      # Runtime Workspace (auto-seeded by setup script)
│   ├── company_memory.json         # Seeded organizational context, SOPs, and learned lessons
│   ├── inbox/
│   │   ├── inv_01_apex.json        # ₹84,500 invoice (triggers GSTIN adaptation + HITL gate)
│   │   └── inv_02_nova.json        # ₹32,000 invoice (proves episodic memory reuse + auto-approval)
│   ├── processed/                  # Completed invoices moved here
│   └── evidence/                   # Per-run audit logs, state checkpoints, and PNG screenshots
├── run_demo.py                     # Turnkey orchestrator: starts portal, runs Run 1 & Run 2, outputs evidence
└── tests/
    └── test_runtime.py             # End-to-end automated verification tests
```

## 5. Detailed Component Specifications
### 5.1. Target Enterprise System: Acme Finance Portal (portal_app/app.py)
A self-contained FastAPI web application running on http://127.0.0.1:8001 backed by an in-memory/JSON SQLite or JSON file store (./workspace/portal_db.json).

Exact Routes & DOM Selector Contracts (CRITICAL: Do not deviate from these IDs):

GET / — Dashboard showing registered vendors table (#vendors-table) and scheduled payouts table (#payouts-table).

GET /vendors/new — HTML form to register a vendor:

Input: <input id="vendor-name" name="name" type="text" required />

Input: <input id="vendor-tax-id" name="tax_id" type="text" required />

Input: <input id="vendor-bank" name="bank_account" type="text" required />

Submit Button: <button id="submit-vendor-btn" type="submit">Register Vendor</button>

Error Container (rendered when validation fails): <div id="error-banner" data-error-code="INVALID_TAX_ID">...</div>

Success Container (rendered when registration succeeds): <div id="success-banner" data-vendor-id="VND-XXXX">Vendor registered successfully</div>

POST /vendors/new — Validates input:

Validation Rule: If tax_id contains - or spaces, or len(tax_id) != 15 or not tax_id.isalnum(), return HTTP 200 with the form HTML displaying #error-banner containing exact text:
"Validation Error [ERP-422]: Field 'tax_id' must be exactly 15 alphanumeric characters without hyphens or spaces."

On valid input, generate vendor_id = f"VND-{uuid4().hex[:6].upper()}", persist to portal_db.json, and render #success-banner with data-vendor-id.

GET /payouts/new — HTML form to schedule a vendor payout:

Input: <input id="payout-vendor-id" name="vendor_id" type="text" required />

Input: <input id="payout-invoice-id" name="invoice_id" type="text" required />

Input: <input id="payout-amount" name="amount_inr" type="number" step="0.01" required />

Input: <input id="payout-due-date" name="due_date" type="text" required />

Submit Button: <button id="submit-payout-btn" type="submit">Schedule Payout</button>

Error Container: <div id="error-banner">...</div>

Success Container: <div id="payout-success-banner" data-payout-id="PAY-XXXX">Payout scheduled successfully</div>

POST /payouts/new — Validates that vendor_id exists in portal_db.json. If valid, creates payout record with state="SCHEDULED" and renders #payout-success-banner.

GET /api/lookup_vendor?name=<name> — Returns {"found": bool, "vendor": {...} | None}.

GET /api/verify/state — Returns the complete { "vendors": {...}, "payouts": {...} } database state for independent post-condition verification.

POST /api/reset — Resets portal_db.json for clean demo runs.

### 5.2. Core Domain Models (core/models.py)
Implement strict Pydantic v2 models:

RunPhase(str, Enum): GOAL, UNDERSTAND, PLAN, EXECUTE, OBSERVE, ADAPT, WAITING_FOR_APPROVAL, VERIFY, COMPLETED, FAILED.

RiskLevel(str, Enum): READ_ONLY, LOW_MUTATION, HIGH_FINANCIAL.

EpisodicLesson(BaseModel):

lesson_id: str

tool_name: str

error_signature: str

parameter_name: str

transformation_rule: str (e.g., "strip_hyphens_and_spaces_uppercase")

explanation: str

created_at: str

PlanStep(BaseModel):

step_id: str

title: str

tool_name: str

params: Dict[str, Any]

risk_level: RiskLevel

expected_postcondition: str

status: Literal["PENDING", "IN_PROGRESS", "COMPLETED", "SKIPPED", "FAILED", "ABORTED"] = "PENDING"

attempts: int = 0

output: Optional[Dict[str, Any]] = None

error_history: List[str] = []

screenshot_paths: List[str] = []

VerificationCheck(BaseModel):

check_name: str

passed: bool

expected: Any

actual: Any

evidence_source: str

TaskRunState(BaseModel):

run_id: str

goal: str

current_phase: RunPhase

resolved_context: Dict[str, Any]

plan: List[PlanStep]

working_memory: Dict[str, Any]

audit_log: List[Dict[str, Any]]

verification_checks: List[VerificationCheck]

evidence_dir: str

### 5.3. Organizational Memory (core/memory.py)
Manages ./workspace/company_memory.json with three responsibilities:

Seed Default Organizational Knowledge:

directory_aliases: {"dropbox folder": "./workspace/inbox", "processed archive": "./workspace/processed"}

system_endpoints: {"finance_portal_url": "http://127.0.0.1:8001"}

sops: {"SOP-FIN-04": "1. Read oldest pending JSON invoice from inbox. 2. Check if vendor is already registered in Finance Portal. 3. If not registered, register vendor via /vendors/new UI form. 4. Schedule payout via /payouts/new UI form. 5. Move processed invoice file to processed archive. 6. Independently verify vendor and payout status."}

policies: {"max_autonomous_payout_inr": 50000.0, "require_human_approval_above_limit": True}

episodic_lessons: []

Pre-Execution Parameter Sanitization:

Before executing any PlanStep, check episodic_lessons for matching tool_name and parameter_name. If a rule like "strip_hyphens_and_spaces_uppercase" exists, automatically transform the parameter and log [MEMORY APPLIED] in the audit trail.

Persistence of New Lessons:

When the ADAPT phase resolves a validation error, append the new EpisodicLesson to company_memory.json immediately.

### 5.4. Tool & Connector Layer (connectors/)
All tools inherit from BaseConnector and return a standardized ToolResult(success: bool, data: dict, error: str | None, screenshot_path: str | None).

FileConnector (connectors/file_connector.py):

fs.read_next_invoice(inbox_dir, target_filename=None): Reads the target or earliest .json invoice in inbox_dir, returns parsed invoice dict (invoice_id, vendor_name, tax_id, bank_account, amount_inr, due_date, file_path).

fs.archive_invoice(file_path, archive_dir): Moves the processed invoice file from inbox/ to processed/.

BrowserConnector (connectors/browser_connector.py):

Uses Playwright (sync_playwright or async_playwright) to drive headless Chromium.

browser.register_vendor_ui(portal_url, name, tax_id, bank_account, evidence_dir, step_id, attempt):

Navigates to f"{portal_url}/vendors/new".

Fills #vendor-name, #vendor-tax-id, #vendor-bank.

Clicks #submit-vendor-btn.

Captures full-page screenshot f"{evidence_dir}/{step_id}_attempt_{attempt}.png".

Checks if #error-banner is visible. If visible, extracts #error-banner inner text and returns ToolResult(success=False, error=banner_text, screenshot_path=...).

Checks if #success-banner is visible. Extracts data-vendor-id attribute and returns ToolResult(success=True, data={"vendor_id": vendor_id}, screenshot_path=...).

browser.schedule_payout_ui(portal_url, vendor_id, invoice_id, amount_inr, due_date, evidence_dir, step_id, attempt):

Navigates to f"{portal_url}/payouts/new".

Fills #payout-vendor-id, #payout-invoice-id, #payout-amount, #payout-due-date.

Clicks #submit-payout-btn.

Captures screenshot f"{evidence_dir}/{step_id}_attempt_{attempt}.png".

Verifies #payout-success-banner is visible, extracts data-payout-id, and returns ToolResult(success=True, data={"payout_id": payout_id}, screenshot_path=...).

ERPConnector (connectors/erp_api_connector.py):

erp.lookup_vendor(portal_url, name): Calls GET /api/lookup_vendor?name=....

erp.fetch_system_state(portal_url): Calls GET /api/verify/state for the independent verifier.

### 5.5. Policy Gate & Human-in-the-Loop (core/policy.py)
Evaluates each step before tool execution.

If step.risk_level == RiskLevel.HIGH_FINANCIAL and float(params["amount_inr"]) > policies["max_autonomous_payout_inr"]:

Transitions TaskRunState.current_phase to WAITING_FOR_APPROVAL.

Saves a serialized state checkpoint to workspace/evidence/<run_id>/checkpoint_hitl.json.

Invokes the configured approval_handler(step, resolved_params, reason).

Supports both interactive CLI prompt ([y/n]) and an automated --auto-approve flag for non-interactive CI/demo execution.

### 5.6. Independent Verifier (core/verifier.py)
Must run after all plan steps finish and never trust the tool's return value alone. It performs 5 independent checks against the live environment:

vendor_exists_in_portal_db: Queries GET /api/verify/state and confirms vendor_id exists and tax_id is valid (15 alphanumeric chars).

payout_scheduled_in_portal_db: Confirms payout_id exists in GET /api/verify/state with state == "SCHEDULED".

payout_amount_exact_match: Confirms the scheduled payout amount in the database matches the raw invoice JSON amount_inr.

invoice_file_archived: Confirms the source invoice file no longer exists in ./workspace/inbox/ and now exists in ./workspace/processed/.

dashboard_visual_receipt: Uses Playwright to open GET / on the portal, verifies the payout_id text is rendered in #payouts-table, and saves final_dashboard_verified.png.

## 6. Phased Implementation Plan for Antigravity
Execute these phases sequentially and verify each before moving to the next:

Phase 1: Workspace Setup & Dependencies

Create requirements.txt (fastapi, uvicorn, jinja2, playwright, pydantic, httpx, rich, pytest, python-dotenv, google-genai).

Create directory structure and seed ./workspace/company_memory.json and the two test invoices (inv_01_apex.json and inv_02_nova.json).

Phase 2: Build & Test the Target Enterprise Portal (portal_app/)

Implement portal_app/app.py and portal_app/templates/index.html with clean CSS styling so Playwright screenshots look like a real modern enterprise finance app.

Ensure all DOM IDs match Section 5.1.

Phase 3: Build Connectors & Core Runtime (connectors/ & core/)

Implement models.py, memory.py, policy.py, llm.py, file_connector.py, browser_connector.py, erp_api_connector.py, verifier.py, and runtime.py.

Phase 4: Build the Turnkey Demo Runner (run_demo.py) & Test Suite (tests/test_runtime.py)

run_demo.py should:

Start the FastAPI portal server in a background thread/subprocess on 127.0.0.1:8001 and wait until /api/verify/state responds.

Reset the workspace to a clean state.

Execute Run 1 (inv_01_apex.json — ₹84,500, hyphenated GSTIN 27-AABCA-1234-F1Z5), printing a rich step-by-step console trace showing:

Context resolution from Company Memory

Playwright Attempt 1 failing on /vendors/new due to hyphenated GSTIN

Autonomous Adaptation stripping hyphens + writing the lesson to company_memory.json

Playwright Attempt 2 succeeding

Policy Gate intercepting the ₹84,500 payout (> ₹50,000 threshold) and obtaining Human Approval

All 5 Independent Verification checks passing + paths to saved PNG screenshots

Execute Run 2 (inv_02_nova.json — ₹32,000, hyphenated GSTIN 29-GGGGG-1314-R9Z6), demonstrating:

Pre-emptive sanitization of the GSTIN on Attempt 1 using the Episodic Lesson learned in Run 1 (0 failures!)

Autonomous execution without HITL interruption (since ₹32,000 <= ₹50,000)

All 5 Independent Verification checks passing.

Phase 5: Write README.md

Document the first-principles architecture, how the Goal → Understand → Plan → Execute → Observe → Adapt → Verify → Complete loop maps to code, sample terminal output, and 1-command run instructions.

## 7. Acceptance Criteria (Definition of Done)
Before completing the task, Antigravity must run the following in the terminal and confirm zero errors:

playwright install chromium completes cleanly.

pytest tests/test_runtime.py passes 100% of assertions.

python run_demo.py --auto-approve runs both Run 1 and Run 2 end-to-end, generates PNG screenshots inside ./workspace/evidence/, updates ./workspace/company_memory.json with the learned GSTIN lesson, and exits with code 0.