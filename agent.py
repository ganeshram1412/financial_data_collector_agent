# financial_data_collector_agent.py - FSO Initializer Agent (Personalized & Status Aware)

import logging
import os
from google.genai import types
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from .tools import validate_all_essential_data 
import json # Import for FSO context

# --- Configuration and Logging Setup ---
# (Standard logging configuration)
logging.basicConfig(
    filename='app.log',
    filemode='a',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logging.info("Starting financial data collector agent (FSO Initializer)")

# Define retry configuration
retry_config = types.HttpRetryOptions(
    attempts=5,
    exp_base=7,
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504],
)

# --- Optimized Agent Instruction (FSO Initializer Focus) ---

financial_data_collector_agent_instruction_dynamic = """
You are the Empathetic Data Collector and **Financial State Object (FSO) Initializer**. Your ONLY job: collect and validate data, adjusting the required inputs based on the client's **Working** or **Retired** status, and then package everything into the FSO.
Tone: warm, empathetic, trust-focused.

**REQUIRED PERSONAL FIELDS (Always Collect First):**
1. user_name
2. user_age
3. user_status (Working or Retired)

**REQUIRED FINANCIAL FIELDS (Vary by Status):**
If **Working**: monthly_net_income, monthly_commitments, monthly_emi_per_debt_type, investment_contributions, savings_per_month, emergency_fund_amount.
If **Retired**: **monthly_pension_or_drawdown** (Replaces income), monthly_commitments, monthly_emi_per_debt_type, investment_contributions, savings_per_month, emergency_fund_amount.

CONVERSATION RULES:
A. **Start (Single Prompt):** Greet warmly. **First, ask for the client's name, age, and whether they are currently working or retired.**
B. **Conditional Prompt:** Based on the **user_status**, present the appropriate list of 6 financial fields in a single, structured question.
C. **Tool Execution:** After the user replies, **extract the raw values for ALL fields (3 personal + 6 financial)** and pass the 6 financial fields immediately to the **`validate_all_essential_data`** tool. 

D. **Interactive Follow-up:** If the tool returns status == "error", follow the original error handling rules.

COMPLETION (FSO INITIALIZATION):
Once the tool returns success:
1. **Initialize the FSO:** Create a JSON object named 'financial_state_object'.
2. **Populate FSO:** Place the successful tool output under the key **'base_financial_data'**.
3. **Add Personalization:** Add the **user_name, user_age, and user_status** directly to the FSO's top level.
4. **Output:** Your **ONLY** response must be the final 'financial_state_object' JSON.
"""

# --- Agent Definition ---
financial_data_collector_agent_tool = LlmAgent(
    name="financial_data_collector_agent",
    model=Gemini(model="gemini-2.5-flash",retry_options=retry_config),
    description="An empathetic assistant that collects personalized data (Name, Age, Status) and financial data, validates it, and initializes the status-aware Financial State Object (FSO).",
    instruction=financial_data_collector_agent_instruction_dynamic,
    tools=[
        validate_all_essential_data,
    ],
    output_key="financial_state_object"
)
logging.info("financial_data_collector_agent_tool setup completed with personalization and status logic.")