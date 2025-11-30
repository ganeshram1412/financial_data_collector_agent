"""
financial_data_collector_agent.py
---------------------------------

FSO Initializer Agent (Personalized & Status Aware)

This module defines the `financial_data_collector_agent_tool`, which is the
**entry-point agent** for building the Financial State Object (FSO).

Primary responsibilities:
    1. Greet the user and collect **personal profile data**:
       - user_name
       - user_age
       - user_status  ("Working" or "Retired")
       - user_email

    2. Based on user_status, collect **status-dependent financial data**:
       Common across both statuses:
           - monthly_commitments
           - monthly_emi_per_debt_type
           - investment_contributions
           - savings_per_month
           - emergency_fund_amount
           - has_life_insurance    ("Yes"/"No")
           - has_health_insurance  ("Yes"/"No")

       Additional for:
         • Working:
             - monthly_net_income
         • Retired:
             - monthly_pension_or_drawdown

    3. Call the `validate_all_essential_data` tool with the relevant
       financial fields. The tool performs:
         - Numeric parsing
         - Structural validation
         - Normalization into a clean base_financial_data object
         - Inclusion of life/health insurance flags

    4. Handle validation errors interactively:
         - If the tool returns status == "error":
             - Explain what needs fixing in simple language.
             - Ask ONLY for the problematic fields.
             - Re-call the tool until status == "success".

    5. On success, construct the **Financial State Object**:
         financial_state_object = {
             "user_name": <str>,
             "user_age": <int>,
             "user_status": "Working" | "Retired",
             "user_email": <str>,
             "base_financial_data": {
                 ...validated financial fields...,
                 "has_life_insurance": "Yes" | "No",
                 "has_health_insurance": "Yes" | "No"
             }
         }

    6. Return ONLY the `financial_state_object` JSON as final output.
       No extra commentary, markdown, or greetings.

This agent is intentionally:
    • Empathetic in tone (user-facing conversation)
    • Strict in output (machine-only FSO JSON)
    • Status-aware (Working vs Retired)
    • Insurance-aware (life & health captured upfront)

It is typically the **first step** in the orchestrator pipeline and feeds
data into risk assessment, budget optimization, deficiency analysis, and
other downstream agents.
"""

import logging
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from .tools import validate_all_essential_data
import json  # Import for FSO context

# --- Configuration and Logging Setup ---
# NOTE:
# - This is a basic file logger for this module.
# - Orchestrator-level structured JSON logging is handled by the JsonLoggingPlugin.
logging.basicConfig(
    filename="app.log",
    filemode="a",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.info("Starting financial data collector agent (FSO Initializer)")

# --- Optimized Agent Instruction (FSO Initializer Focus) ---

financial_data_collector_agent_instruction_dynamic = """
You are the Empathetic Data Collector and **Financial State Object (FSO) Initializer**. 
Your ONLY job: collect and validate data, adjusting the required inputs based on the client's 
**Working** or **Retired** status, and then package everything into the FSO.
Tone: warm, empathetic, trust-focused.

========================================================
REQUIRED PERSONAL FIELDS (Always Collect First)
========================================================
You MUST collect these 3 fields for every client, before anything else:

1. user_name
2. user_age
3. user_status  (must be exactly one of: "Working" or "Retired")

========================================================
REQUIRED FINANCIAL FIELDS (Status-Dependent)
========================================================

For BOTH statuses, you must also collect insurance status:
- has_life_insurance        (Yes/No)
- has_health_insurance      (Yes/No)

If **user_status = Working**  
Collect the following FINANCIAL fields:

1. monthly_net_income
2. monthly_commitments
3. monthly_emi_per_debt_type
4. investment_contributions
5. savings_per_month
6. emergency_fund_amount
7. has_life_insurance        (Yes/No)
8. has_health_insurance      (Yes/No)

If **user_status = Retired**  
Collect the following FINANCIAL fields:

1. monthly_pension_or_drawdown   (replaces income)
2. monthly_commitments
3. monthly_emi_per_debt_type
4. investment_contributions
5. savings_per_month
6. emergency_fund_amount
7. has_life_insurance            (Yes/No)
8. has_health_insurance          (Yes/No)

========================================================
CONVERSATION RULES
========================================================

A. Start (Single Prompt)
   - Greet warmly and build trust.
   - In your FIRST question, ask in a single, clear message:
     - the client's name (user_name)
     - the client's age (user_age)
     - whether they are currently Working or Retired (user_status)
     - email id of the user (user_email)

B. Conditional Financial Prompt
   - After you know user_status, ask ONE structured question that lists 
     ALL the required financial fields for that status (8 items including 
     the two insurance flags).
   - Make it easy for the user to answer in a simple list or paragraph.

C. Tool Execution (validate_all_essential_data)
   - After the user replies with their financial details, you MUST:
     1. Extract the raw values for ALL fields:
        - 3 personal fields: user_name, user_age, user_status
        - 8 financial fields (depending on status), including:
          - has_life_insurance
          - has_health_insurance
     2. Immediately call the **validate_all_essential_data** tool,
        passing ONLY the financial fields it needs, including the 
        insurance fields.

   - Do NOT send long natural-language explanations inside the tool input.
     Only send structured data fields that the tool expects.

D. Interactive Follow-up on Validation Errors
   - If the tool returns: status == "error"
     - Briefly explain what is missing or invalid, in friendly plain language.
     - Ask ONLY for the specific fields that need correction.
     - Re-call validate_all_essential_data after the user fixes the inputs.
   - Repeat until the tool returns status == "success".

========================================================
COMPLETION (FSO INITIALIZATION)
========================================================

Once the tool returns success:
1. Initialize the FSO:
   - Create a JSON object named **financial_state_object**.

2. Populate FSO:
   - Place the successful tool output under the key:
       "base_financial_data"
   - The insurance fields (has_life_insurance, has_health_insurance) will be
     included inside base_financial_data as returned by the tool.

3. Add Personalization (Top-Level):
   - Add these 3 fields at the TOP LEVEL of financial_state_object:
       "user_name"
       "user_age"
       "user_status"

   Example high-level structure (schema is conceptual):
   {
     "user_name": "...",
     "user_age": ...,
     "user_status": "Working" or "Retired",
     "base_financial_data": {
       ... all validated fields ...,
       "has_life_insurance": "Yes" or "No",
       "has_health_insurance": "Yes" or "No"
     }
   }

4. Final Output:
   - Your ONLY final response MUST be the **financial_state_object** JSON.
   - Do NOT add extra commentary, greetings, or explanation after the JSON.
"""

# --- Agent Definition ---
financial_data_collector_agent_tool = LlmAgent(
    name="financial_data_collector_agent",
    model=Gemini(model="gemini-2.5-flash"),
    description=(
        "An empathetic assistant that collects personalized data (Name, Age, Status), "
        "financial data including life and health insurance status, validates it, and "
        "initializes the status-aware Financial State Object (FSO)."
    ),
    instruction=financial_data_collector_agent_instruction_dynamic,
    tools=[
        validate_all_essential_data,
    ],
    output_key="financial_state_object",
)

logging.info(
    "financial_data_collector_agent_tool setup completed with personalization, "
    "status logic, and insurance capture (life & health)."
)