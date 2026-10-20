# design.md — Detailed UI/UX, Telemetry & Data Contract Specification

## 1. Design Philosophy

An autonomous AI Employee platform requires **high-trust visibility**. When an enterprise operator or founder evaluates CentrAlign, two interfaces represent the product:
1. **The Target Environment & Evidence Screenshots (`portal_app/`):** When Playwright captures full-page PNG screenshots during execution, error recovery, and verification, those screenshots must look like a clean, modern enterprise finance system (Stripe / Linear / Brex aesthetic) with clear visual hierarchy, high-contrast validation banners, and structured data tables.
2. **The Operator Telemetry Experience (`run_demo.py` CLI & `/console` Web View):** Every transition in the `GOAL → UNDERSTAND → PLAN → EXECUTE → OBSERVE → ADAPT → VERIFY → COMPLETE` loop must be immediately legible at a glance, clearly distinguishing deterministic policy gates, self-healing adaptations, and independent verification checks.

---

## 2. Visual Design System & CSS Tokens (`portal_app/templates/`)

All HTML templates in `portal_app/templates/` must use an embedded, zero-external-dependency CSS stylesheet built on the following design tokens so screenshots render deterministically offline or online:

### 2.1. Color Palette & Typography
```css
:root {
  /* Backgrounds & Surfaces */
  --bg-canvas: #F8FAFC;         /* Slate 50 */
  --bg-surface: #FFFFFF;        /* Pure White Card */
  --bg-header: #0F172A;         /* Slate 900 Navigation */
  --bg-subtle: #F1F5F9;         /* Slate 100 Table Header */

  /* Typography */
  --text-primary: #0F172A;      /* Slate 900 */
  --text-secondary: #475569;    /* Slate 600 */
  --text-muted: #94A3B8;        /* Slate 400 */
  --font-sans: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, sans-serif;
  --font-mono: "JetBrains Mono", "Fira Code", Consolas, monospace;

  /* Brand & Accents */
  --brand-primary: #2563EB;     /* Blue 600 */
  --brand-hover: #1D4ED8;       /* Blue 700 */
  --border-color: #E2E8F0;      /* Slate 200 */

  /* Semantic Status Colors (Critical for Playwright Evidence Screenshots) */
  --status-success-bg: #ECFDF5; /* Emerald 50 */
  --status-success-bd: #10B981; /* Emerald 500 */
  --status-success-tx: #065F46; /* Emerald 800 */

  --status-error-bg: #FEF2F2;   /* Red 50 */
  --status-error-bd: #EF4444;   /* Red 500 */
  --status-error-tx: #991B1B;   /* Red 800 */

  --status-warn-bg: #FFFBEB;    /* Amber 50 */
  --status-warn-bd: #F59E0B;    /* Amber 500 */
  --status-warn-tx: #92400E;    /* Amber 800 */
}

```

### 2.2. Viewport & Screenshot Geometry

- **Playwright Viewport Size:** Explicitly configure `viewport={"width": 1280, "height": 800}` in `BrowserConnector` so every captured PNG screenshot has uniform 16:10 framing.
- **Navigation Bar:** Top horizontal bar (`height: 60px`, background `--bg-header`) displaying:
  - Left: `"ACME CORP // Enterprise Finance Portal"` with an `"INTERNAL ERP v2.4"` badge.
  - Right: Navigation links for `Dashboard (/)`, `Register Vendor (/vendors/new)`, `Schedule Payout (/payouts/new)`, and `CentrAlign Console (/console)`.

## 3. Screen-by-Screen UI Specifications & DOM Contracts

### 3.1. Screen 1: Portal Dashboard (`GET /`)

Displays live organizational state in a 2-column or stacked card layout:

1. **Summary KPI Strip:**
   - Total Active Vendors (`#kpi-vendor-count`)
   - Total Scheduled Payouts (`#kpi-payout-count`)
   - Total Disbursed Volume in ₹ (`#kpi-payout-volume`)
2. **Registered Vendors Card:**
   - Table ID: `<table id="vendors-table">`
   - Columns: `Vendor ID` (monospace pill), `Legal Name`, `GSTIN / Tax ID` (monospace), `Bank Account`, `Status` (`ACTIVE` green badge).
3. **Scheduled Payouts Card:**
   - Table ID: `<table id="payouts-table">`
   - Columns: `Payout ID` (monospace pill), `Vendor ID`, `Invoice Ref`, `Amount (INR)` (formatted `₹84,500.00`), `Due Date`, `State` (`SCHEDULED` emerald badge).

### 3.2. Screen 2: Vendor Registration Form (`GET /vendors/new` & `POST /vendors/new`)

Centered card (`max-width: 560px`) titled **"Onboard New Vendor (SOP-FIN-04)"**:

- **Alert Slot (Top of Card):**
  - **On Validation Error (`ERP-422`):**

    HTML
    ```html
    <div id="error-banner" data-error-code="INVALID_TAX_ID" class="banner banner-error">
      <strong>Validation Error [ERP-422]:</strong> Field 'tax_id' must be exactly 15 alphanumeric characters without hyphens or spaces.
    </div>

    ```
  - **On Registration Success:**

    HTML
    ```html
    <div id="success-banner" data-vendor-id="{{ vendor_id }}" class="banner banner-success">
      <strong>Vendor Registered Successfully!</strong> Assigned System ID: <code>{{ vendor_id }}</code>
    </div>

    ```
- **Form Fields (`<form method="POST" action="/vendors/new">`):**
  1. `Legal Vendor Name`: `<input id="vendor-name" name="name" type="text" required value="{{ form_name }}" />`
  2. `Tax ID (15-Char Alphanumeric GSTIN)`: `<input id="vendor-tax-id" name="tax_id" type="text" required value="{{ form_tax_id }}" />`
  3. `Settlement Bank Account`: `<input id="vendor-bank" name="bank_account" type="text" required value="{{ form_bank }}" />`
  4. `Submit Button`: `<button id="submit-vendor-btn" type="submit" class="btn-primary">Register Vendor</button>`
- *Note:* When rendering `#error-banner`, keep the submitted `value` attributes populated inside the `<input>` fields so the Playwright failure screenshot visibly shows the hyphenated `27-AABCA-1234-F1Z5` inside the input box alongside the red error banner.

### 3.3. Screen 3: Schedule Payout Form (`GET /payouts/new` & `POST /payouts/new`)

Centered card (`max-width: 560px`) titled **"Schedule Vendor Invoice Payout"**:

- **Alert Slot:**
  - **On Foreign Key / Validation Error:**

    HTML
    ```html
    <div id="error-banner" data-error-code="INVALID_PAYOUT" class="banner banner-error">
      {{ error_message }}
    </div>

    ```
  - **On Success:**

    HTML
    ```html
    <div id="payout-success-banner" data-payout-id="{{ payout_id }}" class="banner banner-success">
      <strong>Payout Scheduled Successfully!</strong> Reference ID: <code>{{ payout_id }}</code>
    </div>

    ```
- **Form Fields (`<form method="POST" action="/payouts/new">`):**
  1. `ERP Vendor ID`: `<input id="payout-vendor-id" name="vendor_id" type="text" required />`
  2. `Invoice Number`: `<input id="payout-invoice-id" name="invoice_id" type="text" required />`
  3. `Payout Amount (INR)`: `<input id="payout-amount" name="amount_inr" type="number" step="0.01" required />`
  4. `Settlement Due Date`: `<input id="payout-due-date" name="due_date" type="text" required />`
  5. `Submit Button`: `<button id="submit-payout-btn" type="submit" class="btn-primary">Schedule Payout</button>`

### 3.4. Screen 4: CentrAlign Operator Console (`GET /console`)

A read-only observability view built into `portal_app/app.py` that reads `./workspace/evidence/*/report.json` and `./workspace/company_memory.json` so a human reviewer can inspect all completed runs in a browser:

- **Section A — Learned Episodic Memory Bank:** Renders a table of all self-learned rules currently stored in `company_memory.json` (`lesson_id`, `tool_name`, `error_signature`, `transformation_rule`, `explanation`).
- **Section B — Execution Run Cards (Run 1 & Run 2):**
  - Displays the 8-stage pipeline bar (`GOAL → UNDERSTAND → PLAN → EXECUTE → OBSERVE → ADAPT → VERIFY → COMPLETE`).
  - Displays the step-by-step audit trail with badges (`[MEMORY APPLIED]`, `[SELF-HEALED]`, `[HITL APPROVED]`).
  - Displays the 5 **Independent Verification Checks** with green `PASS` pills.
  - Serves and renders the captured Playwright evidence screenshots (`/evidence/<run_id>/<filename>.png`) in a visual gallery.

## 4. Terminal CLI Telemetry Design (`run_demo.py` with `rich`)

When running `python run_demo.py`, the terminal output must be structured for maximum clarity during live evaluation or video recording:

1. **Run Header Banner (`rich.panel.Panel`):**
   - Shows `Run ID`, `User Goal`, `Mode (LLM / Deterministic Fallback)`, and `Active Policies`.
2. **Real-Time Phase Stream:**
   - Each phase uses a distinct color and fixed-width badge:
     - `[UNDERSTAND]` (Cyan): Prints resolved directory aliases, loaded SOP ID, and count of prior episodic lessons loaded.
     - `[PLAN]` (Blue): Renders a compact `rich.table.Table` of the planned steps, their target tool, and their `RiskLevel` badge.
     - `[EXECUTE]` (White/Bold): Prints tool invocation and bound parameters.
     - `[OBSERVE]` (Yellow on error, Green on success): Prints DOM/API observation outcome and screenshot file path.
     - `[ADAPT]` (Magenta/Bold): Highlights self-healing parameter transformation (`"27-AABCA-1234-F1Z5" -> "27AABCA1234F1Z5"`) and confirms persistence of `EpisodicLesson` to `company_memory.json`.
     - `[POLICY GATE]` (Bright Yellow Panel): Displays a bordered box when `amount_inr (₹84,500) > max_autonomous_payout_inr (₹50,000)`, showing the checkpoint file path and awaiting/auto-confirming human approval.
     - `[VERIFY]` (Green): Renders a 5-row **Verification Evidence Matrix** (`Check Name | Target | Expected | Actual | Status`).
3. **Final Comparative Summary Table (After Run 1 & Run 2 Finish):**
   - Renders a side-by-side comparison table contrasting **Run 1** vs. **Run 2**:

| Metric                            | Run 1 (`inv_01_apex.json`)                 | Run 2 (`inv_02_nova.json`)              |
| --------------------------------- | ------------------------------------------ | --------------------------------------- |
| **Invoice Amount**                | ₹84,500.00                                 | ₹32,000.00                              |
| **Input Tax ID (Raw)**            | `27-AABCA-1234-F1Z5` (Invalid)             | `29-GGGGG-1314-R9Z6` (Invalid)          |
| **Browser Registration Attempts** | `2` (Failed Attempt 1 → Adapted)           | `1` (Pre-Sanitized via Episodic Memory) |
| **New Episodic Lesson Learned**   | `Yes (strip_hyphens_and_spaces_uppercase)` | `Reused Existing Lesson`                |
| **HITL Policy Gate Triggered**    | `Yes (> ₹50,000 limit)`                    | `No (Within ₹50,000 limit)`             |
| **Independent Verification**      | `5/5 Checks PASSED`                        | `5/5 Checks PASSED`                     |

## 5. Exact Seed Data & Schema Contracts

### 5.1. Seed Invoice 1 (`workspace/inbox/inv_01_apex.json`)

Triggers **Self-Healing Adaptation** (hyphenated GSTIN) AND **Human-in-the-Loop Approval** (`₹84,500 > ₹50,000`):

```json
{
  "invoice_id": "INV-2026-0891",
  "vendor_name": "Apex Cloud Solutions Pvt Ltd",
  "tax_id": "27-AABCA-1234-F1Z5",
  "bank_account": "HDFC0001234_9988776655",
  "amount_inr": 84500.00,
  "due_date": "2026-11-15",
  "currency": "INR",
  "description": "Enterprise GPU Cluster Hosting - Q4"
}

```

### 5.2. Seed Invoice 2 (`workspace/inbox/inv_02_nova.json`)

Proves **Episodic Memory Reuse** (hyphenated GSTIN sanitized *before* Attempt 1) AND **Autonomous Completion** (`₹32,000 <= ₹50,000`):

```json
{
  "invoice_id": "INV-2026-0942",
  "vendor_name": "Nova Data Systems LLP",
  "tax_id": "29-GGGGG-1314-R9Z6",
  "bank_account": "ICIC0005678_1122334455",
  "amount_inr": 32000.00,
  "due_date": "2026-11-20",
  "currency": "INR",
  "description": "Annual Security Audit & Penetration Testing"
}

```

### 5.3. Seed Organizational Memory (`workspace/company_memory.json`)

```json
{
  "organization_name": "Acme Corp India Pvt Ltd",
  "directory_aliases": {
    "dropbox folder": "./workspace/inbox",
    "processed archive": "./workspace/processed"
  },
  "system_endpoints": {
    "finance_portal_url": "http://127.0.0.1:8001"
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
        "6. Run independent verification checks against the portal state API, filesystem, and live dashboard DOM."
      ]
    }
  },
  "policies": {
    "max_autonomous_payout_inr": 50000.00,
    "require_human_approval_above_limit": true
  },
  "episodic_lessons": []
}

```

## 6. LLM Reasoning & Deterministic Fallback Contracts (`core/llm.py`)

`core/llm.py` exposes a `ReasoningEngine` class with two methods that work identically whether an API key (`GEMINI_API_KEY` or `OPENAI_API_KEY`) is configured or running in offline deterministic fallback mode:

### 6.1. Method 1: `generate_plan(goal: str, context: Dict[str, Any], target_invoice_file: Optional[str]) -> List[PlanStep]`

Generates the 5-step canonical execution plan:

1. `step_1_ingest_invoice` (`fs.read_next_invoice`, `READ_ONLY`)
2. `step_2_lookup_vendor` (`erp.lookup_vendor`, `READ_ONLY`)
3. `step_3_register_vendor` (`browser.register_vendor_ui`, `LOW_MUTATION`)
4. `step_4_schedule_payout` (`browser.schedule_payout_ui`, `HIGH_FINANCIAL`)
5. `step_5_archive_invoice` (`fs.archive_invoice`, `LOW_MUTATION`)

### 6.2. Method 2: `diagnose_and_adapt(step: PlanStep, resolved_params: Dict[str, Any], error_text: str) -> AdaptationDecision`

Returns a strict Pydantic model:

```python
class AdaptationDecision(BaseModel):
    recoverable: bool
    root_cause: str
    parameter_name: str
    repaired_value: Any
    transformation_rule: str
    lesson_explanation: str

```

- **Supported Transformation Rules in `CompanyMemoryStore.apply_transformation(rule, value)`:**
  - `"strip_hyphens_and_spaces_uppercase"`: `str(value).replace("-", "").replace(" ", "").strip().upper()`
  - `"trim_whitespace"`: `str(value).strip()`
  - `"uppercase"`: `str(value).upper()`
- When `diagnose_and_adapt()` is triggered by `ERP-422` / `INVALID_TAX_ID`, it returns `transformation_rule="strip_hyphens_and_spaces_uppercase"` and `repaired_value="27AABCA1234F1Z5"`, allowing both immediate retry recovery in Run 1 and automatic pre-execution sanitization in Run 2.


---
