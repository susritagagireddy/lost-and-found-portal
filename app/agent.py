# ruff: noqa
import re
import json
import sys
from typing import Any
from google.adk.agents import Agent
from google.adk.workflow import Workflow, node, START
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.agents.context import Context
from google.adk.tools import AgentTool, ToolContext, request_input, McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from google.adk.apps import App
from google.genai import types
from app.config import config

# --- MCP Toolset Setup ---

mcp_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp_server"]
        )
    )
)

# --- Tools ---

def initiate_claim(item_id: str, tool_context: ToolContext) -> dict:
    """Initiates the claim process for a specific matched item.

    Args:
        item_id: The unique ID of the item being claimed.
    """
    tool_context.state["claim_pending"] = True
    tool_context.state["pending_claim_item_id"] = item_id
    return {
        "status": "success",
        "message": f"Claim process initiated for item {item_id}. Human verification is now required."
    }

# --- Agents ---

reporter_agent = Agent(
    name="reporter_agent",
    model=config.model,
    instruction="""You are the Lost & Found Reporter. 
    Your goal is to gather structured details of a lost or found item from the user.
    Politely ask for:
    1. Item Category (e.g., Electronics, Keys, Wallet, Clothing, Documents, etc.)
    2. Description of the item (color, brand, size, distinguishing features)
    3. Location (where it was lost or found)
    4. Date (when it was lost or found)
    5. Contact email
    
    Ensure you capture all these fields clearly. Once you have collected them, use the `report_item` tool from the MCP toolset to save it to the database.
    """,
    description="Assists with reporting a lost or found item.",
    tools=[mcp_toolset]
)

matcher_agent = Agent(
    name="matcher_agent",
    model=config.model,
    instruction="""You are the Lost & Found Matcher. 
    Your goal is to search for matching items in the database and handle claims.
    Use the `search_items` tool from the MCP toolset to search for matching reported items.
    Explain to the user the matches you found.
    If the user identifies their item from the matches and wants to claim it, call the `initiate_claim` tool with the item's ID.
    """,
    description="Assists with searching matching items or claiming a found item.",
    tools=[mcp_toolset, initiate_claim]
)

orchestrator_agent = Agent(
    name="orchestrator_agent",
    model=config.model,
    instruction="""You are the Lost & Found Coordinator. 
    Your job is to route user requests to the correct specialist sub-agent using your tools:
    - If the user wants to report a lost or found item, delegate to reporter_agent.
    - If the user wants to search for, match, or claim an item, delegate to matcher_agent.
    - Otherwise, help answer general questions about the lost and found process.
    """,
    tools=[AgentTool(reporter_agent), AgentTool(matcher_agent)]
)

# --- Workflow Nodes ---

def security_checkpoint(ctx: Context, node_input: types.Content) -> Event:
    """Scrubber and prompt injection detector node."""
    text = ""
    if hasattr(node_input, "parts") and node_input.parts:
        text = "".join(part.text for part in node_input.parts if part.text)
    
    # 1. Prompt Injection keyword detection
    injection_keywords = ["ignore previous instructions", "system prompt", "developer instructions", "override rules"]
    is_injection = any(kw in text.lower() for kw in injection_keywords)
    
    # Structured audit logging
    audit_log = {
        "event": "security_checkpoint_scan",
        "session_id": ctx.session.id,
        "input_length": len(text),
        "injection_detected": is_injection,
        "severity": "CRITICAL" if is_injection else "INFO"
    }
    print(f"AUDIT_LOG: {json.dumps(audit_log)}")
    
    if is_injection:
        return Event(
            output="Security check failed: Input blocked due to policy violations.",
            route="SECURITY_EVENT"
        )
    
    # 2. Domain-Specific Rule: Prohibited Items check (weapons, illegal substances)
    prohibited_keywords = ["gun", "weapon", "firearm", "drugs", "cocaine", "marijuana", "explosive", "hazardous"]
    has_prohibited = any(kw in text.lower() for kw in prohibited_keywords)
    
    if has_prohibited:
        prohibited_log = {
            "event": "prohibited_item_flagged",
            "session_id": ctx.session.id,
            "severity": "WARNING",
            "message": "Attempt to report or search for prohibited items."
        }
        print(f"AUDIT_LOG: {json.dumps(prohibited_log)}")
        return Event(
            output="Security check failed: Reporting or searching for weapons, drugs, or hazardous materials is prohibited on this portal.",
            route="SECURITY_EVENT"
        )
    
    # 3. PII scrubbing (Scrub Credit Cards and SSNs)
    cc_regex = r"\b(?:\d[ -]*?){13,16}\b"
    ssn_regex = r"\b\d{3}-\d{2}-\d{4}\b"
    
    cleaned_text = re.sub(cc_regex, "[REDACTED_CARD]", text)
    cleaned_text = re.sub(ssn_regex, "[REDACTED_SSN]", cleaned_text)
    
    if cleaned_text != text:
        scrub_log = {
            "event": "pii_redacted",
            "session_id": ctx.session.id,
            "severity": "WARNING"
        }
        print(f"AUDIT_LOG: {json.dumps(scrub_log)}")
        
    return Event(output=cleaned_text, route="SAFE_ROUTE")



def handle_security_violation(node_input: str):
    """Outputs the security warning to user."""
    yield Event(content=types.Content(role='model', parts=[types.Part.from_text(text=node_input)]))
    yield Event(output=node_input)


# We wrap orchestrator agent as a node in workflow
orchestrator_node = orchestrator_agent


async def claim_verification(ctx: Context, node_input: Any) -> Event:
    """Human-in-the-loop verification node for item claims."""
    # Check if a claim has been initiated by the matcher agent
    if ctx.state.get("claim_pending", False):
        if not ctx.resume_inputs or "confirm_claim" not in ctx.resume_inputs:
            item_id = ctx.state.get("pending_claim_item_id", "Unknown")
            yield RequestInput(
                interrupt_id="confirm_claim",
                message=f"System Alert: A claim is being made for item {item_id}. Please confirm by typing 'YES' to verify this claim or 'NO' to cancel."
            )
            return
        
        # We resumed! Parse response
        user_choice = ctx.resume_inputs["confirm_claim"].strip().upper()
        item_id = ctx.state.get("pending_claim_item_id", "Unknown")
        
        # Reset claim state
        ctx.state["claim_pending"] = False
        
        if user_choice == "YES":
            result = f"Verification Success: Claim for item {item_id} has been verified and processed."
            yield Event(content=types.Content(role='model', parts=[types.Part.from_text(text=result)]))
            yield Event(output=result, state={"claim_status": "verified"})
        else:
            result = "Verification Denied: Claim process was cancelled by the user."
            yield Event(content=types.Content(role='model', parts=[types.Part.from_text(text=result)]))
            yield Event(output=result, state={"claim_status": "cancelled"})
    else:
        # Standard flow, pass orchestrator's response straight through without duplicate content event
        text_response = ""
        if isinstance(node_input, types.Content):
            if node_input.parts:
                text_response = "".join(part.text for part in node_input.parts if part.text)
        elif isinstance(node_input, str):
            text_response = node_input
            
        yield Event(output=text_response)
        return


# --- Workflow Graph Definition ---

root_agent = Workflow(
    name="lost_and_found_workflow",
    edges=[
        (START, security_checkpoint),
        (security_checkpoint, {"SECURITY_EVENT": handle_security_violation, "SAFE_ROUTE": orchestrator_node}),
        (orchestrator_node, claim_verification)
    ]
)

app = App(
    root_agent=root_agent,
    name="app",
)
