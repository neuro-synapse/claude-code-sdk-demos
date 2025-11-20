# Pepper with Claude Agent SDK, Kafka, and DBOS

## Design Overview

This design reimagines Pepper using:
- **Claude Agent Python SDK** (native agent framework)
- **Kafka** (distributed event streaming)
- **DBOS** (durable execution and state management)

Following principles: **KISS** (Keep It Simple), **DRY** (Don't Repeat Yourself), **YAGNI** (You Aren't Gonna Need It)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Event Sources                           │
│  (Gmail, User Messages, Reminders, External APIs)               │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Kafka Topics                               │
│  • pepper.events.email        (email events)                    │
│  • pepper.events.user         (user messages)                   │
│  • pepper.events.reminder     (reminder triggers)               │
│  • pepper.tasks.assigned      (tasks for workers)               │
│  • pepper.tasks.results       (task results)                    │
│  • pepper.ui.messages         (messages to UI)                  │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DBOS Workflow Engine                         │
│  • Durable execution (survives restarts)                        │
│  • Automatic retries and recovery                               │
│  • State persistence                                            │
└────────────┬────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Claude Agent SDK Agents                        │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │ SchedulerAgent   │  │  WorkerAgent     │                     │
│  │ (Orchestrator)   │  │  (Task Executor) │                     │
│  │                  │  │                  │                     │
│  │ - Routes events  │  │ - Executes tasks │                     │
│  │ - Assigns tasks  │  │ - Uses tools     │                     │
│  │ - Coordinates    │  │ - Returns results│                     │
│  └──────────────────┘  └──────────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                         PostgreSQL                              │
│  (DBOS State Store + Application Data)                          │
│  • Workflow state                                               │
│  • Conversation history                                         │
│  • User profiles                                                │
│  • Task assignments                                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Event Producers (KISS)
Simple Kafka producers for each event source:
- **EmailProducer**: Monitors Gmail, publishes to `pepper.events.email`
- **UserMessageProducer**: Web UI input, publishes to `pepper.events.user`
- **ReminderProducer**: Timer-based, publishes to `pepper.events.reminder`

### 2. SchedulerAgent (Claude Agent SDK + DBOS)
**Purpose**: Orchestrate incoming events and delegate tasks

**Implementation**:
```python
from anthropic import Claude
from dbos import DBOS, workflow

class SchedulerAgent:
    def __init__(self):
        self.client = Claude(api_key=os.getenv("ANTHROPIC_API_KEY"))

    @workflow()
    async def process_event(self, event_type: str, event_data: dict):
        """DBOS durable workflow - survives crashes"""
        # Step 1: Retrieve context (DBOS handles retries)
        context = await self.get_context(event_type, event_data)

        # Step 2: Call Claude Agent SDK
        response = await self.decide_action(context)

        # Step 3: Publish tasks to Kafka (idempotent)
        if response.tasks:
            await self.publish_tasks(response.tasks)

        # Step 4: Send UI message if needed
        if response.user_message:
            await self.send_to_ui(response.user_message)

        return response
```

**Key Features**:
- DBOS workflow = automatic retries, crash recovery
- Claude Agent SDK = native tool calling, streaming
- Kafka = distributed task assignment

### 3. WorkerAgent (Claude Agent SDK + DBOS)
**Purpose**: Execute assigned tasks with tools

**Implementation**:
```python
class WorkerAgent:
    def __init__(self):
        self.client = Claude(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.tools = self.load_tools()  # MCP tools

    @workflow()
    async def execute_task(self, task: dict):
        """DBOS durable task execution"""
        # Step 1: Initialize agent state
        state = await self.init_state(task)

        # Step 2: Execute with Claude Agent SDK
        result = await self.run_agent_loop(state)

        # Step 3: Publish result to Kafka
        await self.publish_result(task['id'], result)

        return result

    async def run_agent_loop(self, state):
        """Claude Agent SDK loop with tool calling"""
        max_steps = 10
        for step in range(max_steps):
            response = await self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                messages=state.messages,
                tools=self.tools,
                max_tokens=8000
            )

            if response.stop_reason == "end_turn":
                return response.content

            # Execute tools
            tool_results = await self.execute_tools(response.tool_calls)
            state.add_tool_results(tool_results)
```

### 4. Kafka Integration (DRY)
**Reusable Kafka utilities**:

```python
# kafka_utils.py - DRY principle
class KafkaClient:
    """Shared Kafka client for all components"""
    def __init__(self):
        self.producer = KafkaProducer(
            bootstrap_servers=os.getenv('KAFKA_BROKERS'),
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

    async def publish(self, topic: str, key: str, value: dict):
        """Publish with idempotency key"""
        self.producer.send(topic, key=key.encode(), value=value)

    def subscribe(self, topics: list, group_id: str):
        """Create consumer with group ID"""
        return KafkaConsumer(
            *topics,
            bootstrap_servers=os.getenv('KAFKA_BROKERS'),
            group_id=group_id,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
```

### 5. DBOS Workflows (KISS)
**State Management**:

```python
# state.py - Simple state management
from dbos import step

class StateManager:
    @step()
    async def save_conversation(self, agent_id: str, messages: list):
        """Durable state save"""
        await db.execute(
            "INSERT INTO conversations (agent_id, messages, created_at) VALUES ($1, $2, $3)",
            agent_id, json.dumps(messages), datetime.now()
        )

    @step()
    async def load_conversation(self, agent_id: str):
        """Load latest state"""
        result = await db.fetchrow(
            "SELECT messages FROM conversations WHERE agent_id = $1 ORDER BY created_at DESC LIMIT 1",
            agent_id
        )
        return json.loads(result['messages']) if result else []
```

---

## Data Flow

### 1. Email Event Flow
```
Gmail → EmailProducer → Kafka(pepper.events.email)
    → SchedulerAgent(DBOS workflow)
    → Claude Agent SDK(decide)
    → Kafka(pepper.tasks.assigned)
    → WorkerAgent(DBOS workflow)
    → Execute tools
    → Kafka(pepper.tasks.results)
    → UI
```

### 2. User Message Flow
```
UI → UserMessageProducer → Kafka(pepper.events.user)
    → SchedulerAgent(DBOS workflow)
    → Claude Agent SDK(respond)
    → Kafka(pepper.ui.messages)
    → UI
```

---

## Database Schema (YAGNI)

**Only essential tables**:

```sql
-- Conversations (DBOS state)
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(255) NOT NULL,
    messages JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- User profiles
CREATE TABLE user_profiles (
    user_id VARCHAR(255) PRIMARY KEY,
    profile_data JSONB NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Task assignments
CREATE TABLE tasks (
    task_id VARCHAR(255) PRIMARY KEY,
    task_type VARCHAR(100) NOT NULL,
    task_data JSONB NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);
```

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Agent Framework | Claude Agent Python SDK | Native agent implementation |
| Message Broker | Apache Kafka | Event streaming, task queue |
| Durable Execution | DBOS Python | Workflow orchestration, state |
| Database | PostgreSQL | State persistence |
| API Framework | FastAPI | REST endpoints for UI |
| Tools | MCP Protocol | Tool integration (reuse from Pepper) |

---

## Deployment Architecture

### Development
```
docker-compose.yml:
  - PostgreSQL (DBOS + app state)
  - Kafka + Zookeeper
  - scheduler-service (SchedulerAgent)
  - worker-service (WorkerAgent pool)
  - api-service (FastAPI)
```

### Production
```
- Kubernetes cluster
- Managed Kafka (Confluent Cloud / MSK)
- Managed PostgreSQL (RDS / Cloud SQL)
- Horizontal scaling: Multiple worker pods
- DBOS handles distributed execution
```

---

## Key Advantages

### vs. Original Pepper

| Feature | Original Pepper | New Design |
|---------|----------------|------------|
| Event Bus | HTTP Context Store | Kafka (distributed) |
| State | Manual save/load | DBOS (automatic) |
| Fault Tolerance | None | DBOS retry + recovery |
| Scaling | Single process | Horizontal (Kafka groups) |
| Message Delivery | At-most-once | At-least-once (Kafka) |
| Agent Framework | Custom | Claude Agent SDK (native) |

---

## KISS, DRY, YAGNI Application

### KISS (Keep It Simple)
- **3 core components**: Event producers, SchedulerAgent, WorkerAgent
- **Clear data flow**: Kafka topics for each event type
- **Standard tools**: Kafka, PostgreSQL, DBOS (proven technologies)

### DRY (Don't Repeat Yourself)
- **Shared KafkaClient**: All components use same Kafka utilities
- **Shared StateManager**: DBOS steps for state operations
- **Reusable MCP tools**: Same tool servers as original Pepper

### YAGNI (You Aren't Gonna Need It)
- **No premature optimization**: Start with simple workflow logic
- **No complex routing**: Kafka consumer groups handle distribution
- **No custom state management**: DBOS handles it
- **No workflow engine**: DBOS provides durable workflows

---

## Migration from Pepper

### Phase 1: Core Infrastructure
1. Set up Kafka topics
2. Set up PostgreSQL + DBOS
3. Migrate event producers (Gmail, UI)

### Phase 2: Agents
1. Implement SchedulerAgent with Claude Agent SDK
2. Implement WorkerAgent with Claude Agent SDK
3. Migrate MCP tool servers (no changes needed)

### Phase 3: Testing & Deployment
1. Integration testing with sample events
2. Load testing with Kafka
3. Deploy to production

---

## File Structure

```
pepper-claude-kafka-dbos/
├── agents/
│   ├── scheduler.py          # SchedulerAgent (Claude SDK + DBOS)
│   ├── worker.py              # WorkerAgent (Claude SDK + DBOS)
│   └── base.py                # Shared agent utilities
├── kafka/
│   ├── client.py              # KafkaClient (DRY)
│   ├── producers.py           # Event producers
│   └── consumers.py           # Event consumers
├── dbos/
│   ├── workflows.py           # DBOS workflow definitions
│   └── state.py               # State management steps
├── tools/
│   └── mcp_tools.py           # MCP tool integration (reused)
├── api/
│   └── server.py              # FastAPI endpoints
├── config/
│   ├── kafka_topics.yaml      # Topic definitions
│   └── dbos_config.yaml       # DBOS configuration
├── db/
│   └── schema.sql             # Database schema
├── docker-compose.yml         # Local development
├── requirements.txt           # Python dependencies
└── README.md                  # Setup instructions
```

---

## Next Steps

1. Review this design
2. Confirm technology choices
3. Begin implementation (Phase 1)
