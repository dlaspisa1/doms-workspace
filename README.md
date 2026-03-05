# Googipet Work Space

AI-powered workspace using a 3-layer architecture for reliable automation.

## Architecture

This workspace follows a 3-layer design that separates concerns:

**Layer 1: Directives** (`directives/`)
- SOPs written in Markdown
- Define goals, inputs, tools, outputs, and edge cases
- Natural language instructions for the orchestration layer

**Layer 2: Orchestration** (AI Agent)
- Intelligent routing and decision-making
- Reads directives, calls execution tools, handles errors
- Updates directives with learnings

**Layer 3: Execution** (`execution/`)
- Deterministic Python scripts
- Handles API calls, data processing, file operations
- Reliable, testable, fast

## Directory Structure

```
.
├── directives/          # Markdown SOPs (what to do)
├── execution/           # Python scripts (how to do it)
│   └── webhooks.json   # Webhook configuration
├── .tmp/               # Intermediate files (never commit)
├── .env                # Environment variables (never commit)
├── .env.example        # Template for environment variables
└── CLAUDE.md           # System instructions
```

## Setup

1. **Install dependencies** (when scripts are added):
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables**:
   - Copy `.env.example` to `.env`
   - Add your API keys and tokens

3. **Set up Google OAuth** (if needed):
   - Place `credentials.json` in root directory
   - Run authentication flow to generate `token.json`

## Operating Principles

1. **Check for tools first** - Before writing a script, check `execution/` for existing tools
2. **Self-anneal when things break** - Fix errors, update scripts, improve directives
3. **Update directives as you learn** - Directives are living documents

## File Organization

- **Deliverables**: Cloud-based (Google Sheets, Slides, etc.)
- **Intermediates**: Local `.tmp/` directory (can be deleted and regenerated)

## Webhooks (Modal)

Webhooks are configured in `execution/webhooks.json` and map to directives.

**Endpoints:**
- List webhooks: `https://nick-90891--claude-orchestrator-list-webhooks.modal.run`
- Execute directive: `https://nick-90891--claude-orchestrator-directive.modal.run?slug={slug}`
- Test email: `https://nick-90891--claude-orchestrator-test-email.modal.run`

**Available tools:** `send_email`, `read_sheet`, `update_sheet`

## Getting Started

1. Create a directive in `directives/` describing what you want to accomplish
2. Create or use existing execution scripts in `execution/`
3. Let the AI orchestration layer handle the routing and error management

Read [CLAUDE.md](CLAUDE.md) for complete system instructions.
