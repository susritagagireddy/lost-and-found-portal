# Submission Write-Up — Lost & Found Portal

This document outlines the design decisions, architectural elements, and security considerations implemented in the Lost & Found Portal.

## Problem Statement
Traditional lost and found registries are manual, slow, and hard to query. Users must read long lists of items or communicate with staff to check matches. The **Lost & Found Portal** automates this by providing:
1. An conversational agent to take item details.
2. Automating description-matching between lost and found entries.
3. An approval verification workflow (Human-in-the-Loop) to prevent unauthorized claims.
4. Security protections to scrub PII and prevent prompt injections.

## Solution Architecture
The diagram below details the multi-agent graph flow of the portal.

```mermaid
graph TD
    START[User Input] --> SC[Security Checkpoint]
    SC -->|SECURITY_EVENT| SV[Handle Security Violation]
    SC -->|SAFE_ROUTE| ORCH[Orchestrator Agent]
    
    ORCH -->|AgentTool| RA[Reporter Agent]
    ORCH -->|AgentTool| MA[Matcher Agent]
    
    RA -->|report_item| MCP[(MCP Server database)]
    MA -->|search_items / claim_item| MCP
    
    MA -->|initiate_claim| HITL[Claim Verification Node (HITL)]
    
    HITL --> final[Final Output]
    SV --> final
```

## Concepts Used

- **ADK Workflow**: Configured in [agent.py](file:///c:/Users/subha/OneDrive/Documents/capstone%20project/lost-and-found-portal/app/agent.py#L187-L197). Coordinates routing between the security scan, orchestrator, and claim verification steps.
- **LlmAgent**: Used for `orchestrator_agent`, `reporter_agent`, and `matcher_agent` in [agent.py](file:///c:/Users/subha/OneDrive/Documents/capstone%20project/lost-and-found-portal/app/agent.py#L31-L70).
- **AgentTool**: Used by `orchestrator_agent` to delegate to sub-agents.
- **MCP Server**: Defined in [mcp_server.py](file:///c:/Users/subha/OneDrive/Documents/capstone%20project/lost-and-found-portal/app/mcp_server.py). Operates as a local database engine with three tools.
- **Security Checkpoint**: The workflow function node `security_checkpoint` in [agent.py](file:///c:/Users/subha/OneDrive/Documents/capstone%20project/lost-and-found-portal/app/agent.py#L90-L131) checks for malicious prompts and scrubs sensitive PII.
- **Agents CLI**: Project scaffolded using `google-agents-cli scaffold create`.

## Security Design

1. **PII Scrubbing**: Cleans input strings using regex to remove credit cards and SSNs before passing them to agents.
2. **Prompt Injection Detection**: Blocks prompt overrides or instructions-extraction phrases, routing violations to a safety terminal.
3. **Domain-Specific Check**: Blocks search and reporting of dangerous/illegal categories (weapons, drugs) and logs audit events.
4. **Structured JSON Audit Logs**: Decisions are logged to standard output using structured JSON objects showing event metadata, severity level, and flags for quick parsing by security teams.

## MCP Server Design
The server runs via stdio using `FastMCP` and manages a local JSON registry database:
- `report_item`: Stores metadata for reported items (ID, category, location, date, contact details).
- `search_items`: Executes keyword queries to match descriptions or categories.
- `claim_item`: Updates the status of matched items to `claimed`.

## HITL Flow (Human-in-the-Loop)
Claiming an item is a sensitive process. When a user requests a claim, the system initiates a pause via `RequestInput` in the `claim_verification` node. This pauses execution and prompts the user to explicitly confirm with `YES` or `NO`, validating user intent before modifying the database.

## Demo Walkthrough
Refer to the 3 sample test cases in the [README.md](file:///c:/Users/subha/OneDrive/Documents/capstone%20project/lost-and-found-portal/README.md#L45-L66) to test item registration, description matching, and claim verification in the playground UI.

## Impact & Value Statement
This portal cuts down administrative overhead for organizations (offices, schools, public transport) by handling intake and matching automatically, while ensuring users are secure and database access is managed through strict validation.
