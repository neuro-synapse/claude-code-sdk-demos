# Durable Research Agent with E2B Sandboxes

**Production-ready research agent with fault tolerance and isolated execution.**

## Overview

The Durable Research Agent extends the wide research architecture with two critical capabilities:

1. **E2B Sandboxes**: Each sub-agent runs in complete isolation
2. **DBOS Workflows**: All research is durable and recovers from any failure

### Key Benefits

✓ **Fault Tolerance**: Workflows recover from crashes, network failures, or interruptions
✓ **Isolation**: Each agent in its own Firecracker microVM (~150ms startup)
✓ **No Lost Work**: DBOS ensures once-and-only-once execution
✓ **Complete Logs**: Comprehensive logging for debugging and auditing
✓ **Parallel Execution**: All sub-agents run simultaneously in isolated sandboxes

## Architecture

```
User Request
    ↓
[Lead Agent] - Orchestrates workflow
    ↓
[DBOS Workflow Layer] - Wraps everything for durability
    ↓
[E2B Sandbox Manager] - Creates isolated sandboxes
    ↓
[Sub-Agent 1]     [Sub-Agent 2]     [Sub-Agent N]
(Sandbox 1)       (Sandbox 2)       (Sandbox N)
    ↓                 ↓                 ↓
  Research         Research          Research
    ↓                 ↓                 ↓
[Aggregation] - Combine results
    ↓
Final Report
```

### Component Architecture

```
research_agent/
├── agent_durable.py          # Main entry point
├── sandbox/
│   ├── e2b_manager.py        # E2B sandbox management
│   └── agent_executor.py     # Execute agents in sandboxes
├── durable/
│   └── workflow.py           # DBOS workflow definitions
└── utils/
    └── logging_config.py     # Comprehensive logging
```

## Setup

### 1. Install Dependencies

```bash
# Install all dependencies including E2B and DBOS
uv sync
```

### 2. Environment Variables

Create a `.env` file with the following:

```bash
# Required: Anthropic API key
ANTHROPIC_API_KEY=sk-ant-...

# Required: E2B API key (get at https://e2b.dev/dashboard)
E2B_API_KEY=e2b_...

# Required: PostgreSQL for DBOS
DATABASE_URL=postgresql://user:password@localhost:5432/research_agent
```

### 3. Setup PostgreSQL

DBOS requires PostgreSQL to store workflow state:

```bash
# Option 1: Local PostgreSQL
createdb research_agent

# Option 2: Docker
docker run -d \
  --name postgres-dbos \
  -e POSTGRES_DB=research_agent \
  -e POSTGRES_USER=dbos \
  -e POSTGRES_PASSWORD=dbos \
  -p 5432:5432 \
  postgres:15

# Then set DATABASE_URL
export DATABASE_URL=postgresql://dbos:dbos@localhost:5432/research_agent
```

### 4. Run the Agent

```bash
uv run research-agent-durable
```

## Usage

### Wide Research Mode

Research multiple items with equal quality guarantee:

```
You: Research Apple, Microsoft, Google, Amazon

🚀 Starting wide research for 4 items...
📁 Logs: logs/session_20250118_143022

[WORKFLOW START] wide_research
  items: ['Apple', 'Microsoft', 'Google', 'Amazon']

[RESEARCHER-1] Creating sandbox for Apple...
[RESEARCHER-2] Creating sandbox for Microsoft...
[RESEARCHER-3] Creating sandbox for Google...
[RESEARCHER-4] Creating sandbox for Amazon...

✓ All sandboxes created (avg 150ms)
✓ Research complete!
  Successful: 4/4
  Output files: 4
```

### Single Topic Research

Deep dive into one topic with subtopic decomposition:

```
You: Research quantum computing

🚀 Starting research on: quantum computing
📁 Logs: logs/session_20250118_143045

[WORKFLOW START] single_research
  topic: quantum computing
  subtopics: 3

✓ Research complete!
  Subtopics: 3
  Successful: 3/3
```

## How It Works

### E2B Sandboxes

Each sub-agent runs in an **isolated E2B sandbox**:

```python
# Create isolated sandbox for each agent
sandbox = sandbox_manager.create_sandbox(
    agent_type="researcher",
    agent_id="RESEARCHER-1"
)

# Execute code in complete isolation
result = sandbox.run_code(research_code)

# Each sandbox has:
# - Own file system
# - Independent internet connection
# - Fresh Python environment
# - Full tool library
```

**Benefits:**
- No context pollution between agents
- Safe code execution
- Parallel execution without interference
- Fresh context window for each agent

### DBOS Durable Workflows

All research is wrapped in **DBOS workflows**:

```python
@DBOS.workflow()
def run_wide_research(items: List[str]):
    """Entire workflow is durable."""

    results = []
    for item in items:
        # Each step is idempotent
        result = self.execute_research_task(item)  # @DBOS.step()
        results.append(result)

    # Aggregation is also a step
    return self.aggregate_results(results)  # @DBOS.step()
```

**How Recovery Works:**

1. DBOS records each step completion in Postgres
2. If workflow crashes/interrupts, DBOS knows which steps completed
3. On restart, completed steps return recorded outputs (no re-execution)
4. Only incomplete steps are executed
5. Workflow continues to completion

**Example Recovery:**

```
[Initial Run]
✓ STEP: Research Apple (completed)
✓ STEP: Research Microsoft (completed)
✗ CRASH (network failure)

[Automatic Recovery]
→ STEP: Research Apple (skipped - already completed)
→ STEP: Research Microsoft (skipped - already completed)
✓ STEP: Research Google (executing)
✓ STEP: Research Amazon (executing)
✓ WORKFLOW COMPLETE
```

## Logging

Comprehensive logging across all components:

```
logs/session_20250118_143022/
├── agent.log          # All debug logs
├── errors.log         # Error-only log
├── workflow.log       # DBOS workflow steps
├── sandbox.log        # E2B sandbox operations
└── transcript.txt     # Human-readable session
```

### Log Levels

- **Console**: INFO and above (colored)
- **agent.log**: DEBUG and above (everything)
- **errors.log**: ERROR and above
- **workflow.log**: Workflow steps only
- **sandbox.log**: Sandbox operations only

### Example Logs

```
[workflow.log]
2025-01-18 14:30:22 | WORKFLOW START: wide_research
2025-01-18 14:30:22 |   items: ['Apple', 'Microsoft', 'Google']
2025-01-18 14:30:23 | ✓ STEP: execute_research_task [SUCCESS]
2025-01-18 14:30:24 | ✓ STEP: execute_research_task [SUCCESS]

[sandbox.log]
2025-01-18 14:30:22 | INFO | research_agent.sandbox | [RESEARCHER-1] CREATE
2025-01-18 14:30:22 | DEBUG | research_agent.sandbox |   sandbox_id: sbx_abc123
2025-01-18 14:30:23 | INFO | research_agent.sandbox | [RESEARCHER-1] EXECUTE
```

## Design Principles

### KISS (Keep It Simple, Stupid)

- Simple, focused classes with single responsibilities
- No complex inheritance hierarchies
- Clear, readable code over clever tricks

**Example:**
```python
# Simple manager with clear operations
class E2BSandboxManager:
    def create_sandbox(self, agent_type, agent_id) -> Sandbox
    def execute_code(self, agent_id, code) -> Dict
    def close_sandbox(self, agent_id)
```

### DRY (Don't Repeat Yourself)

- Centralized logging configuration
- Reusable sandbox operations
- Shared workflow patterns

**Example:**
```python
# Centralized logging setup
setup_logging(session_dir)  # Used everywhere
log_workflow_start(name, params)  # Consistent format
log_workflow_step(step, status, details)
```

### YAGNI (You Aren't Gonna Need It)

- Only implement what's needed now
- No speculative features
- No premature optimization

**Example:**
- No caching layer (not needed yet)
- No distributed execution (sandboxes handle parallelism)
- No custom workflow DSL (DBOS decorators sufficient)

## Error Handling

### Automatic Recovery

DBOS handles most failures automatically:

```python
# If this fails halfway through:
@DBOS.workflow()
def run_wide_research(items):
    for item in items:
        result = self.execute_research_task(item)  # May fail

# On restart, DBOS:
# 1. Checks which tasks completed
# 2. Returns recorded results for completed tasks
# 3. Only executes incomplete tasks
# 4. Continues to completion
```

### Manual Recovery

Check workflow status:

```python
from research_agent.durable import check_workflow_status

status = check_workflow_status(workflow_id)
# Returns: {
#   "workflow_id": "...",
#   "status": "running" | "completed" | "failed",
#   "completed_steps": [...],
#   "pending_steps": [...]
# }
```

### Sandbox Failures

If a sandbox fails, it's automatically recreated:

```python
try:
    result = execute_in_sandbox(agent_id, code)
except SandboxError:
    # Close failed sandbox
    sandbox_manager.close_sandbox(agent_id)

    # Create new sandbox
    sandbox_manager.create_sandbox(agent_type, agent_id)

    # Retry (DBOS ensures idempotency)
    result = execute_in_sandbox(agent_id, code)
```

## Performance

### E2B Sandboxes

- **Startup**: ~150ms per sandbox
- **Parallel Creation**: All sandboxes created simultaneously
- **Execution**: No overhead (native Firecracker performance)

### DBOS Workflows

- **Overhead**: Minimal (just Postgres writes)
- **Recovery**: Instant (reads from Postgres)
- **Scalability**: Postgres-limited (thousands of workflows)

### Example Timings

```
Wide research for 10 items:
- Sandbox creation: 150ms (parallel)
- Research per item: 30-60s (depends on search)
- Aggregation: 5-10s
- Total: ~1-2 minutes

Recovery after failure:
- Resume time: <1s (read from Postgres)
- Only incomplete work re-executed
```

## Troubleshooting

### E2B API Key Issues

```
Error: E2B_API_KEY not found

Solution:
1. Get API key at https://e2b.dev/dashboard
2. Add to .env: E2B_API_KEY=e2b_...
3. Restart agent
```

### PostgreSQL Connection Issues

```
Error: Could not connect to PostgreSQL

Solution:
1. Check PostgreSQL is running: pg_isready
2. Verify DATABASE_URL in .env
3. Test connection: psql $DATABASE_URL
```

### Sandbox Creation Failures

```
Error: Failed to create sandbox

Solutions:
1. Check E2B API key is valid
2. Check internet connection
3. Check E2B status: https://status.e2b.dev
4. Review sandbox.log for details
```

## FAQ

**Q: What happens if my computer crashes during research?**
A: DBOS automatically recovers. Restart the agent and it continues from the last completed step.

**Q: Can I run multiple workflows simultaneously?**
A: Yes! Each workflow is independent. DBOS handles concurrent workflows.

**Q: How much does E2B cost?**
A: E2B has a free tier. Check https://e2b.dev/pricing for details.

**Q: What if I don't have PostgreSQL?**
A: The agent will run without DBOS (no durability), but sandboxes still work.

**Q: Can I customize the sandboxes?**
A: Yes! Modify `setup_agent_environment()` in `agent_executor.py`.

**Q: How do I resume a failed workflow?**
A: DBOS does this automatically. Just restart the agent.

## Next Steps

1. **Try it**: Run a simple wide research query
2. **Monitor logs**: Check the session directory
3. **Test recovery**: Kill the process mid-research and restart
4. **Customize**: Add your own agent types or tools

## References

- [E2B Documentation](https://e2b.dev/docs)
- [DBOS Documentation](https://docs.dbos.dev)
- [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk)
