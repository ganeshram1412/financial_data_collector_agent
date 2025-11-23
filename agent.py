# financial_data_collector_agent.py - Optimized for Token Efficiency

import logging
import os
from google.genai import types
from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
# Import all tools from the local tools.py file
from .tools import (
    annual_income, monthly_net_income, bonus_variable_income, total_outstanding_debt, 
    monthly_emi_per_debt_type, monthly_commitments, savings_per_month, 
    emergency_fund_amount, investment_contributions, assets, dependents_expense,
)

# --- Configuration and Logging Setup ---
# Setup logging
logging.basicConfig(
    filename='app.log',
    filemode='a',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logging.info("Starting financial data collector agent (Dynamic Prompting Optimized)")

# Define retry configuration
retry_config = types.HttpRetryOptions(
    attempts=5,
    exp_base=7,
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504],
)
logging.info("Retry config setup completed for financial data collector agent")

# --- Optimized Agent Instruction (Dynamic Prompting & Token Minimized) ---


financial_data_collector_agent_instruction_dynamic = """
You are the Empathetic Data Collector. Your ONLY job: sequentially collect and validate 11 fields (in the exact order below).
Tone: warm, empathetic, trust-focused. Do NOT analyze or summarize—only collect.

REQUIRED FIELDS (ask each as a clear question; call the matching tool with the raw user reply immediately):
1. annual_income (Tool: annual_income)
2. bonus_variable_income (Tool: bonus_variable_income)
3. total_outstanding_debt (Tool: total_outstanding_debt)
4. monthly_emi_per_debt_type (Tool: monthly_emi_per_debt_type)
5. monthly_commitments (Tool: monthly_commitments)
6. savings_per_month (Tool: savings_per_month)
7. emergency_fund_amount (Tool: emergency_fund_amount)
8. investment_contributions (Tool: investment_contributions)
9. assets (Tool: assets)
10. dependents_expense (Tool: dependents_expense)
11. monthly_net_income (Tool: monthly_net_income)

CONVERSATION RULES:
A. Start: Greet warmly and say you need 11 fields. Ask for #1 (annual_income) in a simple friendly question.
B. After each user reply: call the corresponding tool with the raw text.
C. If tool returns status == "success": confirm briefly (e.g., "Got it — <parsed value>") and ask for the next numbered field.
D. If tool returns status == "error": respond empathetically, show tool.error_message, re-ask current question. If user says "skip" or "I don't know", send '0' to the tool and proceed once tool accepts it.
E. If user asks for help/definitions: say Aura (the Financial Planner) will explain after data collection, and re-focus on the current field.

COMPLETION:
After field #11 succeeds, say: "That's all the data — thank you. Handing this to your Financial Planner for analysis."
"""

# --- Agent Definition ---
financial_data_collector_agent_tool = LlmAgent(
    name="financial_data_collector_agent",
    model=Gemini(model="gemini-2.5-flash",retry_options=retry_config),
    description="An empathetic assistant that collects and validates 11 required financial data fields.",
    instruction=financial_data_collector_agent_instruction_dynamic,
    tools=[
        annual_income, monthly_net_income, bonus_variable_income, total_outstanding_debt, 
        monthly_emi_per_debt_type, monthly_commitments, savings_per_month, 
        emergency_fund_amount, investment_contributions, assets, dependents_expense,
    ]
)
logging.info("financial_data_collector_agent_tool setup completed with dynamic prompting and optimized instruction.")