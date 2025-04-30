# Accounting Agents – Automated Month‑End Accrual & Vendor‑Follow‑up

## Overview
This repository demonstrates a **multi‑agent workflow** built with the OpenAI Agents SDK (GPT‑4.1 LLM). It automatically:
1. Analyses historical transactions to detect regular vendor billing patterns.
2. Flags vendors that *should* have billed this month but haven’t.
3. Suggests the accrual amount per missing vendor.
4. Drafts personalised e‑mails to request the outstanding invoices.

Rather than sending entire transaction logs to the LLM, a Python preprocessing step first detects relevant transaction patterns. This filtered dataset is then passed to the agents, making the process significantly faster and more cost-efficient.

Everything is orchestrated by a top‑level **Orchestrator** agent, which chooses the right sub‑agents depending on the user’s **query** entered.

---
## Project Structure
```
AccrualAgent/
├─ Csv_files/
│   ├─ historical_transactions.csv
│   └─ current_month_transactions.csv
├─ pre_agentic_check.py        # cadence analysis + accrual tool 
├─ main.py                     # main script to run
├─ README.md                   
└─ .env                        # add OpenAI API key here
```

### Key modules
| File | Purpose |
|------|---------|
| **`pre_agentic_check.py`** | Implements `determine_current_month_accrual()` – a `@function_tool` callable by agents. It computes billing cadences, flags missing vendors and returns a Markdown table (later re‑serialised to JSON by the Accrual agent). |
| **`main.py`** | Defines three agents (Accrual calculator, Communication agent, Orchestrator) and runs the workflow.  Demonstrates dynamic tool‑calling and output‑schema enforcement with `pydantic`. |

---
## Setup
```bash
# create venv / conda env first (optional)
python -m pip install -r requirements.txt  # pandas, python‑dotenv, openai‑agents>=0.12

# add your OpenAI key to .env
OPENAI_API_KEY="sk‑…"
```
Then add your prompt to the orchestrator agent and run the script.
---
## Running
```bash
python main.py  "Calculate accruals for the current month and draft emails to vendors"
# –or–
python main.py  "Calculate just the accruals for the current month"
```
The orchestrator inspects the prompt and decides which combination of tools to invoke:
* **Accrual‑only** → calls `calculate_accrual`, returns JSON (rendered as a DataFrame in the console).
* **Accrual + Emails** → calls `calculate_accrual` *then* `draft_vendor_email`, returning a list of email strings.

---
## How it Works
1. **`Accrual_calculating_agent`**
   * Uses `determine_current_month_accrual` tool from `pre_agentic_check.py` file.
   * Adds polished 'reason' for each vendor.
   * Converts the Markdown table into a validated JSON array (`List[AccrualRow]`).
    
3. **`Communication_agent`**
   * Accepts the JSON array of regular vendors detected by the accrual agebt and writes a custom follow‑up email for each vendor.
     
4. **`Orchestration_agent`**
   * Decides which sub‑agents to call based on the natural‑language query.
   * It can call one or more agents at a time (parallel processing agent type).
   * Returns the final tool output as-is so that in future python (downstream) code can parse it reliably with pandas df.
   

---
## Extending the Workflow
* **Add new specialist agents** as `.as_tool()` wrappers
* **Switch to hand‑offs** if you later need a *single* specialist to take over the full conversation.

---
## Improvement Suggestions
1. **HTML Email Generation**  
   ‑ Update `Communication_agent` to return a JSON object with both `subject` and `html_body` keys.  
   ‑ This can then be parsed into plain text via JS and presented to user with a "Open in Gmail/Outlook" button.
2. **UI Integration**  
   ‑ In a front‑end (using Flask server and React, etc. as front end) display the current month transactions, and place a **“Get suggestions”** button at the bottom-right.  
   ‑ When clicked, sends a query to the orchestrator accordingly.
   - More functionality can be added were button clicks send different queries to orchestrator agent.
   - 
4. **Dashboard**  
   ‑ Persist results to a database and build a lightweight BI dashboard to track recurring vendors, missed invoices, and month‑end accrual totals over time.

---
