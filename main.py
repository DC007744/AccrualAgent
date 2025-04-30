"""
About:
This script uses OpenAI's Agents SDK (with the latest gpt-4.1 LLM) to create agentic workflows for financial analysis.
Given a user query, it decides which agents to call, orchestrates their interactions, and returns the final output (see sections 4 & 5).
"""

# -------------------------------------------------------
# Section 1: Import the necessary libraries
# -------------------------------------------------------
import asyncio
import io
from typing import Any, List

import pandas as pd
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from agents import Agent, Runner
from agents.items import ToolCallOutputItem        # for introspecting tool results
from pre_agentic_check import determine_current_month_accrual

# -------------------------------------------------------
# Section 2: Load environment variables
# -------------------------------------------------------
load_dotenv()

# -------------------------------------------------------
# Section 3: Defining the agents
# -------------------------------------------------------

# ---------- 3-A · shared Pydantic schema ----------
class AccrualRow(BaseModel):
    vendor_id: str
    suggested_accrual: float
    reason: str | None = None          # rewritten for accountants


# ---------- 3-B · Accrual-calculating agent ----------
Accrual_calculating_agent = Agent(
    name="Current month accrual calculator",
    tools=[determine_current_month_accrual],
    model="gpt-4.1",
    instructions="""
        You are a financial-analysis assistant.  When asked for suggested accruals:
        1. Call determine_current_month_accrual.
        2. Return **only** a JSON array that follows the AccrualRow schema
           (rewrite the “reason” text so accountants can understand it).
        Do **not** add commentary, Markdown, or bullets.
    """,
    output_type=List[AccrualRow],      # SDK validates JSON
)


# ---------- 3-C · Communication (e-mail) agent ----------
Communication_agent = Agent(
    name="Vendor payment follow-up agent",
    model="gpt-4.1",
    instructions="""
        You will receive a JSON array of accrual rows.  Write a personalised
        follow-up e-mail for *each* vendor explaining the missing invoice and
        quoting the suggested accrual amount.
        Return a Python **list[str]** – one e-mail per list element.  Do not wrap
        the list in extra text.
    """,
    output_type=List[str],
)


# ---------- 3-D · Orchestration agent ----------
Orchestration_agent = Agent(
    name="Finance Orchestrator",
    model="gpt-4.1",
    instructions="""
        You are the top-level orchestrator.  Decide which tools to call based on
        the user's request.

        • If the user only wants accrual calculations, call **calculate_accrual**
          and return that tool's JSON result directly.

        • If the user wants both accrual calculations *and* e-mails, first call
          **calculate_accrual**, store the JSON as `accruals`, then call
          **draft_vendor_email** with `accruals` as the argument, and finally
          return the list of e-mails.

        • If the user only wants e-mails and supplies accrual JSON, call
          **draft_vendor_email** with that JSON.

        • For future functionality, choose whichever tools (or sequences of
          tools) are needed; always return only the last tool's output with no
          extra narration.
    """,
    tools=[
        Accrual_calculating_agent.as_tool(
            tool_name="calculate_accrual",
            tool_description="Suggest accruals for missing vendor invoices",
        ),
        Communication_agent.as_tool(
            tool_name="draft_vendor_email",
            tool_description="Compose follow-up e-mails to vendors",
        ),
    ],
)

# -------------------------------------------------------
# Section 4: Defining main function to call Orchestrator
# -------------------------------------------------------
async def call_orchestrator(query: str):

    print("\n\n---- User Query ----")
    print(query)

    print("\n---- Running Orchestrator ----")
    run = await Runner.run(starting_agent=Orchestration_agent, input=query)

    final: Any = run.final_output

    # ---- 4-A Flexible post-processing / logging ----
    if isinstance(final, list) and final and isinstance(final[0], str):
        # looks like a list of e-mails
        print("\n---- Generated E-mails ----")
        for i, mail in enumerate(final, 1):
            print(f"\nEmail #{i}\n{'-'*30}\n{mail}")

    elif isinstance(final, list):
        # likely a list[dict] → accrual JSON
        print("\n---- Accruals JSON ----")
        print(final)

        try:
            df = pd.DataFrame(final)
            print("\n---- Accrual DataFrame ----")
            print(df.head())
        except Exception as e:
            print(f"(Could not convert to DataFrame: {e})")

    else:
        print("\n---- Raw Output ----")
        print(final)

    # ---- 4-B Optional: always keep the first accrual JSON for later use ----
    accrual_json = None
    for item in run.new_items:
        if (
            isinstance(item, ToolCallOutputItem)
            and item.agent is Accrual_calculating_agent
        ):
            accrual_json = item.output
            break

    if accrual_json:
        df = pd.read_json(io.StringIO(accrual_json))
        print("\n(Accrual DataFrame extracted from first tool call)")
        print(df.head())


# -------------------------------------------------------
# Section 5: Run the orchestrator
# -------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(
        call_orchestrator(
            "Calculate accruals for the current month and draft emails to vendors"
            #"Calculate just the accruals for the current month"
        )
    )