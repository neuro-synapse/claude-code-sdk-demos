# Durable Agent Setup Guide

Complete setup guide for the Durable Research Agent with E2B sandboxes and DBOS workflows.

## Prerequisites

- Python 3.10+
- PostgreSQL 12+
- Internet connection
- API keys (Anthropic, E2B)

## Step-by-Step Setup

### 1. Clone and Install

```bash
# Navigate to research-agent directory
cd research-agent

# Install dependencies using uv
uv sync
```

This installs:
- `claude-agent-sdk` - Claude Agent SDK
- `dbos` - DBOS durable workflow library
- `e2b-code-interpreter` - E2B sandbox SDK
- `psycopg2-binary` - PostgreSQL adapter

### 2. Get API Keys

#### Anthropic API Key

1. Visit https://console.anthropic.com/settings/keys
2. Create a new API key
3. Copy the key (starts with `sk-ant-`)

#### E2B API Key

1. Visit https://e2b.dev/dashboard
2. Sign up or log in
3. Create a new API key
4. Copy the key (starts with `e2b_`)

### 3. Setup PostgreSQL

Choose one of the following options:

#### Option A: Local PostgreSQL

```bash
# Install PostgreSQL (if not already installed)
# macOS:
brew install postgresql@15
brew services start postgresql@15

# Ubuntu/Debian:
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql

# Create database
createdb research_agent

# Set DATABASE_URL
export DATABASE_URL=postgresql://$(whoami)@localhost:5432/research_agent
```

#### Option B: Docker PostgreSQL

```bash
# Run PostgreSQL in Docker
docker run -d \
  --name postgres-research \
  -e POSTGRES_DB=research_agent \
  -e POSTGRES_USER=dbos \
  -e POSTGRES_PASSWORD=dbos \
  -p 5432:5432 \
  postgres:15

# Verify it's running
docker ps | grep postgres-research

# Set DATABASE_URL
export DATABASE_URL=postgresql://dbos:dbos@localhost:5432/research_agent
```

#### Option C: Cloud PostgreSQL

Use any cloud provider (AWS RDS, Google Cloud SQL, Azure Database, etc.)

```bash
# Example for a cloud database
export DATABASE_URL=postgresql://user:password@your-host.rds.amazonaws.com:5432/research_agent
```

### 4. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your keys
nano .env  # or vim, code, etc.
```

Your `.env` should look like:

```bash
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here
E2B_API_KEY=e2b_your-actual-key-here
DATABASE_URL=postgresql://user:password@localhost:5432/research_agent
```

### 5. Initialize DBOS

```bash
# DBOS will auto-initialize tables on first run
# Test the connection:
psql $DATABASE_URL -c "SELECT version();"
```

Expected output:
```
                                     version
------------------------------------------------------------------------------------
 PostgreSQL 15.x on ...
(1 row)
```

### 6. Verify Setup

Run the setup verification script:

```bash
# Create a test script
cat > test_setup.py << 'EOF'
import os
from dotenv import load_dotenv

load_dotenv()

# Check environment variables
checks = {
    "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
    "E2B_API_KEY": os.getenv("E2B_API_KEY"),
    "DATABASE_URL": os.getenv("DATABASE_URL")
}

print("Setup Verification")
print("=" * 50)

all_good = True
for var, value in checks.items():
    status = "✓" if value else "✗"
    display = "SET" if value else "NOT SET"
    print(f"{status} {var}: {display}")
    if not value:
        all_good = False

print("=" * 50)

if all_good:
    print("✓ All environment variables configured!")
    print("\nNext steps:")
    print("  1. Run: uv run research-agent-durable")
    print("  2. Try: 'Research Apple, Microsoft, Google'")
else:
    print("✗ Missing environment variables")
    print("  Edit .env file and add missing keys")
EOF

# Run verification
uv run python test_setup.py

# Clean up
rm test_setup.py
```

### 7. Run the Agent

```bash
uv run research-agent-durable
```

You should see:

```
✓ Environment configured
✓ DBOS initialized (durable execution enabled)

🔬 DURABLE RESEARCH AGENT (E2B + DBOS)
================================================================================

Features:
  ✓ Durable workflows (recovers from any failure)
  ✓ Isolated sandboxes (each sub-agent in E2B sandbox)
  ✓ Parallel execution (all agents run simultaneously)
  ✓ Comprehensive logging (track everything)

You:
```

## Testing

### Test 1: Basic Research

```
You: Research Python, JavaScript

🚀 Starting wide research for 2 items...
📁 Logs: logs/session_20250118_143022

[WORKFLOW START] wide_research
...
```

### Test 2: Failure Recovery

```bash
# Terminal 1: Start research
You: Research Apple, Microsoft, Google, Amazon, Tesla

# Let it start processing...
# Then kill it (Ctrl+C) after the first item completes

# Restart the agent
uv run research-agent-durable

# Enter the same query
You: Research Apple, Microsoft, Google, Amazon, Tesla

# DBOS will:
# ✓ Skip Apple (already completed)
# → Continue with Microsoft, Google, Amazon, Tesla
```

### Test 3: Sandbox Isolation

```bash
# Run the example script
uv run python examples/durable_demo.py

# Choose option 3 (Sandbox Isolation)
# This demonstrates that each agent has its own environment
```

## Troubleshooting

### Problem: "E2B API Key not found"

**Solution:**
```bash
# Check .env file
cat .env | grep E2B_API_KEY

# Should show: E2B_API_KEY=e2b_...
# If not, add it to .env
```

### Problem: "Could not connect to PostgreSQL"

**Solution:**
```bash
# Test connection
psql $DATABASE_URL -c "SELECT 1;"

# If fails, check:
# 1. PostgreSQL is running: pg_isready
# 2. DATABASE_URL is correct
# 3. User has permissions
```

### Problem: "DBOS initialization failed"

**Solution:**
```bash
# Check PostgreSQL version (needs 12+)
psql $DATABASE_URL -c "SELECT version();"

# Check database exists
psql -l | grep research_agent

# If not, create it
createdb research_agent
```

### Problem: "Sandbox creation failed"

**Solution:**
```bash
# Check E2B API key
curl -H "Authorization: Bearer $E2B_API_KEY" https://api.e2b.dev/health

# Check internet connection
ping e2b.dev

# Check E2B status
open https://status.e2b.dev
```

### Problem: "Module not found"

**Solution:**
```bash
# Reinstall dependencies
uv sync --force

# Verify installation
uv run python -c "import dbos; import e2b_code_interpreter; print('OK')"
```

## Configuration

### DBOS Configuration

Edit `dbos-config.yaml` to customize:

- Workflow timeout
- Retry behavior
- Logging level
- Worker threads

Example:

```yaml
workflows:
  maxExecutionTime: 7200  # 2 hours instead of 1
  maxRetries: 5           # 5 retries instead of 3

logging:
  level: debug  # More verbose logging
```

### E2B Configuration

E2B sandboxes are configured in code:

```python
# In e2b_manager.py, customize sandbox creation:
sandbox = Sandbox.create(
    timeout=600,  # 10 minutes
    # Add more configuration as needed
)
```

### Logging Configuration

Edit logging settings in `utils/logging_config.py`:

```python
# Change console log level
setup_logging(console_level=logging.DEBUG)

# Change file log level
setup_logging(file_level=logging.INFO)
```

## Next Steps

1. **Try Examples**: Run `examples/durable_demo.py`
2. **Read Docs**: See [DURABLE_AGENT.md](DURABLE_AGENT.md)
3. **Customize**: Modify agent prompts in `prompts/`
4. **Monitor**: Check logs in `logs/session_*/`

## Support

- **E2B Issues**: https://github.com/e2b-dev/E2B/issues
- **DBOS Issues**: https://github.com/dbos-inc/dbos-transact-py/issues
- **Agent Issues**: Create an issue in this repository

## Quick Reference

```bash
# Start agent
uv run research-agent-durable

# Run examples
uv run python examples/durable_demo.py

# Check logs
tail -f logs/session_*/agent.log

# Check workflow log
tail -f logs/session_*/workflow.log

# Check errors
tail -f logs/session_*/errors.log

# Clean up old logs
rm -rf logs/session_*

# Reset database (CAUTION: deletes all workflow state)
psql $DATABASE_URL -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```
