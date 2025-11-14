# Claude Code SDK Demos - Architecture & Development Guide

This document provides a comprehensive guide to the Claude Agent SDK demo repository, covering architecture patterns, technology stack, development conventions, and best practices across all demo agents.

## Repository Overview

This repository contains 6 demo applications showcasing different approaches to building AI-powered applications with the Claude Agent SDK:

| Demo | Language | Purpose | Key Features |
|------|----------|---------|--------------|
| **hello-world** | TypeScript | Getting started | Basic SDK usage, hooks, file operations |
| **sms-agent** | TypeScript + Bun | SMS response automation | Server with webhooks, SQLite database |
| **sms-agent-python** | Python + FastAPI | Python equivalent SMS | Multi-agent patterns, async processing |
| **email-agent** | TypeScript + React | Email management UI | Complex async, IMAP integration, WebSockets |
| **excel-demo** | Electron + Python | Spreadsheet automation | Desktop app, Excel skill, openpyxl |
| **research-agent** | Python | Multi-agent coordination | Subagent tracking, document processing skills |

---

## Technology Stack

### Runtime Environments

- **Node.js / Bun**: TypeScript demos use Bun (faster, native TypeScript) or Node.js
- **Python**: Python demos use Python 3.10+ with `uv` package manager
- **Electron**: Desktop application (excel-demo)

### Core Dependencies

#### TypeScript Projects
```json
{
  "@anthropic-ai/claude-agent-sdk": "^0.1.28",  // or claude-code
  "zod": "^4.1.12",                              // Validation
  "dotenv": "^17.2.1",                           // Environment config
  "typescript": "^5.9.3",
  "@types/node": "^24.7.2"
}
```

#### Python Projects
```toml
[dependencies]
claude-agent-sdk >= 0.1.0      # Main SDK
python-dotenv >= 1.0.0          # Environment config
fastapi >= 0.104.0              # (sms-agent-python)
uvicorn >= 0.24.0               # (sms-agent-python)
```

### Additional Frameworks

- **React**: For UI (email-agent, excel-demo renderer)
- **TailwindCSS**: Styling (email-agent)
- **SQLite**: Local data persistence (sms-agent, email-agent)
- **node-imap**: Email protocol client (email-agent)
- **mailparser**: Email parsing (email-agent)
- **openpyxl**: Excel file manipulation (excel-demo agents)
- **FastAPI**: Python web framework (sms-agent-python)

---

## Project Structure Patterns

### Directory Organization

Every demo follows a consistent structure:

```
demo-name/
├── .claude/                    # SDK configuration directory
│   ├── agents/                # Agent definitions (YAML/Markdown)
│   │   └── agent-name.md     # Agent instructions & tools
│   └── skills/               # Custom skills/tools
│       └── skill-name/
│           ├── SKILL.md      # Skill documentation
│           └── scripts/      # Implementation files
├── agent/                     # Agent code
│   ├── index.ts / agent.py   # Main agent entry point
│   └── custom_scripts/       # Agent-writable directory
├── server/                    # Optional: Web server
│   ├── index.ts / api.py     # Server implementation
│   └── endpoints/            # Route handlers
├── database/                  # Optional: Data persistence
│   ├── db.ts / db.py        # Database client
│   └── schema/               # Table definitions
├── client/                    # Optional: Frontend (React)
├── .env.example              # Configuration template
├── package.json / pyproject.toml
├── tsconfig.json / uv.lock
├── CLAUDE.md                 # Agent-specific instructions
└── README.md                 # Project-specific setup
```

### Configuration Hierarchy

1. **`.env` files** (root level)
   - `ANTHROPIC_API_KEY` - Required API credential
   - Service-specific config (IMAP, SMS provider, etc.)
   - Loaded via `dotenv.load()`

2. **`.claude/` directory** (agent working directory)
   - Agent definitions: `agents/*.md` with instructions and tools
   - Skills: `skills/*/SKILL.md` with capability documentation
   - **Note**: `.claude` is git-ignored except in research-agent (skills needed)

3. **`CLAUDE.md` files** (agent-level instructions)
   - `agent/CLAUDE.md` - Instructions for Claude when running as this agent
   - Specifies available tools, preferences, restrictions
   - Example: "Only write scripts to custom_scripts/"

---

## SDK Architecture

### Core Concepts

#### 1. Query Objects (TypeScript)

```typescript
const q = query({
  prompt: 'Your instruction here',
  options: {
    maxTurns: 100,
    cwd: '/path/to/working/dir',      // Must exist
    model: 'opus' | 'sonnet' | 'haiku', // Default: haiku
    executable: 'node',                 // Runtime binary
    allowedTools: ['Read', 'Write', ...],
    appendSystemPrompt: 'Additional instructions',
    hooks: {
      PreToolUse: [...],
      PostToolUse: [...]
    }
  }
});

for await (const message of q) {
  // Process message types: 'system', 'assistant', 'result'
}
```

#### 2. Client-Based (Python)

```python
async with ClaudeSDKClient(options=options) as client:
  await client.query(prompt=user_input)
  async for msg in client.receive_response():
    # Process message
```

#### 3. Agent Definitions (Python Multi-Agent)

```python
agents = {
  "researcher": AgentDefinition(
    description="Purpose of this subagent...",
    tools=["WebSearch", "Write"],
    prompt=researcher_prompt,
    model="haiku"
  )
}

options = ClaudeAgentOptions(
  agents=agents,
  allowed_tools=["Task"],  # Lead agent uses Task to spawn subagents
  hooks={...}
)
```

### Available Tools

**File Operations**: `Read`, `Write`, `Edit`, `MultiEdit`, `NotebookEdit`, `Glob`, `Grep`

**Execution**: `Bash`, `Task` (spawn subagent), `BashOutput`, `KillBash`

**Web**: `WebSearch`, `WebFetch`

**Utilities**: `TodoWrite`, `ExitPlanMode`, `Skill` (invoke .claude/skills)

**Custom**: Via hooks and `.claude/agents/` definitions

### Message Types

```typescript
// System: Framework messages
message.type === 'system'

// Assistant: Claude's responses
message.type === 'assistant'
message.message.content // TextBlock[]

// Result: Tool execution results
message.type === 'result'
message.result.content // Tool output
```

---

## Hooks System

Hooks intercept tool execution before (`PreToolUse`) and after (`PostToolUse`) invocation.

### PreToolUse Hook (Validation/Blocking)

```typescript
hooks: {
  PreToolUse: [{
    matcher: "Write|Edit|MultiEdit",  // Tool name regex
    hooks: [
      async (input: any): Promise<HookJSONOutput> => {
        // input.tool_name, input.tool_input
        
        // Allow execution
        return { continue: true };
        
        // Block execution
        return {
          decision: 'block',
          stopReason: 'Reason for blocking',
          continue: false
        };
      }
    ]
  }]
}
```

### Common Hook Patterns

1. **File Path Restrictions** (hello-world)
   - Enforce scripts only in `custom_scripts/`
   - Validate file extensions

2. **Tracking & Logging** (research-agent)
   - Log all tool calls to transcript
   - Record tool inputs/outputs in JSONL format
   - Track subagent hierarchies

3. **Permission Management**
   - Check `permission_mode: "bypassPermissions"`
   - Filter based on tool type or parameters

### Python Hooks

```python
hooks = {
  'PreToolUse': [
    HookMatcher(
      matcher=None,  # None = match all tools
      hooks=[tracker.pre_tool_use_hook]
    )
  ],
  'PostToolUse': [
    HookMatcher(matcher=None, hooks=[tracker.post_tool_use_hook])
  ]
}
```

---

## Multi-Agent Patterns

### Research Agent Pattern

The research-agent demonstrates a sophisticated multi-agent architecture:

#### Architecture

```
┌─────────────────────────────────────┐
│        Lead Agent                   │
│ (Spawns & coordinates subagents)    │
│ Tools: Task only                    │
└───────────┬───────────────────────┬─┘
            │                       │
    ┌───────▼──────┐         ┌──────▼────────┐
    │ Researchers  │         │ Report-Writer │
    │ (in parallel)│         │ (synthesizes) │
    │ Tools: WebSearch,      │ Tools: Read,  │
    │        Write           │        Glob,  │
    │                        │        Write  │
    └───────┬──────┘         └───────┬──────┘
            │                        │
            └─────────┬──────────────┘
                      │
              ┌───────▼──────┐
              │ Shared Files │
              │ research_    │
              │  notes/      │
              │ reports/     │
              └──────────────┘
```

#### Key Files

- `research_agent/agent.py` - Lead agent initialization
- `research_agent/agent_wide.py` - Variant for list comparison
- `research_agent/prompts/` - System prompts for each agent type
- `research_agent/utils/subagent_tracker.py` - Hook-based tracking
- `research_agent/utils/transcript.py` - Session logging

#### Subagent Tracking

Hooks extract `parent_tool_use_id` from each tool call to link calls to their spawning subagent:

```python
# When lead agent calls Task tool → returns task_123
# Researcher's tool calls include parent_tool_use_id = task_123
# PreToolUse hook maps this to RESEARCHER-1

# Output: logs/session_YYYYMMDD_HHMMSS/
# - transcript.txt: Human-readable conversation
# - tool_calls.jsonl: Structured JSON event log
```

### Two Modes

1. **Traditional Mode** (agent.py)
   - Decomposes single topic into 2-4 subtopics
   - One researcher per subtopic
   - Integrated final report

2. **Wide Research Mode** (agent_wide.py)
   - Analyzes lists of items (companies, products, papers)
   - One researcher per item
   - Equal quality guarantee
   - Prevents "fabrication threshold" bias

---

## Server Patterns

### Web Server Integration

#### TypeScript/Bun (sms-agent)

```typescript
const server = Bun.serve({
  port: 3001,
  async fetch(req) {
    // Handle webhook endpoints
    // Integrate with SMS agent for processing
  }
});
```

#### Python/FastAPI (sms-agent-python)

```python
from fastapi import FastAPI

app = FastAPI()

@app.post("/webhook/sms")
async def handle_sms(sms: IncomingSMS):
  # Process with SDK agent
  response = await agent.generateResponse(context)
  return {"status": "ok"}
```

### Database Integration

#### TypeScript (SQLite)

```typescript
const db = new Database('sms-agent.db');

// Schema definition
db.run(`
  CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY,
    phone_number TEXT UNIQUE,
    name TEXT,
    relationship TEXT,
    trust_level INTEGER
  )
`);

// Usage
const contact = db.query(
  "SELECT * FROM contacts WHERE phone_number = ?"
).get(phoneNumber);
```

#### Python (SQLite)

```python
class SMSDatabase:
  def __init__(self, db_path='sms.db'):
    self.conn = sqlite3.connect(db_path)
    self.setup_schema()
  
  def setup_schema(self):
    self.conn.execute("""
      CREATE TABLE IF NOT EXISTS messages (...)
    """)
```

---

## Skills System

### What are Skills?

Skills are specialized tools/capabilities defined in `.claude/skills/` that extend the SDK's built-in tools.

### Skills in This Repository

#### Research Agent Skills

Located in `research-agent/.claude/skills/`:

1. **xlsx** - Excel spreadsheet creation/manipulation
   - SKILL.md: Documentation
   - recalc.py: LibreOffice formula calculation
   - Supports: Creating with formulas, data analysis, conditional formatting

2. **docx** - Word document generation
   - SKILL.md: Capabilities
   - docx-js.md: Implementation details
   - ooxml.md: OpenXML format reference

3. **pdf** - PDF manipulation
   - SKILL.md: Tool documentation
   - Forms and form-filling capabilities
   - reference.md: API reference

4. **pptx** - PowerPoint presentations
   - SKILL.md: Presentation creation
   - html2pptx.md: HTML to slides conversion
   - ooxml.md: Format specification

#### Excel Demo Skills

`excel-demo/agent/.claude/skills/xlsx/`:
- Accessed via `Skill` tool with command "xlsx"
- Used in Python agents for spreadsheet operations
- Includes recalc.py for formula evaluation

### Using Skills

#### From Agent Code

```typescript
// TypeScript - invoke via hooks/tools
allowedTools: ["Skill"]
```

```python
# Python - invoke via Skill tool
tools=["Skill", "Read", "Write"]
```

#### In CLAUDE.md Instructions

```markdown
You have access to the `xlsx` skill via the Skill tool.
Use the Skill tool with command "xlsx" for spreadsheet operations.
```

---

## Common Development Patterns

### 1. Configuration Management

```typescript
// .env.example shows expected variables
// Load with dotenv in each demo

import "dotenv/config";

const apiKey = process.env.ANTHROPIC_API_KEY;
const port = process.env.PORT ?? 3001;
```

### 2. Agent Initialization

**TypeScript Pattern:**
```typescript
const q = query({
  prompt: systemPrompt,
  options: {
    cwd: path.join(__dirname, 'agent'),
    allowedTools: ['Read', 'Write', 'Bash'],
    hooks: { /* validation */ }
  }
});
```

**Python Pattern:**
```python
options = ClaudeAgentOptions(
  system_prompt=prompt,
  allowed_tools=['WebSearch', 'Write'],
  agents={'researcher': AgentDefinition(...)}
)

async with ClaudeSDKClient(options=options) as client:
  await client.query(prompt=user_input)
```

### 3. Streaming Response Handling

```typescript
for await (const message of q) {
  if (message.type === 'assistant') {
    const text = message.message.content
      .find(c => c.type === 'text')?.text;
    console.log(text);
  }
}
```

```python
async for msg in client.receive_response():
  if type(msg).__name__ == 'AssistantMessage':
    for block in msg.content:
      if hasattr(block, 'text'):
        print(block.text)
```

### 4. File Writing Restrictions

**Pattern from hello-world:**

```typescript
// Hook validates file paths before Write tool executes
const ext = path.extname(filePath).toLowerCase();
if (ext === '.js' || ext === '.ts') {
  if (!filePath.startsWith(allowedDir)) {
    return {
      decision: 'block',
      stopReason: 'Scripts must be in custom_scripts/',
      continue: false
    };
  }
}
```

### 5. Subagent Tracking

**Pattern from research-agent:**

```python
class SubagentTracker:
  def register_subagent_spawn(self, tool_use_id, subagent_type):
    # Create unique ID like "RESEARCHER-1"
    subagent_id = f"{subagent_type.upper()}-{counter}"
    self.sessions[tool_use_id] = SubagentSession(...)
  
  async def pre_tool_use_hook(self, input: dict):
    # Log tool invocation with subagent context
    tool_name = input['tool_name']
    agent_id = self._lookup_agent(input['parent_tool_use_id'])
    self.transcript_writer.write(f"[{agent_id}] → {tool_name}")
```

---

## Testing & Validation

### TypeScript Configuration (tsconfig.json)

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true
  }
}
```

### Python Configuration (pyproject.toml)

```toml
[project]
name = "demo-name"
requires-python = ">=3.10"

[tool.black]
line-length = 88

[tool.ruff]
line-length = 88
```

### Testing Patterns

- **hello-world**: No tests (simple example)
- **email-agent**: Jest configuration (unit/integration tests)
- **research-agent**: Manual integration testing
- **sms-agent-python**: pytest patterns for async code

---

## Best Practices

### 1. Working Directory Organization

```
agent/                          # Agent's working directory
├── .claude/                    # Configuration (git-tracked)
│   ├── agents/
│   └── skills/
├── custom_scripts/             # Agent-writable area
├── data/                       # Persistent data
└── logs/                       # Generated logs
```

### 2. Error Handling

```typescript
// Always wrap agent execution
try {
  for await (const message of q) {
    // Process message
  }
} catch (error) {
  console.error('Agent error:', error);
}
```

```python
# Validate API key before creating files
if not os.environ.get("ANTHROPIC_API_KEY"):
  print("Error: ANTHROPIC_API_KEY required")
  return
```

### 3. Logging & Debugging

- Use **transcript files** for user-facing output
- Use **JSONL logs** for structured data analysis
- Include **timestamps** for all events
- Track **parent_tool_use_id** for request tracing

### 4. Security Considerations

⚠️ **Important**: These are demos for LOCAL development only

- Credentials stored in `.env` (not git-tracked)
- No authentication (local only)
- No validation of webhook signatures
- Should NOT be deployed to production

### 5. Scalability Patterns

- **Horizontal**: Use Task tool to spawn parallel subagents
- **Vertical**: Increase `maxTurns` for complex tasks
- **Caching**: Leverage shared file system for data exchange
- **Monitoring**: Use hooks to track all operations

---

## Agent-Specific CLAUDE.md Files

Each agent that runs as a Claude Code subprocess should have its own `agent/CLAUDE.md`:

```markdown
# [Agent Name] Instructions

You are a [specialized] agent. Your responsibilities:

## Tools Available
- Tool1: Description
- Tool2: Description

## Restrictions
- Cannot write to X
- Must use Y for Z operations

## Best Practices
- Always validate inputs
- Prefer X over Y
```

**Examples:**
- `email-agent/agent/CLAUDE.MD` - Email agent constraints
- `excel-demo/agent/CLAUDE.MD` - Excel skill usage
- `research-agent/prompts/` - System prompts for different agent types

---

## Running Demos

### TypeScript Demos

```bash
cd demo-name
npm install  # or bun install
export ANTHROPIC_API_KEY="your-key"
npm run dev  # or bun run
```

### Python Demos

```bash
cd demo-name
uv sync  # Install dependencies
export ANTHROPIC_API_KEY="your-key"
uv run agent.py  # or main.py
```

### Desktop Demo

```bash
cd excel-demo
npm install
npm start  # Launches Electron app
```

---

## Key Files Reference

| Path | Purpose |
|------|---------|
| `README.md` | Repository overview |
| `*/README.md` | Demo-specific setup |
| `*/CLAUDE.md` | Agent instructions |
| `*/.env.example` | Configuration template |
| `*/package.json` / `pyproject.toml` | Dependencies |
| `*/.claude/agents/*.md` | Subagent definitions |
| `*/.claude/skills/*/SKILL.md` | Skill documentation |
| `*/prompts/` | Agent system prompts |
| `*/server/` | Web server (if applicable) |
| `*/database/` | Data persistence (if applicable) |

---

## Additional Resources

- [Claude Agent SDK Documentation](https://docs.anthropic.com/en/docs/claude-code/sdk/sdk-overview)
- [API Reference](https://docs.anthropic.com/claude)
- [Bun Runtime](https://bun.sh)
- [Python uv Package Manager](https://github.com/astral-sh/uv)

---

## Summary: Architecture Decision Matrix

| Scenario | Recommended Pattern | Example |
|----------|-------------------|---------|
| Simple scripting | `query()` with hooks | hello-world |
| Webhook integration | Server + Agent | sms-agent |
| Complex research | Multi-agent with Task | research-agent |
| Web UI needed | React + WebSocket | email-agent |
| Desktop app | Electron + Python agents | excel-demo |
| Single-language | Use native bindings | sms-agent-python |

