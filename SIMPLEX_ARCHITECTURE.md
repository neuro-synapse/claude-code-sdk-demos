# Simplex Architecture Design

**Design Principles:**
- **Obvious**: Developer can guess what to do without thinking hard
- **Simple**: Avoid complexity at all costs
- **Low Cognitive Load**: Minimal unknown unknowns
- **Confidence**: Quick guesses are likely correct

---

## 1. System Overview

The Simplex system is a real-time, event-driven AI assistant with four core components:

```
┌─────────────────────────────────────────────────────────────┐
│                        SIMPLEX SYSTEM                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐                                               │
│  │  FEEDS   │──────┐                                        │
│  └──────────┘      │                                        │
│   (Sensors)        │    ┌───────────────┐                  │
│                    ├───→│ CONTEXT STORE │                  │
│  ┌──────────┐      │    └───────┬───────┘                  │
│  │  EMAIL   │──────┤            │                           │
│  │  FEED    │      │            │                           │
│  └──────────┘      │            ↓                           │
│                    │    ┌───────────────┐                  │
│  ┌──────────┐      │    │   SCHEDULER   │                  │
│  │ CALENDAR │──────┤    │    (Brain)    │                  │
│  │   FEED   │      │    └───────┬───────┘                  │
│  └──────────┘      │            │                           │
│                    │            │  ┌─────────────┐         │
│  ┌──────────┐      │            ├─→│   WORKERS   │         │
│  │   SMS    │──────┤            │  │   (Hands)   │         │
│  │   FEED   │      │            │  └─────────────┘         │
│  └──────────┘      │            │                           │
│                    │            │  ┌─────────────┐         │
│  ┌──────────┐      │            └─→│ STATEFUL    │         │
│  │  TWITTER │──────┘               │   WORKER    │         │
│  │   FEED   │                      └─────────────┘         │
│  └──────────┘                                               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Data Flow:**
1. **Feeds** monitor external sources → emit clean signals → **Context Store**
2. **Scheduler** pulls signals from queue → makes decision → dispatches to **Workers**
3. **Workers** execute actions using tools → report results → **Scheduler** → **Context Store**

---

## 2. Component Architecture

### 2.1 Feeds (The Sensors)

**Purpose:** Monitor external sources and convert raw events into clean, actionable signals

**Responsibility:**
- Subscribe to data sources (email, calendar, SMS, Twitter, Oura, etc.)
- Filter noise and prioritize events
- Emit structured signals to Context Store
- Maintain high signal-to-noise ratio

**Design:**

```
feeds/
├── base/
│   └── feed.ts              # Abstract Feed class
├── email-feed/
│   ├── feed.ts              # EmailFeed implementation
│   ├── classifier.ts        # Lightweight heuristics or AI classification
│   └── config.ts            # What to listen to, when/how to emit
├── calendar-feed/
│   ├── feed.ts              # CalendarFeed implementation
│   └── config.ts
├── sms-feed/
│   ├── feed.ts              # SMSFeed implementation
│   └── config.ts
├── twitter-feed/
│   ├── feed.ts              # TwitterFeed implementation
│   └── config.ts
└── oura-feed/
    ├── feed.ts              # OuraFeed implementation
    └── config.ts
```

**Feed Interface (Obvious and Simple):**

```typescript
interface Feed {
  // What to listen to
  source: string;                    // "email", "calendar", "sms", etc.

  // Start monitoring
  start(): Promise<void>;

  // Stop monitoring
  stop(): Promise<void>;

  // Process raw event into signal
  process(rawEvent: unknown): Promise<Signal | null>;

  // Emit signal to Context Store
  emit(signal: Signal): Promise<void>;
}

interface Signal {
  id: string;                        // Unique event ID
  source: string;                    // "email", "calendar", etc.
  priority: "urgent" | "high" | "normal" | "low";
  content: string;                   // Human-readable summary
  metadata: Record<string, unknown>; // Source-specific data
  created_at: string;                // ISO timestamp
}
```

**Two Feed Types:**

1. **Lightweight Feed** (Email, SMS, Calendar)
   - Simple heuristics: keywords, sender importance, urgency
   - Fast processing (<100ms)
   - Example: "Action requested by Alice on 'Project Phoenix', due tomorrow."

2. **Sophisticated Feed** (Twitter, Team Chat, Transcripts)
   - AI-powered analysis using Claude
   - Multi-step reasoning to detect blockers, sentiment, action items
   - Example: Analyzes meeting transcript to detect blockers and schedule follow-ups

**Existing Pattern:** Email-agent's `ListenersManager` serves as a Feed prototype

---

### 2.2 Context Store (The Memory)

**Purpose:** Single source of truth for all system state and signals

**Responsibility:**
- Store signals from Feeds
- Maintain FIFO event queue
- Persist conversation history
- Store user profile and preferences
- Provide fast lookups for Scheduler

**Design:**

```
context-store/
├── database/
│   ├── schema.sql           # SQLite schema
│   └── migrations/          # Schema versioning
├── store.ts                 # Main ContextStore class
├── signal-queue.ts          # FIFO queue implementation
├── models/
│   ├── signal.ts            # Signal data model
│   ├── conversation.ts      # Conversation history
│   ├── user-profile.ts      # User preferences
│   └── worker-state.ts      # Stateful worker persistence
└── queries/
    ├── signals.ts           # Signal CRUD operations
    └── workers.ts           # Worker state operations
```

**ContextStore Interface (Obvious and Simple):**

```typescript
interface ContextStore {
  // Signal queue operations
  enqueue(signal: Signal): Promise<void>;
  dequeue(batchSize: number): Promise<Signal[]>;
  peek(count: number): Promise<Signal[]>;

  // Conversation history
  getHistory(limit: number): Promise<Message[]>;
  appendMessage(message: Message): Promise<void>;

  // User profile
  getProfile(): Promise<UserProfile>;
  updateProfile(updates: Partial<UserProfile>): Promise<void>;

  // Worker state (for stateful workers)
  getWorkerState(workerId: string): Promise<WorkerState | null>;
  saveWorkerState(workerId: string, state: WorkerState): Promise<void>;
}
```

**Storage:**
- **SQLite** for persistence (same as email-agent)
- **In-memory cache** for hot data (recent signals, active workers)
- **JSONL logs** for audit trail (same as research-agent)

**Existing Pattern:** Email-agent's database layer + research-agent's transcript system

---

### 2.3 Scheduler (The Brain)

**Purpose:** Central orchestrator that decides what to do and when

**Responsibility:**
- Pull signals from Context Store queue
- Make decisions using LLM
- Dispatch work to Workers
- Maintain system responsiveness
- Handle dependencies between events

**Design:**

```
scheduler/
├── scheduler.ts             # Main Scheduler class
├── loop.ts                  # Event processing loop
├── decision-maker.ts        # LLM-based decision logic
├── dispatcher.ts            # Worker dispatch logic
└── config.ts                # Batch size, timeouts, etc.
```

**Scheduler Architecture:**

```typescript
interface Scheduler {
  // Start the main loop
  start(): Promise<void>;

  // Stop gracefully
  stop(): Promise<void>;

  // Main loop step (single LLM call)
  step(): Promise<void>;

  // Decision logic
  decide(signals: Signal[], context: Context): Promise<Decision[]>;

  // Dispatch to workers
  dispatch(decision: Decision): Promise<void>;
}

interface Decision {
  type: "invoke_worker" | "send_message" | "wait" | "ignore";
  worker?: WorkerType;                    // Which worker to use
  input?: unknown;                        // Input data for worker
  stateful?: boolean;                     // Stateful or stateless?
  worker_id?: string;                     // Resume existing stateful worker
}
```

**Event Processing Loop:**

```
┌─────────────────────────────────────────┐
│         SCHEDULER MAIN LOOP             │
└─────────────────────────────────────────┘
              │
              ↓
      ┌───────────────┐
      │ Pull signals  │  (batch of 1-5 from queue)
      │ from queue    │
      └───────┬───────┘
              │
              ↓
      ┌───────────────┐
      │ Fetch context │  (conversation history, user profile)
      │ from store    │
      └───────┬───────┘
              │
              ↓
      ┌───────────────┐
      │  LLM decides  │  (single LLM call - lightweight)
      │ what to do    │
      └───────┬───────┘
              │
              ↓
      ┌───────────────┐
      │   Dispatch    │  (invoke workers, send messages)
      │   actions     │
      └───────┬───────┘
              │
              ↓
      ┌───────────────┐
      │  Update store │  (log decisions, update state)
      └───────┬───────┘
              │
              ↓
      ┌───────────────┐
      │ Yield control │  (non-blocking sleep ~100ms)
      └───────┬───────┘
              │
              └──────→ (loop)
```

**Key Design Decisions:**

1. **Synchronous Processing:** Only ONE scheduler step at a time
   - Prevents race conditions
   - Simplifies dependency handling
   - Easy to reason about

2. **Lightweight Steps:** Each step completes quickly (<1s)
   - Single LLM call per step
   - Small batch size (1-5 signals)
   - Immediate yielding

3. **Non-Blocking:** Sleep between iterations
   - System stays responsive
   - Feeds can continue emitting signals
   - Workers run in parallel

4. **FIFO Queue:** First in, first out
   - Predictable ordering
   - Simple priority via signal.priority field
   - No complex scheduling algorithms

**Existing Pattern:** Research-agent's Lead Agent (orchestrator using only Task tool)

---

### 2.4 Workers (The Hands)

**Purpose:** Specialized agents that execute actions using tools

**Responsibility:**
- Receive tasks from Scheduler
- Use tools to perform actions (email, calendar, search, etc.)
- Report results back to Scheduler
- Maintain state (stateful workers only)

**Design:**

```
workers/
├── base/
│   ├── worker.ts            # Abstract Worker class
│   ├── stateful.ts          # Stateful Worker base
│   └── stateless.ts         # Stateless Worker base
├── email-worker/
│   ├── worker.ts            # Email specialist
│   └── tools.ts             # Email-specific tools
├── calendar-worker/
│   ├── worker.ts            # Calendar specialist
│   └── tools.ts
├── search-worker/
│   ├── worker.ts            # Web search specialist
│   └── tools.ts
├── reminder-worker/
│   ├── worker.ts            # Reminder specialist
│   └── tools.ts
└── thread-manager-worker/
    ├── worker.ts            # Email thread specialist (STATEFUL)
    └── tools.ts
```

**Worker Interface (Obvious and Simple):**

```typescript
interface Worker {
  // Worker metadata
  id: string;                          // Unique worker ID
  type: WorkerType;                    // "email", "calendar", etc.
  stateful: boolean;                   // Is this stateful?

  // Execute task
  execute(input: WorkerInput): Promise<WorkerOutput>;

  // Tools available to this worker
  tools: Tool[];
}

interface WorkerInput {
  task: string;                        // Natural language task description
  context?: Record<string, unknown>;   // Additional context
}

interface WorkerOutput {
  success: boolean;
  result: string;                      // Human-readable result
  data?: Record<string, unknown>;      // Structured data
  error?: string;
}
```

**Two Worker Types:**

### 2.4.1 Stateless Workers (One-Off Tasks)

**Use Cases:**
- Answer a quick question
- Search for information
- Send a single email
- Create a calendar event

**Characteristics:**
- Ephemeral (created and destroyed per task)
- No memory between invocations
- Fast and lightweight
- Use `return_final_answer` tool to report back

**Example:**

```typescript
class SearchWorker extends StatelessWorker {
  type = "search";
  tools = [WebSearchTool, ReturnFinalAnswerTool];

  async execute(input: WorkerInput): Promise<WorkerOutput> {
    // Single-use: search and return
    // No state persisted
  }
}
```

**Existing Pattern:** Research-agent's Researcher subagents (one-off web search tasks)

### 2.4.2 Stateful Workers (Long-Running Tasks)

**Use Cases:**
- Manage email thread (track conversation over days)
- Maintain task list (update across sessions)
- Coordinate reminders (schedule and track follow-ups)
- Monitor ongoing project (accumulate context over time)

**Characteristics:**
- Persistent identity (same worker_id across invocations)
- Maintain "mini-world" with dedicated memory
- Resume from saved state
- Can be invoked multiple times

**State Persistence:**

```typescript
interface WorkerState {
  worker_id: string;
  worker_type: WorkerType;
  created_at: string;
  updated_at: string;

  // Event history
  events: Array<{
    timestamp: string;
    event_type: string;
    data: unknown;
  }>;

  // Running summary
  summary: string;

  // Domain-specific state
  state: Record<string, unknown>;
}
```

**Example:**

```typescript
class EmailThreadWorker extends StatefulWorker {
  type = "email_thread";
  tools = [ReadEmailTool, SendEmailTool, ArchiveEmailTool];

  async execute(input: WorkerInput): Promise<WorkerOutput> {
    // Load previous state
    const state = await this.loadState();

    // Execute task with context
    const result = await this.processWithContext(input, state);

    // Save updated state
    await this.saveState(state);

    return result;
  }
}
```

**State Storage:** SQLite in Context Store (workers table)

**Existing Pattern:** Email-agent's action system (stateful execution with audit trail)

---

## 3. File Structure

**Complete Directory Layout:**

```
simplex/
├── feeds/                           # Feed implementations
│   ├── base/
│   │   ├── feed.ts                  # Abstract Feed
│   │   └── signal.ts                # Signal interface
│   ├── email-feed/
│   │   ├── feed.ts
│   │   ├── classifier.ts
│   │   └── config.ts
│   ├── calendar-feed/
│   ├── sms-feed/
│   ├── twitter-feed/
│   └── oura-feed/
│
├── context-store/                   # State and persistence
│   ├── database/
│   │   ├── schema.sql
│   │   └── migrations/
│   ├── store.ts                     # Main ContextStore
│   ├── signal-queue.ts              # FIFO queue
│   ├── models/
│   │   ├── signal.ts
│   │   ├── conversation.ts
│   │   ├── user-profile.ts
│   │   └── worker-state.ts
│   └── queries/
│       ├── signals.ts
│       └── workers.ts
│
├── scheduler/                       # Orchestration brain
│   ├── scheduler.ts                 # Main Scheduler
│   ├── loop.ts                      # Event loop
│   ├── decision-maker.ts            # LLM decision logic
│   ├── dispatcher.ts                # Worker dispatch
│   └── config.ts
│
├── workers/                         # Execution layer
│   ├── base/
│   │   ├── worker.ts                # Abstract Worker
│   │   ├── stateful.ts              # Stateful base
│   │   └── stateless.ts             # Stateless base
│   ├── email-worker/
│   ├── calendar-worker/
│   ├── search-worker/
│   ├── reminder-worker/
│   └── thread-manager-worker/       # Stateful example
│
├── tools/                           # Worker tools (MCP)
│   ├── email-tools.ts
│   ├── calendar-tools.ts
│   ├── search-tools.ts
│   └── reminder-tools.ts
│
├── server/                          # HTTP + WebSocket server
│   ├── server.ts
│   ├── websocket-handler.ts
│   └── endpoints/
│       ├── feeds.ts
│       ├── scheduler.ts
│       └── workers.ts
│
├── client/                          # Optional frontend
│   └── (React app for monitoring)
│
├── logs/                            # Audit trail
│   ├── signals.jsonl                # All signals
│   ├── decisions.jsonl              # Scheduler decisions
│   └── worker-calls.jsonl           # Worker invocations
│
└── config/                          # Configuration
    ├── feeds.yaml                   # Feed configurations
    ├── scheduler.yaml               # Scheduler settings
    └── workers.yaml                 # Worker definitions
```

---

## 4. Data Flow Examples

### 4.1 Simple Flow (Stateless Worker)

**Scenario:** Important email arrives from Alice requesting action

```
1. EMAIL FEED
   - IMAP detects new email
   - Classifier: sender=Alice (VIP), keywords="urgent", "action needed"
   - Emit signal:
     {
       id: "sig_123",
       source: "email",
       priority: "urgent",
       content: "Action requested by Alice on 'Project Phoenix', due tomorrow.",
       metadata: { email_id: "456", sender: "alice@company.com" }
     }

2. CONTEXT STORE
   - Enqueue signal (FIFO)
   - Queue now contains: [sig_123]

3. SCHEDULER (next loop iteration)
   - Dequeue signals: [sig_123]
   - Fetch context: conversation history, user profile
   - LLM decision: "Send email to Alice acknowledging request"
   - Decision:
     {
       type: "invoke_worker",
       worker: "email",
       stateful: false,
       input: {
         task: "Send acknowledgment to Alice about Project Phoenix action",
         context: { email_id: "456", sender: "alice@company.com" }
       }
     }

4. WORKER (Stateless Email Worker)
   - Receive task
   - Use SendEmailTool: compose and send email
   - Return result:
     {
       success: true,
       result: "Acknowledgment sent to Alice"
     }

5. SCHEDULER
   - Receive worker result
   - Update Context Store (log decision and result)
   - Continue loop
```

**Total Time:** ~2-3 seconds from email arrival to response sent

---

### 4.2 Complex Flow (Stateful Worker)

**Scenario:** User has ongoing email thread with client, needs tracking across days

```
1. INITIAL REQUEST (Day 1)
   - Email Feed emits signal: "New thread started with client XYZ"
   - Scheduler decides: "Create stateful worker to manage this thread"
   - Decision:
     {
       type: "invoke_worker",
       worker: "email_thread",
       stateful: true,
       worker_id: "thread_xyz_001",  // New worker instance
       input: {
         task: "Monitor and manage email thread with client XYZ",
         context: { thread_id: "789", client: "XYZ Corp" }
       }
     }

2. STATEFUL WORKER CREATED
   - Worker ID: "thread_xyz_001"
   - Initial state:
     {
       worker_id: "thread_xyz_001",
       worker_type: "email_thread",
       events: [
         { timestamp: "2025-01-15T10:00:00Z", event_type: "thread_started", ... }
       ],
       summary: "Managing email thread with XYZ Corp about contract renewal",
       state: { thread_id: "789", last_response: "2025-01-15T10:00:00Z" }
     }
   - Worker executes: sends initial response
   - Worker saves state to Context Store
   - Worker reports back: "Thread initiated, monitoring"

3. FOLLOW-UP (Day 2)
   - Email Feed emits signal: "Reply received in thread with client XYZ"
   - Scheduler decides: "Resume existing worker"
   - Decision:
     {
       type: "invoke_worker",
       worker: "email_thread",
       stateful: true,
       worker_id: "thread_xyz_001",  // SAME worker instance
       input: {
         task: "Process new reply from client XYZ",
         context: { email_id: "890" }
       }
     }

4. STATEFUL WORKER RESUMED
   - Load state from Context Store (worker_id="thread_xyz_001")
   - Worker has full history:
     - Original request
     - Initial response
     - All intermediate messages
   - Worker processes new reply WITH CONTEXT
   - Worker updates state:
     {
       events: [...previous events..., { timestamp: "2025-01-16T14:00:00Z", event_type: "reply_received", ... }],
       summary: "Client responded with contract questions, answered FAQ 1-3",
       state: { thread_id: "789", last_response: "2025-01-16T14:30:00Z" }
     }
   - Worker saves updated state
   - Worker reports back: "Reply processed, FAQ answered"

5. REMINDER (Day 3)
   - Calendar Feed emits signal: "Reminder: follow up on XYZ thread"
   - Scheduler decides: "Resume existing worker"
   - Worker loads state, sees no response yet
   - Worker sends gentle follow-up email
   - Worker updates state and saves
```

**Benefits of Stateful Worker:**
- **Context preservation**: Full thread history across days
- **Consistency**: Same worker maintains coherent interaction style
- **State tracking**: Knows what's been said, what's pending
- **Efficiency**: No need to re-analyze entire thread each time

---

## 5. Component Interfaces

### 5.1 Feed → Context Store

**Method:** `ContextStore.enqueue(signal: Signal)`

**Contract:**
- Feed MUST provide valid Signal with all required fields
- Context Store MUST acknowledge receipt
- Context Store MUST preserve order (FIFO)
- Idempotent: same signal.id can be enqueued multiple times (deduplicated)

---

### 5.2 Context Store → Scheduler

**Method:** `ContextStore.dequeue(batchSize: number)`

**Contract:**
- Context Store returns 0 to batchSize signals (FIFO order)
- Signals are NOT removed until Scheduler acknowledges processing
- Empty array if queue is empty (non-blocking)

---

### 5.3 Scheduler → Workers

**Method:** `Worker.execute(input: WorkerInput)`

**Contract:**
- Scheduler MUST provide valid WorkerInput
- Worker MUST return WorkerOutput (success or failure)
- Worker MUST complete in reasonable time (<30s for stateless, <2min for stateful)
- Worker MUST use return_final_answer tool to report results

---

### 5.4 Workers → Context Store (Stateful Only)

**Methods:**
- `ContextStore.getWorkerState(workerId: string)`
- `ContextStore.saveWorkerState(workerId: string, state: WorkerState)`

**Contract:**
- Worker MUST save state after each execution
- Context Store MUST persist state durably (survive restarts)
- Worker MUST handle missing state gracefully (first invocation)

---

## 6. Simplicity Guarantees

### 6.1 Obvious File Locations

**Rule:** File location = component name + function

**Examples:**
- Email feed logic? → `feeds/email-feed/feed.ts`
- Signal queue? → `context-store/signal-queue.ts`
- Scheduler loop? → `scheduler/loop.ts`
- Email worker? → `workers/email-worker/worker.ts`

**No Guesswork:** Developer can navigate codebase without documentation

---

### 6.2 Obvious Data Flow

**Rule:** All data flows through Context Store

**Simplified Mental Model:**
```
Feeds → Context Store ← Scheduler → Workers
                 ↓
           (persistence)
```

**No Hidden Channels:** No direct Feed→Scheduler or Worker→Feed communication

---

### 6.3 Obvious Execution Model

**Rule:** Scheduler is the ONLY orchestrator

**Guaranteed:**
- Only ONE Scheduler step at a time (synchronous)
- All decisions go through Scheduler
- Workers NEVER invoke other workers
- Feeds NEVER invoke workers

**Easy to Reason About:** Single point of control

---

### 6.4 Obvious State Management

**Rule:** Context Store is the ONLY source of truth

**Guaranteed:**
- All signals stored in Context Store
- All worker state stored in Context Store
- No in-memory state (except caches)
- Restart-safe: system resumes from Context Store

**Easy to Debug:** Check Context Store to see entire system state

---

### 6.5 Obvious Worker Types

**Rule:** Only TWO worker types

**Decision Tree:**
```
Does this task need memory across invocations?
  ├─ Yes → Stateful Worker
  └─ No  → Stateless Worker
```

**No Ambiguity:** Clear choice for every use case

---

## 7. Error Handling

### 7.1 Feed Errors

**Strategy:** Retry with exponential backoff, then log and skip

```
Feed error (e.g., API timeout) →
  Retry 1 (after 1s) → Retry 2 (after 2s) → Retry 3 (after 4s) →
    Still failing? Log error, skip event, continue monitoring
```

**Guarantee:** One Feed's failure doesn't block other Feeds

---

### 7.2 Scheduler Errors

**Strategy:** Log, skip problematic signal, continue loop

```
Scheduler error (e.g., LLM timeout) →
  Log error with full context →
    Move signal to dead-letter queue →
      Continue processing next signals
```

**Guarantee:** System stays responsive even with bad signals

---

### 7.3 Worker Errors

**Strategy:** Timeout after 30s (stateless) or 2min (stateful), log, report failure

```
Worker error or timeout →
  Log error with full input/output →
    Return WorkerOutput with success=false →
      Scheduler decides whether to retry
```

**Guarantee:** Workers can't hang the system

---

## 8. Observability

### 8.1 Logging

**All Events Logged to JSONL:**

```
logs/
├── signals.jsonl           # Every signal emitted by Feeds
├── decisions.jsonl         # Every Scheduler decision
└── worker-calls.jsonl      # Every Worker invocation + result
```

**Format:** One JSON object per line, greppable, human-readable

**Existing Pattern:** Research-agent's comprehensive JSONL logging

---

### 8.2 Monitoring Dashboard (Optional)

**Real-Time View:**
- Current queue size (how many signals pending?)
- Scheduler status (processing, idle, error)
- Active workers (which stateful workers running?)
- Recent errors (last 10 errors across all components)

**Implementation:** React frontend + WebSocket (same as email-agent)

---

## 9. Configuration

### 9.1 Feed Configuration (`config/feeds.yaml`)

```yaml
feeds:
  - type: email
    enabled: true
    source: imap://imap.gmail.com
    poll_interval: 30s
    classifier: lightweight  # or "ai"
    priority_rules:
      - sender: alice@company.com
        priority: urgent
      - keywords: ["action needed", "urgent"]
        priority: high

  - type: calendar
    enabled: true
    source: google-calendar
    poll_interval: 60s

  - type: sms
    enabled: true
    source: twilio
    webhook: true  # Real-time via webhook
```

**Obvious:** All feed settings in one file

---

### 9.2 Scheduler Configuration (`config/scheduler.yaml`)

```yaml
scheduler:
  loop_interval: 100ms       # Sleep between iterations
  batch_size: 3              # Max signals per step
  llm_model: claude-sonnet-4-5
  llm_timeout: 10s
  max_retries: 3
```

**Obvious:** All scheduler settings in one file

---

### 9.3 Worker Configuration (`config/workers.yaml`)

```yaml
workers:
  stateless:
    - type: email
      tools: [read_email, send_email, archive_email]
      timeout: 30s

    - type: search
      tools: [web_search]
      timeout: 20s

  stateful:
    - type: email_thread
      tools: [read_email, send_email, archive_email, get_thread_history]
      timeout: 120s
      state_ttl: 30d  # Auto-cleanup after 30 days
```

**Obvious:** All worker definitions in one file

---

## 10. Deployment

### 10.1 Single Process Architecture

**Simplest Deployment:** All components run in one Node.js process

```
┌─────────────────────────────────┐
│      Simplex Process            │
│                                 │
│  ┌──────────────────────────┐  │
│  │   Feeds (background)     │  │
│  └──────────────────────────┘  │
│                                 │
│  ┌──────────────────────────┐  │
│  │   Scheduler (main loop)  │  │
│  └──────────────────────────┘  │
│                                 │
│  ┌──────────────────────────┐  │
│  │   Workers (on-demand)    │  │
│  └──────────────────────────┘  │
│                                 │
│  ┌──────────────────────────┐  │
│  │   Context Store (SQLite) │  │
│  └──────────────────────────┘  │
│                                 │
└─────────────────────────────────┘
```

**Benefits:**
- No network latency between components
- No distributed systems complexity
- Easy to develop and debug
- Fast startup and shutdown

**Limitation:** Single machine, but sufficient for most use cases

---

### 10.2 Startup Sequence

```
1. Load configuration files
2. Initialize Context Store (SQLite)
3. Start Feeds (background monitoring)
4. Start Scheduler (main loop)
5. Start WebSocket server (optional, for monitoring)
6. Ready!
```

**Total Startup Time:** <1 second

---

### 10.3 Shutdown Sequence

```
1. Stop Feeds (graceful disconnect)
2. Stop Scheduler (finish current step)
3. Wait for active Workers (max 2min timeout)
4. Flush logs to disk
5. Close Context Store
6. Exit
```

**Graceful Degradation:** System can resume from Context Store after restart

---

## 11. Development Workflow

### 11.1 Adding a New Feed

**Steps:**
1. Create `feeds/<feed-name>/feed.ts` implementing `Feed` interface
2. Add configuration to `config/feeds.yaml`
3. Register feed in `feeds/index.ts`
4. Done!

**Time:** ~30 minutes for simple feed

**Existing Pattern:** Email-agent's listener system

---

### 11.2 Adding a New Worker

**Steps:**
1. Create `workers/<worker-name>/worker.ts` extending `StatelessWorker` or `StatefulWorker`
2. Define tools in `workers/<worker-name>/tools.ts`
3. Add configuration to `config/workers.yaml`
4. Register worker in `workers/index.ts`
5. Done!

**Time:** ~1 hour for stateless, ~2 hours for stateful

**Existing Pattern:** Research-agent's subagent system

---

### 11.3 Debugging

**Tools:**
1. **JSONL logs**: Grep for specific signal IDs, worker IDs, timestamps
2. **SQLite CLI**: Query Context Store directly (`sqlite3 context-store.db`)
3. **Monitoring dashboard**: Real-time view of system state
4. **Print statements**: Console.log shows in process stdout

**Existing Pattern:** Research-agent's comprehensive logging

---

## 12. Key Architectural Decisions

### 12.1 Why Synchronous Scheduler?

**Rationale:**
- Simplifies dependency handling between events
- Prevents race conditions
- Easy to reason about execution order
- Single point of control

**Trade-off:** Lower throughput vs. async, but sufficient for human-scale events

---

### 12.2 Why FIFO Queue?

**Rationale:**
- Predictable ordering (obvious)
- Simple priority via `signal.priority` field
- No complex scheduling algorithms
- Easy to debug (signals processed in order they arrive)

**Trade-off:** Less flexible than priority queue, but simpler

---

### 12.3 Why SQLite?

**Rationale:**
- Single file, no server to manage
- ACID guarantees (reliable)
- Fast for single-process workloads
- Restart-safe persistence

**Trade-off:** Single machine only, but sufficient for this use case

**Existing Pattern:** Email-agent uses SQLite successfully

---

### 12.4 Why Two Worker Types Only?

**Rationale:**
- Covers all use cases (one-off vs. long-running)
- Clear decision criteria (memory needed or not?)
- Prevents over-engineering
- Easy to explain

**Trade-off:** Could add more types, but complexity cost is high

---

## 13. Migration from Current Codebase

### 13.1 Reusable Patterns

**From Email-Agent:**
- ✅ Listener system → Feed architecture
- ✅ Action system → Worker templates
- ✅ WebSocket server → Monitoring dashboard
- ✅ SQLite database → Context Store

**From Research-Agent:**
- ✅ Subagent system → Worker architecture
- ✅ Hook-based tracking → Observability logging
- ✅ JSONL logs → Audit trail
- ✅ Lead agent orchestration → Scheduler decision-making

**From SMS-Agent:**
- ✅ Message processing → Signal processing
- ✅ Contact awareness → User profile in Context Store

---

### 13.2 What Changes?

**Consolidation:**
- Email-agent's listeners + research-agent's orchestrator → Unified Scheduler
- Multiple databases → Single Context Store
- Ad-hoc tool definitions → Centralized worker/tool configuration

**Simplification:**
- Remove email-agent's complex UI state system (not needed for Simplex)
- Remove research-agent's wide-mode complexity (single Scheduler handles all)
- Single event loop vs. multiple independent systems

---

## 14. Success Metrics

### 14.1 Obviousness Test

**Question:** Can a new developer find the code they need in <30 seconds?

**Measurement:**
- Time to locate Feed for email: `feeds/email-feed/feed.ts`
- Time to locate Scheduler loop: `scheduler/loop.ts`
- Time to locate Worker state: `context-store/queries/workers.ts`

**Goal:** Average <15 seconds

---

### 14.2 Simplicity Test

**Question:** Can a developer add a new Feed without reading documentation?

**Measurement:**
- Copy existing Feed (e.g., `sms-feed/`)
- Modify for new source
- Add to config
- Works on first try?

**Goal:** 90% success rate without docs

---

### 14.3 Low Cognitive Load Test

**Question:** Can a developer hold the entire architecture in their head?

**Measurement:**
- 4 core components (Feeds, Context Store, Scheduler, Workers)
- 2 worker types (Stateful, Stateless)
- 1 data flow (Feeds → Context Store ← Scheduler → Workers)

**Goal:** Explainable in <2 minutes

---

## 15. Summary

### Core Principles

1. **Obvious**: File location = function, data flow is linear
2. **Simple**: 4 components, 2 worker types, 1 source of truth
3. **Low Cognitive Load**: Everything goes through Context Store
4. **Confident Guessing**: Developer intuition is usually correct

### Component Summary

- **Feeds**: Sensors monitoring external sources → clean signals
- **Context Store**: Single source of truth for state and signals
- **Scheduler**: Synchronous brain making decisions in event loop
- **Workers**: Stateless (one-off) or Stateful (long-running) executors

### File Structure

```
simplex/
├── feeds/               # Monitoring external sources
├── context-store/       # State persistence
├── scheduler/           # Orchestration brain
├── workers/             # Execution layer
├── tools/               # Worker capabilities
├── server/              # HTTP + WebSocket
├── logs/                # JSONL audit trail
└── config/              # YAML configuration
```

### Key Guarantees

1. Only ONE Scheduler step at a time (synchronous)
2. All state in Context Store (restart-safe)
3. All data flows through Context Store (no hidden channels)
4. Only TWO worker types (stateful/stateless)
5. Graceful degradation (errors don't cascade)

### Next Steps

1. Implement Context Store (SQLite + queue)
2. Implement Scheduler loop (event processing)
3. Implement base Worker classes (stateful/stateless)
4. Implement first Feed (email-feed)
5. End-to-end test (email arrives → Scheduler decides → Worker acts)
6. Add observability (JSONL logs, monitoring dashboard)
7. Add remaining Feeds (calendar, SMS, Twitter, Oura)

---

**End of Architecture Document**
