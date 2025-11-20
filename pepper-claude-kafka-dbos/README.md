# Pepper with Claude Agent SDK, Kafka, and DBOS

A production-ready personal AI assistant built with:
- **Claude Agent Python SDK** (native agent framework)
- **Apache Kafka** (distributed event streaming)
- **DBOS** (durable execution and state management)

Following **KISS**, **DRY**, and **YAGNI** principles.

---

## Architecture

```
Event Sources → Kafka Topics → DBOS Workflows → Claude Agents → PostgreSQL
```

- **SchedulerAgent**: Orchestrates events, delegates tasks
- **WorkerAgent**: Executes tasks with tool access
- **Kafka**: Event streaming and task distribution
- **DBOS**: Durable workflows with automatic retries
- **PostgreSQL**: State persistence

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Anthropic API key

### Setup

1. **Clone and navigate**:
   ```bash
   cd pepper-claude-kafka-dbos
   ```

2. **Set environment variables**:
   ```bash
   export ANTHROPIC_API_KEY=your_api_key_here
   ```

3. **Start services**:
   ```bash
   docker-compose up -d
   ```

   This starts:
   - PostgreSQL (database)
   - Kafka + Zookeeper (message broker)
   - Scheduler service
   - Worker service
   - API service (port 8000)

4. **Check health**:
   ```bash
   curl http://localhost:8000/health
   ```

---

## Usage

### Send User Message

```bash
curl -X POST http://localhost:8000/api/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "Summarize my important emails from today", "user_id": "user123"}'
```

### Publish Email Event (Webhook)

```bash
curl -X POST http://localhost:8000/api/emails \
  -H "Content-Type: application/json" \
  -d '{
    "message_id": "msg_123",
    "from_address": "alice@example.com",
    "subject": "Project Update",
    "preview": "The project deadline has been moved...",
    "body": "Full email body here..."
  }'
```

### View Logs

```bash
# Scheduler logs
docker-compose logs -f scheduler

# Worker logs
docker-compose logs -f worker

# API logs
docker-compose logs -f api
```

---

## Scaling

Scale workers horizontally (Kafka consumer group load balancing):

```bash
docker-compose up -d --scale worker=3
```

---

## Development

### Local Development (without Docker)

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Start PostgreSQL and Kafka** (via Docker):
   ```bash
   docker-compose up -d postgres kafka zookeeper
   ```

3. **Initialize database**:
   ```bash
   psql -h localhost -U postgres -d pepper -f db/schema.sql
   ```

4. **Set environment variables**:
   ```bash
   export ANTHROPIC_API_KEY=your_key
   export KAFKA_BROKERS=localhost:9092
   export DB_HOST=localhost
   export DB_USER=postgres
   export DB_PASSWORD=postgres
   export DB_NAME=pepper
   ```

5. **Run services**:
   ```bash
   # Terminal 1: Scheduler
   python -m agents.scheduler

   # Terminal 2: Worker
   python -m agents.worker

   # Terminal 3: API
   uvicorn api.server:app --reload
   ```

---

## Configuration

### Kafka Topics

- `pepper.events.email` - Email events
- `pepper.events.user` - User messages
- `pepper.events.reminder` - Reminder triggers
- `pepper.tasks.assigned` - Tasks for workers
- `pepper.tasks.results` - Task results
- `pepper.ui.messages` - Messages to UI

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Claude API key | Required |
| `KAFKA_BROKERS` | Kafka bootstrap servers | `localhost:9092` |
| `DB_HOST` | PostgreSQL host | `localhost` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `DB_USER` | Database user | `postgres` |
| `DB_PASSWORD` | Database password | `postgres` |
| `DB_NAME` | Database name | `pepper` |

---

## Project Structure

```
pepper-claude-kafka-dbos/
├── agents/
│   ├── scheduler.py          # SchedulerAgent (Claude SDK + DBOS)
│   └── worker.py              # WorkerAgent (Claude SDK + DBOS)
├── kafka/
│   ├── client.py              # Shared Kafka client (DRY)
│   └── producers.py           # Event producers
├── dbos/
│   └── state.py               # State management (DBOS steps)
├── api/
│   └── server.py              # FastAPI server
├── db/
│   └── schema.sql             # Database schema
├── docker-compose.yml         # Local deployment
├── Dockerfile                 # Container image
├── requirements.txt           # Python dependencies
├── DESIGN.md                  # Architecture documentation
└── README.md                  # This file
```

---

## Key Features

### DBOS Durable Workflows
- **Automatic retries**: Failed workflows retry automatically
- **Crash recovery**: Workflows resume from last checkpoint
- **State persistence**: All state saved to PostgreSQL

### Kafka Event Streaming
- **Distributed processing**: Multiple workers consume from same topic
- **Guaranteed delivery**: At-least-once message delivery
- **Scalability**: Add workers without code changes

### Claude Agent SDK
- **Native tool calling**: Built-in support for tools
- **Streaming responses**: Real-time agent output
- **Production-ready**: Handles rate limits, errors gracefully

---

## Monitoring

### Metrics (Optional)

Add Prometheus metrics by uncommenting in `requirements.txt`:
```
prometheus-client>=0.20.0
```

Then add to agents:
```python
from prometheus_client import Counter, Histogram

events_processed = Counter('events_processed_total', 'Total events processed')
task_duration = Histogram('task_duration_seconds', 'Task execution duration')
```

---

## Testing

### Unit Tests

```bash
pytest tests/
```

### Integration Tests

```bash
# Start services
docker-compose up -d

# Run tests
pytest tests/integration/

# Cleanup
docker-compose down
```

---

## Production Deployment

### Kubernetes

See `k8s/` directory for Kubernetes manifests (TODO: add if needed).

### Managed Services

Recommended production setup:
- **Kafka**: Confluent Cloud or AWS MSK
- **PostgreSQL**: AWS RDS or Google Cloud SQL
- **Compute**: Kubernetes (EKS, GKE) or serverless (Cloud Run)

---

## Troubleshooting

### Kafka Connection Issues

```bash
# Check Kafka is running
docker-compose ps kafka

# Check topics exist
docker-compose exec kafka kafka-topics --list --bootstrap-server localhost:9092
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Test connection
psql -h localhost -U postgres -d pepper
```

### Agent Errors

Check logs for details:
```bash
docker-compose logs -f scheduler
docker-compose logs -f worker
```

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes following KISS, DRY, YAGNI
4. Add tests
5. Submit pull request

---

## License

MIT License

---

## Acknowledgements

Based on [Pepper](https://github.com/agentica-org/pepper) by the Agentica Team.

Enhanced with:
- [Claude Agent Python SDK](https://www.anthropic.com/)
- [Apache Kafka](https://kafka.apache.org/)
- [DBOS](https://www.dbos.dev/)
