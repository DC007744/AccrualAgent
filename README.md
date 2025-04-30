# Accounting Agents – Automated Month‑End Accrual & Vendor‑Follow‑up

## Overview
This repository demonstrates a **multi‑agent workflow** built with the April‑2025 OpenAI Agents SDK (GPT‑4 series).  It automatically:
1. Analyses historical transactions to detect regular vendor billing patterns.
2. Flags vendors that *should* have billed this month but haven’t.
3. Suggests the accrual amount per missing vendor.
4. (Optionally) drafts personalised e‑mails to request the outstanding invoices.

Everything is orchestrated by a top‑level **Finance Orchestrator** agent, which chooses the right sub‑agents/tool calls depending on the user’s request.

---
## Project Structure
```
accounting_agents/
├─ Csv_files/
│   ├─ historical_transactions.csv
│   └─ current_month_transactions.csv
├─ pre_agentic_check.py        # cadence analysis + accrual tool
├─ main.py                     # entry‑point / CLI runner
├─ README.md                   # you’re here
└─ .env                        # OpenAI API key & misc settings
```

### Key modules
| File | Purpose |
|------|---------|
| **`pre_agentic_check.py`** | Implements `determine_current_month_accrual()` – a `@function_tool` callable by agents. It computes billing cadences, flags missing vendors and returns a Markdown table (later re‑serialised to JSON by the Accrual agent). |
| **`main.py`** | Defines three agents (Accrual calculator, Communication agent, Orchestrator) and runs the workflow.  Demonstrates dynamic tool‑calling and output‑schema enforcement with `pydantic`. |

---
## Setup
```bash
# create venv / conda env first (optional)
python -m pip install -r requirements.txt  # pandas, python‑dotenv, openai‑agents>=0.12

# add your OpenAI key to .env
OPENAI_API_KEY="sk‑…"
```

---
## Running
```bash
python main.py  "Calculate accruals for the current month and draft emails to vendors"
# –or–
python main.py  "Calculate just the accruals for the current month"
```
The orchestrator inspects the prompt and decides which combination of tools to invoke:
* **Accrual‑only** → calls `calculate_accrual`, returns JSON (rendered as a DataFrame in the console).
* **Accrual + Emails** → calls `calculate_accrual` *then* `draft_vendor_email`, returning a list of email strings.

---
## How it Works
1. **`Accrual_calculating_agent`**
   * Wraps `determine_current_month_accrual` (from `pre_agentic_check.py`).
   * Converts the Markdown table into a validated JSON array (`List[AccrualRow]`).
2. **`Communication_agent`**
   * Accepts the JSON array and writes a custom follow‑up email for each vendor.
3. **`Orchestration_agent`**
   * Decides which sub‑tools to run based on the natural‑language query.
   * Returns the final tool output verbatim (no extra narration) so downstream code can parse it reliably.
4. **`main.py`** captures `run.final_output` (plus the first tool result via `ToolCallOutputItem`) to build pandas DataFrames or display emails.

---
## Extending the Workflow
* **Add new specialist agents** as `.as_tool()` wrappers – e.g. a *Forecasting* agent, *Variance‑analysis* agent, etc.
* **Add guardrails** (`InputGuardrail`, `output_type`) to ensure the orchestrator routes only valid requests.
* **Switch to hand‑offs** if you later need a *single* specialist to take over the full conversation.
* **Persist outputs** to your accounting system via an additional tool that writes to your ERP/API.

---
## Improvement Suggestions
1. **HTML Email Generation**  
   ‑ Update `Communication_agent` to return a JSON object with both `subject` and `html_body` keys.  
   ‑ Use inline CSS to guarantee consistent rendering across clients.
2. **UI Integration**  
   ‑ In a front‑end (Streamlit, React, etc.) parse the JSON, display the HTML preview, and place a **“Send Email”** button next to each draft.  
   ‑ When clicked, call an email‑sending endpoint (SMTP or transactional service like SendGrid) with the generated HTML.
3. **Vendor Metadata Enrichment**  
   ‑ Extend `AccrualRow` to include `service_provided`, `contact_email`, etc.  
   ‑ Source these columns from your ERP or a vendor master data table.
4. **Scheduler / Automations**  
   ‑ Use the SDK’s `automations` tool to run the workflow automatically each month‑end and notify stakeholders via Slack or email.
5. **Dashboard**  
   ‑ Persist results to a database and build a lightweight BI dashboard to track recurring vendors, missed invoices, and month‑end accrual totals over time.

---
## License
MIT License – see `LICENSE` file.

