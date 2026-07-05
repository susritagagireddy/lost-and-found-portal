# 🔍 Lost & Found Portal

An automated, secure, and intelligent lost and found matching system powered by ADK 2.0 multi-agent workflows, a local MCP database server, and custom security checkpoints.

## Prerequisites

- **Python 3.11+**
- **uv** (Python package manager)
- **Gemini API Key** from [Google AI Studio](https://aistudio.google.com/apikey)

## Quick Start

```bash
git clone <repo-url>
cd lost-and-found-portal
cp .env.example .env   # add your GOOGLE_API_KEY
make install
make playground        # opens UI at http://localhost:18081
```

## Architecture

Here is the system architecture showing the flow of user queries through the security checkpoints, orchestrator, sub-agents, and MCP server.

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

## How to Run

- **Interactive Playground Mode**:
  ```bash
  make playground
  ```
  This launches the ADK Web Dev UI at [http://localhost:18081](http://localhost:18081).
  
- **Local Server Mode**:
  ```bash
  make run
  ```
  Runs the local FastAPI server at `http://127.0.0.1:8000`.

## Sample Test Cases

### Test Case 1: Report a Found Item
- **Input**: `Hi, I found a black leather wallet on the bus today. My email is finder@example.com`
- **Expected**: The request is scanned by the security checkpoint (safe, clean), routed to the `reporter_agent`, which calls the `report_item` tool.
- **Check**: The playground UI displays: `Item reported successfully! Assigned ID: <id>. Match searches will run automatically.`

### Test Case 2: Report a Lost Item & Match
- **Input**: `Hi, I lost my wallet. It's a black leather wallet, and I think I left it on the bus. My email is owner@example.com`
- **Expected**: The request is routed to the `matcher_agent`, which searches the database, finds the match from Test Case 1, calls `initiate_claim`, and pauses for human verification.
- **Check**: The UI displays: `System Alert: A claim is being made for item <id>. Please confirm by typing 'YES' to verify this claim or 'NO' to cancel.`

### Test Case 3: Verify the Claim
- **Input**: `YES`
- **Expected**: The workflow resumes, transitions to verification success, marks the item as claimed, and finishes.
- **Check**: The UI displays: `Verification Success: Claim for item <id> has been verified and processed.`

## Troubleshooting

1. **Error: 'uv' is not installed or not on PATH**
   - **Fix**: Prepend `$HOME\.local\bin` to your `PATH` or install `uv` following instructions in `GETTING_STARTED.md`.
2. **Error: 404 Model Not Found**
   - **Fix**: Double check that `GEMINI_MODEL=gemini-2.5-flash` is defined in `.env` (older `gemini-1.5-*` models are retired).
3. **Changes in agent.py not appearing (Windows)**
   - **Fix**: Uvicorn reloading does not hot-reload processes spawning subprocesses on Windows. Run:
     ```powershell
     Get-Process -Id (Get-NetTCPConnection -LocalPort 18081, 8090 -ErrorAction SilentlyContinue).OwningProcess | Stop-Process -Force
     ```
     and relaunch `make playground`.

## Push to GitHub

1. Create a new repo at https://github.com/new
   - Name: lost-and-found-portal
   - Visibility: Public or Private
   - Do NOT initialize with README (you already have one)

2. In your terminal, navigate into your project folder:
   ```bash
   cd lost-and-found-portal
   git init
   git add .
   git commit -m "Initial commit: lost-and-found-portal ADK agent"
   git branch -M main
   git remote add origin https://github.com/susritagagireddy/lost-and-found-portal.git
   git push -u origin main
   ```

3. Verify .gitignore includes:
   ```
   .env          ← your API key — must NEVER be pushed
   .venv/
   __pycache__/
   *.pyc
   .adk/
   ```

⚠ NEVER push .env to GitHub. Your API key will be exposed publicly.
