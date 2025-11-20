# Implementation Notes

## Key Design Decisions

### KISS (Keep It Simple, Stupid)

1. **Simple Architecture**
   - 3 core components: Scheduler, Worker, API
   - Clear separation of concerns
   - Standard technologies (Kafka, PostgreSQL, FastAPI)

2. **Straightforward Data Flow**
   - Events → Kafka → Agents → Results
   - No complex routing or orchestration layers
   - Direct tool calling via Claude SDK

3. **Minimal Configuration**
   - All config via environment variables
   - Sensible defaults
   - Docker Compose for local development

### DRY (Don't Repeat Yourself)

1. **Shared Kafka Client** (`kafka/client.py`)
   - Single KafkaClient class used by all components
   - Centralized serialization/deserialization
   - Reusable consumer and producer factories

2. **Shared State Manager** (`dbos/state.py`)
   - DBOS steps for all state operations
   - Conversation, profile, task management
   - Used by both Scheduler and Worker

3. **Common Patterns**
   - Same workflow pattern for both agents
   - Shared message formatting
   - Consistent error handling

### YAGNI (You Aren't Gonna Need It)

1. **Only Essential Features**
   - No premature optimization
   - No complex workflow engine (DBOS provides it)
   - No custom state management (PostgreSQL + DBOS)
   - No service mesh or complex networking

2. **Minimal Database Schema**
   - Only 3 tables: conversations, user_profiles, tasks
   - DBOS manages workflow state automatically
   - No caching layer (add later if needed)

3. **Basic Tools**
   - Started with simple tools (delegate, send_to_user, wait)
   - MCP integration ready but not fully implemented
   - Can add more tools as requirements emerge

## Claude Agent SDK Integration

### Native Agent Implementation

The design uses Claude Agent SDK's native capabilities:

```python
response = self.client.messages.create(
    model="claude-sonnet-4-5-20250929",
    messages=messages,
    tools=self.tools,
    max_tokens=4000,
)
```

**Benefits**:
- Built-in tool calling
- Streaming support (can be enabled)
- Rate limiting and retries handled by SDK
- Standard message format

### Agent Loop Pattern

Both Scheduler and Worker follow the same pattern:

1. Load conversation state (DBOS step)
2. Add new user message
3. Call Claude SDK
4. Process response and tool calls
5. Save state (DBOS step)

This is **KISS** - no complex state machines.

## Kafka Integration

### Topic Design

Topics follow a clear naming convention:
- `pepper.events.*` - Input events (email, user, reminder)
- `pepper.tasks.*` - Task lifecycle (assigned, results)
- `pepper.ui.*` - UI communication (messages)

**KISS**: Topic per event type, no complex routing.

### Consumer Groups

- Scheduler: `scheduler-group` (single consumer)
- Workers: `worker-group` (multiple consumers for load balancing)

**YAGNI**: Start with simple groups, add partitioning later if needed.

### Message Keys

Messages keyed by:
- Email: `message_id`
- User: `user_id`
- Tasks: `task_id`

**Purpose**: Ordering within key, easier debugging.

## DBOS Integration

### Workflow Pattern

```python
@workflow()
async def process_event(self, event_type: str, event_data: Dict) -> Dict:
    # DBOS ensures this is durable
    context = await self.state_manager.load_conversation(agent_id)
    response = await self._call_claude(messages, summary)
    result = await self._execute_actions(response, messages)
    await self.state_manager.save_conversation(agent_id, messages)
    return result
```

**Benefits**:
- Automatic crash recovery
- Retries on failure
- Idempotent execution
- State checkpointing

### State Management

DBOS `@step()` decorators mark durable operations:
- Database queries
- Kafka publishes (in transaction)
- External API calls

**KISS**: Let DBOS handle complexity, we just mark steps.

## Advantages Over Original Pepper

| Aspect | Original Pepper | New Design |
|--------|----------------|------------|
| **Event Bus** | HTTP Context Store | Kafka (distributed, durable) |
| **State** | Manual save/load | DBOS (automatic, crash-safe) |
| **Fault Tolerance** | None | DBOS retry + Kafka redelivery |
| **Scaling** | Single process | Horizontal (Kafka consumer groups) |
| **Message Delivery** | At-most-once | At-least-once (Kafka guarantees) |
| **Agent Framework** | Custom implementation | Claude Agent SDK (native) |
| **Tool Integration** | MCP stdio | MCP stdio (same, reusable) |
| **Deployment** | Manual | Docker Compose / Kubernetes |

## Production Readiness

### What's Included

✅ Durable execution (DBOS)
✅ Distributed processing (Kafka)
✅ Horizontal scaling (worker pool)
✅ State persistence (PostgreSQL)
✅ Health checks
✅ Graceful shutdown
✅ Docker deployment

### What's Not Included (YAGNI)

❌ Metrics/monitoring (add Prometheus later)
❌ Distributed tracing (add OpenTelemetry later)
❌ Advanced security (add auth/encryption as needed)
❌ Multi-tenancy (add if needed)
❌ Rate limiting (add if needed)
❌ Caching (add if performance requires)

## Next Steps for Production

1. **Add Monitoring**
   - Prometheus metrics
   - Grafana dashboards
   - Alert rules

2. **Add Authentication**
   - API key authentication
   - User sessions
   - Rate limiting per user

3. **Add MCP Tools**
   - Reuse tool servers from original Pepper
   - Add web search, email compose, etc.
   - Tool calling in worker agents

4. **Performance Optimization**
   - Connection pooling tuning
   - Kafka partition optimization
   - Query optimization

5. **Testing**
   - Unit tests for agents
   - Integration tests for workflows
   - Load testing with Kafka

## Migration from Original Pepper

### Phase 1: Infrastructure (Week 1)
- Set up Kafka cluster
- Set up PostgreSQL with DBOS
- Deploy docker-compose locally

### Phase 2: Core Agents (Week 2)
- Migrate SchedulerAgent logic
- Migrate WorkerAgent logic
- Test with sample events

### Phase 3: Tools (Week 3)
- Integrate MCP tool servers
- Add Composio integration
- Add email service integration

### Phase 4: Testing & Deployment (Week 4)
- Integration testing
- Performance testing
- Production deployment

## Code Organization

```
pepper-claude-kafka-dbos/
├── agents/          # Claude Agent SDK agents (KISS: one file per agent)
├── kafka/           # Kafka utilities (DRY: shared client)
├── dbos/            # DBOS workflows and state (DRY: shared steps)
├── api/             # FastAPI server (KISS: simple REST API)
├── db/              # Database schema (YAGNI: minimal tables)
├── docker-compose.yml
└── requirements.txt
```

**KISS**: Flat structure, no over-engineering.

## Summary

This design takes the best parts of Pepper (multi-agent architecture, MCP tools) and makes it production-ready with:

- **Claude Agent SDK**: Native, production-grade agent framework
- **Kafka**: Distributed, durable event streaming
- **DBOS**: Durable workflows with automatic retries

Following:
- **KISS**: Simple architecture, standard tools
- **DRY**: Shared utilities, no duplication
- **YAGNI**: Only what's needed now, extensible later
