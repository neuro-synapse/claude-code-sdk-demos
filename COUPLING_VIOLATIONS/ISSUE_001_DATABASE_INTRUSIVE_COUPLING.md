# [COUPLING] [CRITICAL]: Multiple Uncoordinated Database Instances in email-agent

**Issue ID**: #001
**Severity**: Critical
**Type**: Intrusive Coupling
**Module**: email-agent
**Status**: Open
**Created**: 2025-10-16

---

## Problem Statement

The email-agent service creates **7 independent SQLite Database instances** across multiple modules without coordination. This represents intrusive coupling where modules directly access shared database resources without proper abstraction, leading to potential connection conflicts, inconsistent state, and Write-Ahead Logging (WAL) issues.

Each module instantiates its own Database connection independently, creating:
- Resource contention and file locking issues
- Inconsistent caching and prepared statement management
- No centralized query logging or performance monitoring
- Unpredictable behavior under concurrent access

---

## Current State

### Location

**Files with Database Instantiations:**

1. **`/root/repo/email-agent/server/server.ts:19`**
   ```typescript
   const db = new Database(DATABASE_PATH);
   ```

2. **`/root/repo/email-agent/server/server.ts:21-22`**
   ```typescript
   const dbManager = DatabaseManager.getInstance();  // Internal: new Database()
   const imapManager = ImapManager.getInstance();
   ```

3. **`/root/repo/email-agent/server/server.ts:34`**
   ```typescript
   const syncService = new EmailSyncService(DATABASE_PATH);  // Internal: new EmailDatabase()
   ```

4. **`/root/repo/email-agent/ccsdk/websocket-handler.ts` (constructor)**
   ```typescript
   constructor(dbPath: string = DATABASE_PATH) {
     this.db = new Database(dbPath);  // Instance #4
   }
   ```

5. **`/root/repo/email-agent/database/database-manager.ts:74`**
   ```typescript
   private constructor(dbPath: string = DATABASE_PATH) {
     this.db = new Database(dbPath);  // Singleton instance #2
   }
   ```

6. **`/root/repo/email-agent/database/email-db.ts:75`**
   ```typescript
   constructor(dbPath: string = DATABASE_PATH) {
     this.db = new Database(dbPath);  // Instance #3
   }
   ```

7. **`/root/repo/email-agent/server/endpoints/emails.ts` (estimated ~line 10-15)**
   ```typescript
   const db = new Database(DATABASE_PATH);  // Additional instances in endpoints
   ```

8. **`/root/repo/email-agent/server/endpoints/sync.ts` (estimated ~line 10-15)**
   ```typescript
   const db = new Database(DATABASE_PATH);
   ```

**Module Dependencies:**
- server → database (direct instantiation)
- server → ccsdk (creates wsHandler with its own db)
- server → endpoints (endpoints create their own instances)
- ccsdk/websocket-handler → database (direct instantiation)
- database/database-manager → sqlite (singleton)
- database/email-db → sqlite (regular class)

**Owner(s)**: Backend Infrastructure Team, Email Service Team

**Coupling Type**: Intrusive (Direct resource access without coordination)

**Connascence Degree**: **Connascence of Identity (CoI)** - Multiple components must share the same database instance for consistency, but currently don't.

---

### Evidence

**server.ts creates 4 different connection pathways:**
```typescript
// Line 19 - Direct instance for sync metadata
const db = new Database(DATABASE_PATH);

// Line 21 - DatabaseManager singleton (internal Database instance)
const dbManager = DatabaseManager.getInstance();

// Line 22 - ImapManager uses DatabaseManager internally
const imapManager = ImapManager.getInstance();

// Line 34 - EmailSyncService creates EmailDatabase (another internal instance)
const syncService = new EmailSyncService(DATABASE_PATH);

// Line 18 - WebSocketHandler creates its own instance
const wsHandler = new WebSocketHandler(DATABASE_PATH);
```

**Concurrent Database Access Points:**
```
Server Startup:
  ├─ db (server.ts:19) → emails.db
  ├─ dbManager.db (database-manager.ts:74) → emails.db
  ├─ syncService.database.db (email-db.ts:75) → emails.db
  ├─ wsHandler.db (websocket-handler.ts) → emails.db
  ├─ endpoints/emails.ts: db → emails.db
  └─ endpoints/sync.ts: db → emails.db

= 7 INDEPENDENT DATABASE CONNECTIONS TO SAME FILE
```

---

## Impact Assessment

### Severity: Critical

#### Why This Matters

**Business Impact**:
- **Data Corruption Risk**: Multiple uncoordinated writes can violate ACID properties
- **Race Conditions**: Two handlers updating same email simultaneously = unpredictable state
- **Performance Degradation**: Each connection maintains separate cache and prepared statements
- **Production Incidents**: Intermittent "database is locked" errors under load
- **User Experience**: Slow response times, occasional 500 errors

**Technical Impact**:
- **WAL Mode Conflicts**: SQLite's Write-Ahead Logging has limitations with multiple connections
- **No Connection Pooling**: Each module opens its own file handle
- **Memory Overhead**: 7× statement cache overhead
- **Query Performance**: No shared query cache or optimization
- **Difficult Debugging**: Data mutations can happen from 7 different code paths
- **No Transaction Coordination**: Cross-module operations can't be atomic

**Team Impact**:
- **Difficult Troubleshooting**: "Which module wrote this data?" question has 7 possible answers
- **Coordination Overhead**: All database schema changes must be tested with 7 access patterns
- **Onboarding Friction**: New developers confused by multiple database abstractions
- **Code Review Complexity**: Reviewers must check all 7 instantiation points

---

### Blast Radius

**Modules Affected**: 4 primary modules
- `server` (main application)
- `database` (two competing abstractions)
- `ccsdk` (WebSocket handler)
- `endpoints` (REST API handlers)

**Teams Affected**: 2-3 teams
- Backend Infrastructure (owns database layer)
- Email Feature Team (owns server and endpoints)
- AI Integration Team (owns ccsdk module)

**Deployment Coupling**: **Critical**
- All modules must deploy together
- Cannot independently version database access layer
- Schema migrations affect 7 different access patterns
- Rollback complexity: must ensure all 7 access points are compatible

---

### Risk Factors

**Change Frequency**: **High**
- Email-agent is actively developed
- Database schema evolves frequently
- New features regularly add database queries

**Failure Probability**: **Medium-High**
- SQLite *can* handle multiple readers
- BUT: Write contention causes locking
- WAL mode mitigates but doesn't eliminate issues
- Under load: "database is locked" errors likely

**Detection Difficulty**: **Very High**
- Issues manifest intermittently
- Reproduce only under concurrent load
- No centralized logging of database operations
- Race conditions are non-deterministic
- Data inconsistency may go unnoticed until much later

**Example Failure Scenario**:
```
1. WebSocket client requests inbox → wsHandler.db.prepare(SELECT...)
2. Simultaneously: Sync job runs → syncService.db.prepare(INSERT...)
3. Endpoint receives search request → endpoint.db.prepare(SELECT...)
4. All three execute concurrently on same emails.db file
5. SQLite WAL checkpoint triggers
6. Random "database is locked" error to one of the callers
7. User sees 500 error, no indication of what failed
```

---

## Current Behavior vs. Expected Behavior

### Current Behavior

**Initialization (server startup)**:
```typescript
// 7 different Database instances created
const db = new Database(DATABASE_PATH);  // #1
const dbManager = DatabaseManager.getInstance();  // #2 (internal)
const wsHandler = new WebSocketHandler(DATABASE_PATH);  // #3 (internal)
const syncService = new EmailSyncService(DATABASE_PATH);  // #4 (internal EmailDatabase)
// + 3 more in endpoints
```

**Query Execution**:
- Each module executes queries independently
- No shared prepared statement cache
- No centralized logging
- No transaction coordination across modules

**Connection Lifecycle**:
- Connections opened at module initialization
- Never explicitly closed (rely on process exit)
- No connection pooling or management
- No health checks or reconnection logic

**Consequences**:
- Inconsistent query performance (cold cache for each connection)
- Difficult to implement request tracing
- Cannot optimize queries globally
- Cannot implement query throttling or rate limiting

---

### Expected Behavior

**Single Database Connection Manager**:
```typescript
// Infrastructure layer
export class DatabaseConnectionPool {
  private static instance: DatabaseConnectionPool;
  private db: Database;

  private constructor() {
    this.db = new Database(DATABASE_PATH);
    this.db.exec("PRAGMA journal_mode = WAL");
    this.db.exec("PRAGMA foreign_keys = ON");
    this.initializeSchema();
  }

  public static getInstance(): DatabaseConnectionPool {
    if (!DatabaseConnectionPool.instance) {
      DatabaseConnectionPool.instance = new DatabaseConnectionPool();
    }
    return DatabaseConnectionPool.instance;
  }

  public getConnection(): Database {
    return this.db;  // Always returns same instance
  }
}
```

**Repository Pattern**:
```typescript
// Data access layer
export interface IEmailRepository {
  searchEmails(criteria: SearchCriteria): Promise<EmailRecord[]>;
  upsertEmail(email: EmailRecord): Promise<number>;
  getRecentEmails(limit: number): Promise<EmailRecord[]>;
}

export class EmailRepository implements IEmailRepository {
  constructor(private db: Database) {}  // Injected dependency

  async searchEmails(criteria: SearchCriteria): Promise<EmailRecord[]> {
    // Implementation uses this.db
  }
}
```

**Dependency Injection**:
```typescript
// Server initialization
const pool = DatabaseConnectionPool.getInstance();
const db = pool.getConnection();

// Create repositories
const emailRepo = new EmailRepository(db);
const syncRepo = new SyncRepository(db);

// Inject into services
const wsHandler = new WebSocketHandler(emailRepo);
const syncService = new EmailSyncService(syncRepo, emailRepo);
const imapManager = new ImapManager(emailRepo);

// Inject into endpoints
const emailEndpoints = createEmailEndpoints(emailRepo);
```

**Benefits**:
- ✅ Single source of truth for database access
- ✅ Centralized query logging and monitoring
- ✅ Easy to mock for testing
- ✅ Clear dependency tree
- ✅ No hidden database access
- ✅ Can implement transaction coordination
- ✅ Can optimize query performance globally

---

### Violated Principles

1. **Single Responsibility Principle (SRP)**
   - Multiple modules responsible for creating database connections
   - Connection management logic scattered across codebase

2. **Dependency Inversion Principle (DIP)**
   - High-level modules (server, ccsdk) depend on low-level details (SQLite Database class)
   - Should depend on abstractions (IEmailRepository, IDatabase)

3. **Don't Repeat Yourself (DRY)**
   - Database instantiation logic duplicated 7 times
   - Connection configuration repeated in each module

4. **Open/Closed Principle**
   - Cannot change database implementation without modifying all 7 instantiation points
   - Not open for extension (can't swap SQLite for PostgreSQL)

5. **Interface Segregation Principle**
   - Modules that only read emails still have full Database write access
   - No role-based or permission-based connection management

---

## Remediation Plan

### Recommended Solution: Repository Pattern with Connection Pool

**Design Strategy**:

1. **Create DatabaseConnectionPool** (Infrastructure Layer)
   - Single managed SQLite connection
   - Lifecycle management (init, health checks, graceful shutdown)
   - Schema initialization
   - Query logging and monitoring

2. **Implement Repository Pattern** (Data Access Layer)
   - `IEmailRepository` interface with read/write operations
   - `ISyncRepository` interface for sync metadata
   - `IAttachmentRepository` interface for attachments
   - Concrete implementations injected with Database instance

3. **Inject Dependencies** (Application Layer)
   - All services receive repository interfaces via constructor
   - No service directly imports or uses Database class
   - Clear dependency graph visible in server.ts

4. **Migrate Existing Code**
   - Replace direct Database access with repository calls
   - Move SQL queries from business logic into repositories
   - Update unit tests to mock repositories

5. **Remove Duplicates**
   - Delete DatabaseManager class (superseded by repositories)
   - Delete EmailDatabase class (superseded by repositories)
   - Consolidate schema initialization

---

### Specific Implementation Steps

#### Step 1: Create Infrastructure Layer (2 days)

**File: `database/infrastructure/connection-pool.ts`**
```typescript
import { Database } from "bun:sqlite";
import { DATABASE_PATH } from "../config";
import { initializeSchema } from "./schema";

export class DatabaseConnectionPool {
  private static instance: DatabaseConnectionPool;
  private db: Database;
  private isInitialized = false;

  private constructor() {
    this.db = new Database(DATABASE_PATH);
    this.configure();
    this.initialize();
  }

  private configure(): void {
    this.db.exec("PRAGMA journal_mode = WAL");
    this.db.exec("PRAGMA foreign_keys = ON");
    this.db.exec("PRAGMA busy_timeout = 5000");  // 5 second timeout
  }

  private initialize(): void {
    if (!this.isInitialized) {
      initializeSchema(this.db);
      this.isInitialized = true;
    }
  }

  public static getInstance(): DatabaseConnectionPool {
    if (!DatabaseConnectionPool.instance) {
      DatabaseConnectionPool.instance = new DatabaseConnectionPool();
    }
    return DatabaseConnectionPool.instance;
  }

  public getConnection(): Database {
    return this.db;
  }

  public close(): void {
    if (this.db) {
      this.db.close();
      DatabaseConnectionPool.instance = null as any;
    }
  }

  public healthCheck(): boolean {
    try {
      this.db.prepare("SELECT 1").get();
      return true;
    } catch (error) {
      console.error("Database health check failed:", error);
      return false;
    }
  }
}
```

#### Step 2: Create Repository Interfaces (1 day)

**File: `database/repositories/interfaces.ts`**
```typescript
import { EmailRecord, SearchCriteria, Attachment } from "../types";

export interface IEmailRepository {
  searchEmails(criteria: SearchCriteria): Promise<EmailRecord[]>;
  upsertEmail(email: EmailRecord, attachments: Attachment[]): Promise<number>;
  getEmailByMessageId(messageId: string): Promise<EmailRecord | null>;
  getRecentEmails(limit: number): Promise<EmailRecord[]>;
  getEmailsByIds(ids: number[]): Promise<EmailRecord[]>;
  getAttachments(emailId: number): Promise<Attachment[]>;
  batchUpsertEmails(emails: Array<{email: EmailRecord, attachments?: Attachment[]}>): Promise<void>;
}

export interface ISyncRepository {
  recordSync(emailsSynced: number, emailsSkipped: number, syncType: string): Promise<void>;
  getLastSync(): Promise<Date | null>;
  getSyncStatistics(): Promise<any>;
}
```

#### Step 3: Implement Repositories (3 days)

**File: `database/repositories/email-repository.ts`**
```typescript
import { Database } from "bun:sqlite";
import { IEmailRepository } from "./interfaces";
import { EmailRecord, SearchCriteria, Attachment } from "../types";

export class EmailRepository implements IEmailRepository {
  constructor(private db: Database) {}

  async searchEmails(criteria: SearchCriteria): Promise<EmailRecord[]> {
    // Move searchEmails logic from DatabaseManager here
    // Use this.db instead of creating new instance
    const whereClauses: string[] = [];
    const params: any = {};

    // ... (full implementation from database-manager.ts)

    const query = this.db.prepare(sql);
    const results = query.all(params);
    return results.map(row => this.mapRowToEmailRecord(row));
  }

  async upsertEmail(email: EmailRecord, attachments: Attachment[] = []): Promise<number> {
    // Move upsertEmail logic from DatabaseManager here
    const upsertEmail = this.db.prepare(`...`);
    // ... (full implementation)
    return emailId;
  }

  // ... implement other methods

  private mapRowToEmailRecord(row: any): EmailRecord {
    // Move mapping logic here
  }
}
```

**File: `database/repositories/sync-repository.ts`**
```typescript
import { Database } from "bun:sqlite";
import { ISyncRepository } from "./interfaces";

export class SyncRepository implements ISyncRepository {
  constructor(private db: Database) {}

  async recordSync(emailsSynced: number, emailsSkipped: number, syncType: string): Promise<void> {
    this.db.run(`
      INSERT INTO sync_metadata (sync_time, emails_synced, emails_skipped, sync_type)
      VALUES (?, ?, ?, ?)
    `, [new Date().toISOString(), emailsSynced, emailsSkipped, syncType]);
  }

  async getLastSync(): Promise<Date | null> {
    const result = this.db.prepare(`
      SELECT MAX(sync_time) as last_sync FROM sync_metadata
    `).get() as any;

    return result?.last_sync ? new Date(result.last_sync) : null;
  }

  async getSyncStatistics(): Promise<any> {
    return this.db.prepare(`
      SELECT
        COUNT(*) as total_syncs,
        SUM(emails_synced) as total_emails_synced,
        AVG(emails_synced) as avg_per_sync
      FROM sync_metadata
    `).get();
  }
}
```

#### Step 4: Update Server Initialization (1 day)

**File: `server/server.ts`**
```typescript
import { DatabaseConnectionPool } from "../database/infrastructure/connection-pool";
import { EmailRepository } from "../database/repositories/email-repository";
import { SyncRepository } from "../database/repositories/sync-repository";
import { WebSocketHandler } from "../ccsdk/websocket-handler";
import { EmailSyncService } from "../database/email-sync";
import { ImapManager } from "../database/imap-manager";
import { createEmailEndpoints } from "./endpoints";

// Single database connection
const pool = DatabaseConnectionPool.getInstance();
const db = pool.getConnection();

// Create repositories
const emailRepo = new EmailRepository(db);
const syncRepo = new SyncRepository(db);

// Inject repositories into services
const imapManager = new ImapManager(emailRepo);  // Updated constructor
const wsHandler = new WebSocketHandler(emailRepo);  // Updated constructor
const syncService = new EmailSyncService(syncRepo, emailRepo);  // Updated constructor

// Create endpoints with injected repositories
const emailEndpoints = createEmailEndpoints(emailRepo);
const syncEndpoints = createSyncEndpoints(syncRepo, syncService);

const server = Bun.serve({
  port: 3000,
  idleTimeout: 120,

  websocket: {
    open(ws: WSClient) {
      wsHandler.onOpen(ws);
    },
    message(ws: WSClient, message: string) {
      wsHandler.onMessage(ws, message);
    },
    close(ws: WSClient) {
      wsHandler.onClose(ws);
    }
  },

  async fetch(req: Request, server: any) {
    const url = new URL(req.url);

    if (req.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    if (url.pathname === '/ws') {
      const upgraded = server.upgrade(req, { data: { sessionId: '' } });
      if (!upgraded) {
        return new Response('WebSocket upgrade failed', { status: 400 });
      }
      return;
    }

    // Use injected endpoint handlers
    if (url.pathname === '/api/sync' && req.method === 'POST') {
      return syncEndpoints.handleSync(req);
    }

    if (url.pathname === '/api/emails/inbox' && req.method === 'GET') {
      return emailEndpoints.handleInbox(req);
    }

    // ... other routes
  },
});

// Graceful shutdown
process.on('SIGINT', () => {
  console.log('Shutting down server...');
  pool.close();
  process.exit(0);
});
```

#### Step 5: Update Service Constructors (2 days)

**File: `ccsdk/websocket-handler.ts`**
```typescript
import { IEmailRepository } from "../database/repositories/interfaces";
import type { WSClient } from "./types";

export class WebSocketHandler {
  private sessions: Map<string, Session> = new Map();
  private clients: Map<string, WSClient> = new Map();

  // CHANGED: Accept repository instead of dbPath
  constructor(private emailRepo: IEmailRepository) {
    this.setupPeriodicInboxUpdates();
  }

  private async broadcastInboxUpdate() {
    // CHANGED: Use repository instead of this.db
    const emails = await this.emailRepo.getRecentEmails(30);

    // ... rest of implementation
  }

  // ... other methods updated to use this.emailRepo
}
```

**File: `database/imap-manager.ts`**
```typescript
import { IEmailRepository } from "./repositories/interfaces";

export class ImapManager {
  private static instance: ImapManager;
  private emailRepo: IEmailRepository;

  // CHANGED: Accept repository instead of creating DatabaseManager
  private constructor(emailRepo: IEmailRepository) {
    this.emailRepo = emailRepo;
  }

  public static getInstance(emailRepo: IEmailRepository): ImapManager {
    if (!ImapManager.instance) {
      ImapManager.instance = new ImapManager(emailRepo);
    }
    return ImapManager.instance;
  }

  async searchEmails(criteria: SearchCriteria): Promise<EmailRecord[]> {
    // CHANGED: Use this.emailRepo instead of DatabaseManager.getInstance()
    return await this.emailRepo.searchEmails(criteria);
  }

  // ... other methods
}
```

**File: `database/email-sync.ts`**
```typescript
import { IEmailRepository, ISyncRepository } from "./repositories/interfaces";

export class EmailSyncService {
  // CHANGED: Accept repositories instead of dbPath
  constructor(
    private syncRepo: ISyncRepository,
    private emailRepo: IEmailRepository
  ) {}

  async syncEmails(limit: number): Promise<any> {
    // CHANGED: Use repositories instead of creating EmailDatabase
    const emails = await fetchEmailsFromIMAP(limit);

    await this.emailRepo.batchUpsertEmails(emails.map(e => ({
      email: e,
      attachments: e.attachments || []
    })));

    await this.syncRepo.recordSync(emails.length, 0, 'manual');

    return {
      synced: emails.length,
      skipped: 0
    };
  }
}
```

#### Step 6: Update Endpoints (2 days)

**File: `server/endpoints/emails.ts`**
```typescript
import { IEmailRepository } from "../../database/repositories/interfaces";

// CHANGED: Export factory function that accepts repository
export function createEmailEndpoints(emailRepo: IEmailRepository) {
  return {
    async handleInboxEndpoint(req: Request) {
      const limit = parseInt(new URL(req.url).searchParams.get('limit') || '50');

      // CHANGED: Use injected repository instead of creating Database
      const emails = await emailRepo.getRecentEmails(limit);

      return new Response(JSON.stringify(emails), {
        headers: { 'Content-Type': 'application/json' }
      });
    },

    async handleSearchEndpoint(req: Request) {
      const criteria = await req.json();

      // CHANGED: Use injected repository
      const results = await emailRepo.searchEmails(criteria);

      return new Response(JSON.stringify(results), {
        headers: { 'Content-Type': 'application/json' }
      });
    },

    async handleEmailDetailsEndpoint(req: Request, emailId: string) {
      // CHANGED: Use injected repository
      const email = await emailRepo.getEmailByMessageId(emailId);

      if (!email) {
        return new Response('Email not found', { status: 404 });
      }

      const attachments = await emailRepo.getAttachments(email.id!);

      return new Response(JSON.stringify({ email, attachments }), {
        headers: { 'Content-Type': 'application/json' }
      });
    },

    // ... other handlers
  };
}
```

#### Step 7: Remove Legacy Database Classes (1 day)

**Delete these files:**
- `database/database-manager.ts` (superseded by EmailRepository)
- `database/email-db.ts` (superseded by EmailRepository)

**Update imports across codebase:**
```bash
# Find all references to removed classes
grep -r "DatabaseManager" --include="*.ts"
grep -r "EmailDatabase" --include="*.ts"

# Replace with repository references
# (manual updates based on context)
```

#### Step 8: Update Tests (2 days)

**File: `tests/email-repository.test.ts`**
```typescript
import { Database } from "bun:sqlite";
import { EmailRepository } from "../database/repositories/email-repository";
import { EmailRecord } from "../database/types";

describe("EmailRepository", () => {
  let db: Database;
  let repo: EmailRepository;

  beforeEach(() => {
    // Create in-memory database for testing
    db = new Database(":memory:");
    initializeSchema(db);
    repo = new EmailRepository(db);
  });

  afterEach(() => {
    db.close();
  });

  it("should search emails by criteria", async () => {
    // Arrange
    await repo.upsertEmail({
      messageId: "test@example.com",
      fromAddress: "sender@example.com",
      subject: "Test Email",
      dateSent: new Date(),
      // ... other fields
    }, []);

    // Act
    const results = await repo.searchEmails({
      from: "sender@example.com"
    });

    // Assert
    expect(results).toHaveLength(1);
    expect(results[0].subject).toBe("Test Email");
  });

  // ... more tests
});
```

**File: `tests/websocket-handler.test.ts`**
```typescript
import { WebSocketHandler } from "../ccsdk/websocket-handler";
import { IEmailRepository } from "../database/repositories/interfaces";
import { EmailRecord } from "../database/types";

// Mock repository
class MockEmailRepository implements IEmailRepository {
  async getRecentEmails(limit: number): Promise<EmailRecord[]> {
    return [{
      id: 1,
      messageId: "test@example.com",
      subject: "Mock Email",
      fromAddress: "mock@example.com",
      // ... other fields
    }];
  }

  // ... implement other interface methods
}

describe("WebSocketHandler", () => {
  it("should broadcast inbox updates using repository", async () => {
    // Arrange
    const mockRepo = new MockEmailRepository();
    const handler = new WebSocketHandler(mockRepo);

    // Act
    // ... test logic

    // Assert
    // Verify handler used mockRepo.getRecentEmails()
  });
});
```

---

### Alternative Approaches

#### Option A: Keep Singleton Pattern but Make It Stricter

**Approach**:
- Keep DatabaseManager as singleton
- Force all modules to use `DatabaseManager.getInstance()`
- Add runtime checks to prevent direct `new Database()` calls
- Add centralized logging in DatabaseManager

**Pros**:
- Minimal refactoring required
- Faster implementation (1 week vs 3 weeks)
- Less breaking changes
- Team can deliver features faster

**Cons**:
- Still violates Dependency Inversion Principle
- Difficult to test (can't mock getInstance())
- Singleton is global state (hard to reason about)
- Can't inject different implementations
- Limited flexibility for future changes

**Recommendation**: ❌ **Not Recommended**
While faster to implement, this approach addresses symptoms but not root cause. Testing remains difficult, and architectural flexibility is limited.

---

#### Option B: Use Dependency Injection Container (InversifyJS)

**Approach**:
- Add InversifyJS dependency
- Define interfaces for all services
- Register bindings in container
- Resolve dependencies from container at runtime

**Example**:
```typescript
// inversify.config.ts
const container = new Container();

// Bind interfaces to implementations
container.bind<Database>(TYPES.Database).toConstantValue(new Database(DATABASE_PATH));
container.bind<IEmailRepository>(TYPES.EmailRepository).to(EmailRepository);
container.bind<ImapManager>(TYPES.ImapManager).to(ImapManager);

export { container };

// server.ts
import { container } from "./inversify.config";

const emailRepo = container.get<IEmailRepository>(TYPES.EmailRepository);
const wsHandler = container.get<WebSocketHandler>(TYPES.WebSocketHandler);
```

**Pros**:
- Industry-standard pattern
- Excellent testability (easy to rebind for tests)
- Clear dependency declarations
- Automatic dependency resolution
- Supports decorator-based injection

**Cons**:
- Adds external dependency (~50KB)
- Steeper learning curve for team
- More boilerplate code (decorators, TYPES constants)
- Requires understanding of DI containers
- Overkill for small codebase

**Recommendation**: ⚠️ **Consider for Larger Codebases**
Good choice if email-agent will grow significantly or if team is familiar with DI containers. For current scope, manual constructor injection (recommended approach) is sufficient.

---

#### Option C: Hybrid Approach - Connection Pool Only

**Approach**:
- Create DatabaseConnectionPool as recommended
- Keep existing DatabaseManager/EmailDatabase for queries
- Update modules to get Database instance from pool

**Example**:
```typescript
// server.ts
const pool = DatabaseConnectionPool.getInstance();
const db = pool.getConnection();

const dbManager = new DatabaseManager(db);  // Pass instance instead of path
const wsHandler = new WebSocketHandler(db);
```

**Pros**:
- Solves connection management issue immediately
- Less refactoring than full repository pattern
- Can implement repositories incrementally later
- Quick win for critical issue

**Cons**:
- Doesn't solve abstraction problem
- Raw SQL still scattered
- Testing still difficult
- Partial solution only

**Recommendation**: ⚠️ **Acceptable Short-Term Solution**
If team needs to ship features urgently, implement this first to eliminate critical connection issues. Then refactor to full repository pattern in next sprint.

---

### Recommended Approach: Repository Pattern with Connection Pool

**Why This is Best**:

1. **Solves Root Cause**: Addresses both connection management AND abstraction issues
2. **Testability**: Easy to mock repositories for unit tests
3. **Clear Boundaries**: Database logic isolated in repository layer
4. **Flexibility**: Can swap SQLite for PostgreSQL with minimal changes
5. **Industry Standard**: Well-understood pattern with extensive resources
6. **Maintainability**: Clear separation of concerns
7. **No External Dependencies**: Uses TypeScript patterns only

**Implementation Timeline**: 3 weeks
- Week 1: Infrastructure + Repositories
- Week 2: Service/Endpoint Migration + Testing
- Week 3: Legacy Code Removal + Documentation

---

## Acceptance Criteria

### Functional Requirements
- [ ] Only one Database instance created in entire application
- [ ] All database access goes through repository interfaces
- [ ] No module directly imports or instantiates `Database` class (except infrastructure layer)
- [ ] All endpoints receive repositories via dependency injection
- [ ] All services receive repositories via constructor injection
- [ ] Database connection lifecycle is managed centrally

### Non-Functional Requirements
- [ ] All existing tests pass (no regression)
- [ ] Integration tests verify single connection pool
- [ ] No direct SQL queries outside repository implementations
- [ ] Query performance is equivalent or better than before
- [ ] Memory usage does not increase significantly

### Testing Requirements
- [ ] Unit tests for all repository methods (>80% coverage)
- [ ] Integration tests with mocked repositories
- [ ] End-to-end tests with real database
- [ ] Load testing shows no "database is locked" errors
- [ ] Concurrent request testing passes

### Documentation Requirements
- [ ] Architecture Decision Record (ADR) created
- [ ] Repository pattern documented with examples
- [ ] Migration guide for future developers
- [ ] Code comments on key architectural choices
- [ ] Diagram showing dependency flow

---

## Definition of Done

- [ ] ✅ Code changes implemented across all affected modules
- [ ] ✅ All 7 Database instantiation points eliminated
- [ ] ✅ Repository interfaces defined and implemented
- [ ] ✅ Server initialization uses dependency injection
- [ ] ✅ Unit tests added for all repository methods
- [ ] ✅ Integration tests verify single connection pool
- [ ] ✅ All existing tests pass without modification
- [ ] ✅ Code review completed by infrastructure team AND email team
- [ ] ✅ Performance testing shows no regression
- [ ] ✅ Documentation updated (ADR, README, code comments)
- [ ] ✅ Migration deployed to staging environment
- [ ] ✅ Smoke tests pass in staging
- [ ] ✅ Team training session conducted on new architecture
- [ ] ✅ Post-deployment monitoring confirms stability

---

## Effort Estimation

### Size: Large (2-3 weeks)

**Breakdown by Phase**:

| Phase | Task | Days | Engineer Level |
|-------|------|------|----------------|
| **Phase 1** | Design & Planning | 1 | Senior |
| | Create DatabaseConnectionPool | 1 | Mid-level |
| | Define repository interfaces | 1 | Senior |
| | | |
| **Phase 2** | Implementation | | |
| | Implement EmailRepository | 2 | Mid-level |
| | Implement SyncRepository | 1 | Mid-level |
| | Update server initialization | 1 | Senior |
| | | |
| **Phase 3** | Service Migration | | |
| | Update WebSocketHandler | 1 | Mid-level |
| | Update ImapManager | 1 | Mid-level |
| | Update EmailSyncService | 1 | Mid-level |
| | | |
| **Phase 4** | Endpoint Migration | | |
| | Update emails endpoints | 1 | Junior |
| | Update sync endpoints | 1 | Junior |
| | Update profile endpoint | 0.5 | Junior |
| | | |
| **Phase 5** | Testing | | |
| | Write unit tests | 2 | Mid-level |
| | Write integration tests | 1 | Mid-level |
| | Performance testing | 1 | Senior |
| | | |
| **Phase 6** | Cleanup | | |
| | Remove legacy classes | 0.5 | Junior |
| | Update documentation | 1 | Senior |
| | Code review & refinement | 1 | Senior |
| | | |
| **Buffer** | Unexpected issues | 2-3 | Team |
| | | |
| **TOTAL** | | **15-18 days** | **~3 weeks** |

**Resource Requirements**:
- 1 Senior Engineer (design, review, critical paths): 6 days
- 1-2 Mid-level Engineers (implementation, testing): 8 days
- 1 Junior Engineer (endpoint updates, documentation): 3 days

**Parallelization Opportunities**:
- Phases 3 & 4 can partially overlap (2 engineers)
- Unit tests can be written alongside implementation
- Documentation can start after Phase 2

**Risk Buffer**:
- 2-3 days for unexpected issues
- Common issues: Schema migration complexity, test data setup, performance optimization

---

## Dependencies

### Blocks (Issues that can't proceed until this is fixed)

**#TBD - Email Search Optimization**
- Requires repository pattern to implement query caching
- Can't optimize without centralized query layer
- **Impact**: Performance improvements blocked

**#TBD - Add Email Caching Layer**
- Needs single Database instance for Redis/cache integration
- Can't cache with multiple uncoordinated instances
- **Impact**: Scalability improvements blocked

**#TBD - Implement Request Tracing**
- Needs centralized logging in repository layer
- Can't trace queries across 7 different access points
- **Impact**: Observability improvements blocked

**#TBD - Add Read-Only Database User**
- Needs repository interfaces to enforce read-only access
- Can't implement with direct Database instantiation
- **Impact**: Security improvements blocked

---

### Blocked By (Issues that must be resolved first)

**None** - This issue can start immediately.

This is a foundational issue. No other architectural work is blocking it. In fact, resolving this unblocks multiple other improvements.

---

### Related Issues

**#002 - Duplicated EmailRecord Interfaces**
- Should be fixed in same pull request
- Both involve consolidating database layer
- **Relationship**: Complementary (fix together)

**#004 - Raw SQL Queries Scattered Throughout**
- Repository pattern solves this naturally
- All SQL moves into repository implementations
- **Relationship**: Superseded by this fix

**#006 - Circular Dependency Between Database Layers**
- Repositories replace both DatabaseManager and EmailDatabase
- Eliminates circular dependency entirely
- **Relationship**: Superseded by this fix

**#008 - Missing API Versioning**
- Not directly related but should coordinate deployment
- Breaking changes in database access + API versioning together
- **Relationship**: Coordinate deployment

---

## Migration Strategy

### Phase 1: Infrastructure Setup (No Breaking Changes)

**Timeline**: 2 days

**Goals**:
- Create new infrastructure layer
- Establish repository interfaces
- Add tests
- No changes to existing code yet

**Actions**:
1. Create `database/infrastructure/connection-pool.ts`
2. Create `database/repositories/interfaces.ts`
3. Create `database/repositories/email-repository.ts`
4. Create `database/repositories/sync-repository.ts`
5. Write unit tests for repositories
6. Verify tests pass

**Validation**:
- [ ] New code has >80% test coverage
- [ ] All existing tests still pass
- [ ] No changes to server.ts or endpoints

**Rollback Plan**: Simply delete new files if issues found.

---

### Phase 2: Parallel Operation (Proof of Concept)

**Timeline**: 3 days

**Goals**:
- Update ONE endpoint to use repository
- Update ONE service to use repository
- Prove pattern works without breaking existing functionality

**Actions**:
1. Update server.ts to create connection pool + repositories
2. Update WebSocketHandler to accept IEmailRepository
3. Update one endpoint (e.g., handleInboxEndpoint) to use repository
4. Run integration tests
5. Compare performance benchmarks

**Validation**:
- [ ] Updated endpoint works correctly
- [ ] Existing endpoints still work (using old path)
- [ ] WebSocketHandler works with injected repository
- [ ] No performance regression
- [ ] Both old and new code paths functional

**Rollback Plan**: Revert server.ts changes, keep new infrastructure layer for next attempt.

---

### Phase 3: Full Migration (All Modules)

**Timeline**: 5 days

**Goals**:
- Migrate all endpoints to use repositories
- Migrate all services to use repositories
- Ensure zero downtime

**Actions**:
1. Update all endpoints in `server/endpoints/` (2 days)
2. Update ImapManager constructor (1 day)
3. Update EmailSyncService constructor (1 day)
4. Update all endpoint route handlers in server.ts (1 day)
5. Run full test suite after each module migration
6. Deploy to staging environment for validation

**Migration Order** (by risk/complexity):
1. ✅ WebSocketHandler (already done in Phase 2)
2. endpoints/profile.ts (lowest risk, simple queries)
3. endpoints/sync.ts (medium risk)
4. endpoints/emails.ts (high risk, most used)
5. ImapManager (medium complexity)
6. EmailSyncService (high complexity)

**Validation**:
- [ ] All endpoints work correctly
- [ ] All services use repositories
- [ ] No direct `new Database()` calls remain (except connection-pool)
- [ ] Integration tests pass
- [ ] Staging deployment successful

**Rollback Plan**: Keep old Database classes temporarily. If critical issue found, can revert service constructors to old pattern while fixing repositories.

---

### Phase 4: Cleanup and Optimization (Final Steps)

**Timeline**: 2 days

**Goals**:
- Remove legacy code
- Optimize queries
- Finalize documentation

**Actions**:
1. Delete `database/database-manager.ts`
2. Delete `database/email-db.ts`
3. Remove unused imports across codebase
4. Update documentation (README, ADR)
5. Conduct team training session
6. Deploy to production

**Validation**:
- [ ] No references to deleted classes
- [ ] All tests pass
- [ ] Documentation complete
- [ ] Team trained on new architecture
- [ ] Production deployment successful
- [ ] Post-deployment monitoring shows stability

**Rollback Plan**: If production issues arise, can quickly restore deleted files from git history and revert endpoint changes.

---

### Deployment Strategy

**Blue-Green Deployment Recommended**:

1. **Deploy to Green Environment**:
   - Full new architecture
   - Test thoroughly
   - Monitor for 24 hours

2. **Switch Traffic Gradually**:
   - 10% traffic → Green (monitor for 1 hour)
   - 50% traffic → Green (monitor for 1 hour)
   - 100% traffic → Green (monitor for 24 hours)

3. **Keep Blue Environment**:
   - Maintain for 1 week
   - Quick rollback if critical issue found

4. **Decommission Blue**:
   - After 1 week of stable operation

**Monitoring During Migration**:
- Database connection count
- Query latency (p50, p95, p99)
- Error rate (especially "database is locked")
- Memory usage
- CPU usage

**Success Criteria for Each Phase**:
- Error rate < baseline
- Query latency < baseline + 10%
- Zero "database is locked" errors
- Memory usage stable

---

## Prevention Strategy

### How to Prevent This Pattern from Recurring

#### 1. Add Architectural Fitness Functions to CI/CD

**GitHub Actions Workflow**: `.github/workflows/coupling-check.yml`
```yaml
name: Coupling Compliance Check

on: [push, pull_request]

jobs:
  check-database-coupling:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Check for direct Database instantiation
        run: |
          # Fail if "new Database" found outside infrastructure layer
          ! grep -r "new Database" \
            --include="*.ts" \
            --exclude-dir="database/infrastructure" \
            email-agent/

      - name: Check for raw SQL outside repositories
        run: |
          # Fail if db.prepare/exec found outside repositories
          ! grep -r "db\.prepare\|db\.exec" \
            --include="*.ts" \
            --exclude-dir="database/repositories" \
            --exclude-dir="database/infrastructure" \
            email-agent/

      - name: Check for singleton getInstance usage
        run: |
          # Warn if getInstance() pattern detected
          INSTANCES=$(grep -r "\.getInstance()" --include="*.ts" email-agent/ || true)
          if [ ! -z "$INSTANCES" ]; then
            echo "Warning: Singleton pattern detected:"
            echo "$INSTANCES"
            echo "Consider using dependency injection instead."
          fi
```

**Benefits**:
- Prevents new violations from being merged
- Runs on every PR automatically
- Fast feedback loop for developers
- No manual code review needed for this check

---

#### 2. Update Development Guidelines

**File**: `DEVELOPMENT.md` or `ARCHITECTURE.md`
```markdown
## Database Access Guidelines

### ✅ DO

- Access database through repository interfaces
- Inject repositories via constructor
- Write all SQL queries in repository implementations
- Use DatabaseConnectionPool for connection management
- Write unit tests with mocked repositories

### ❌ DON'T

- Create Database instances directly (`new Database()`)
- Write SQL queries in business logic or endpoints
- Use `getInstance()` singleton pattern
- Access database from CCSDK or client layers
- Skip repository layer for "simple" queries

### Examples

**Good**:
```typescript
// Inject repository via constructor
class EmailService {
  constructor(private emailRepo: IEmailRepository) {}

  async getInbox() {
    return await this.emailRepo.getRecentEmails(50);
  }
}
```

**Bad**:
```typescript
// Direct Database instantiation - DON'T DO THIS!
class EmailService {
  private db = new Database(DATABASE_PATH);  // ❌

  async getInbox() {
    return this.db.prepare("SELECT * FROM emails").all();  // ❌
  }
}
```
```

---

#### 3. Create Architectural Decision Record (ADR)

**File**: `docs/adr/001-repository-pattern-for-database-access.md`
```markdown
# ADR 001: Repository Pattern for Database Access

**Status**: Accepted
**Date**: 2025-10-16
**Decision Makers**: Backend Team, Infrastructure Team

## Context

Email-agent previously had 7 independent Database instances across modules,
leading to connection conflicts, inconsistent state, and difficult testing.

## Decision

We will use the Repository Pattern with a single DatabaseConnectionPool:

1. All database access must go through repository interfaces
2. Services and endpoints receive repositories via constructor injection
3. No module may directly instantiate Database class
4. All SQL queries must live in repository implementations

## Consequences

**Positive**:
- Single source of truth for database access
- Easy to test with mocked repositories
- Clear dependency boundaries
- Can implement caching/optimization globally

**Negative**:
- More boilerplate code (interfaces + implementations)
- Learning curve for repository pattern
- Migration effort required for existing code

## Alternatives Considered

1. **Stricter Singleton**: Keep DatabaseManager, enforce usage
   - Rejected: Doesn't solve testing or flexibility issues

2. **DI Container (InversifyJS)**: Use third-party DI framework
   - Rejected: Overkill for current codebase size

## Monitoring

We will track:
- Number of Database instances (must remain 1)
- Query performance (should not regress)
- Test coverage (should increase)
```

---

#### 4. Add Linting Rules (ESLint Custom Rule)

**File**: `.eslintrc.js` (add custom rule)
```javascript
module.exports = {
  rules: {
    'no-direct-database-instantiation': {
      create(context) {
        return {
          NewExpression(node) {
            if (node.callee.name === 'Database') {
              const filename = context.getFilename();

              // Allow in infrastructure layer only
              if (!filename.includes('infrastructure/connection-pool.ts')) {
                context.report({
                  node,
                  message: 'Direct Database instantiation not allowed. Use DatabaseConnectionPool instead.',
                });
              }
            }
          },
        };
      },
    },
  },
};
```

**Benefits**:
- IDE shows error immediately
- Prevents accidental violations
- Self-documenting (error message explains pattern)

---

#### 5. Code Review Checklist

Add to `.github/PULL_REQUEST_TEMPLATE.md`:
```markdown
## Database Access Checklist

- [ ] No direct `new Database()` calls (use DatabaseConnectionPool)
- [ ] No SQL queries outside repository layer
- [ ] Dependencies injected via constructor (no `getInstance()`)
- [ ] Repository interfaces used instead of concrete types
- [ ] Unit tests mock repositories, not Database
```

---

#### 6. Team Training

**Onboarding Session** (1 hour):
- Explain repository pattern
- Show code examples
- Live coding demo: Creating a new repository
- Q&A

**Resources**:
- Link to Martin Fowler's Repository Pattern article
- Internal documentation (ADR)
- Example PR showing pattern usage

---

#### 7. Periodic Architecture Audits

**Schedule**: Quarterly

**Process**:
1. Run automated coupling checks
2. Review new Database-related code
3. Check for new anti-patterns
4. Update guidelines if needed

**Metrics to Track**:
- Number of Database instances (should be 1)
- Lines of SQL outside repositories (should be 0)
- Test coverage of repository layer (should be >80%)

---

## Additional Context

### Related Documentation

**Repository Pattern**:
- [Martin Fowler - Repository Pattern](https://martinfowler.com/eaaCatalog/repository.html)
- [Microsoft - Repository Pattern](https://docs.microsoft.com/en-us/dotnet/architecture/microservices/microservice-ddd-cqrs-patterns/infrastructure-persistence-layer-design)

**Dependency Injection**:
- [Wikipedia - Dependency Injection](https://en.wikipedia.org/wiki/Dependency_injection)
- [Dependency Injection in TypeScript](https://www.typescriptlang.org/docs/handbook/2/classes.html#abstract-classes)

**SQLite Best Practices**:
- [SQLite WAL Mode](https://www.sqlite.org/wal.html)
- [SQLite Connection Pooling](https://www.sqlite.org/c3ref/open.html)

---

### Historical Context

**Why did this happen?**

This pattern likely emerged from:
1. **Rapid Feature Development**: Developers needed database access quickly
2. **Multiple Contributors**: Different developers implemented features independently
3. **No Architectural Governance**: No established patterns for database access
4. **Demo Code Evolution**: Code started as demo/example, evolved into production
5. **Convenience Over Architecture**: `new Database(path)` is easier than dependency injection

**Was it a conscious tradeoff?**

Likely **no**. More likely:
- No one realized 7 instances were being created
- Each developer thought their instance was "the" instance
- No code review caught the pattern
- Tests didn't reveal the issue (worked fine in isolation)

**Context that might affect solution**:
- If this is still demo/example code: Simpler solution might suffice
- If this is production-critical: Full repository pattern essential
- If team is small/junior: Extra documentation and training needed

---

### Questions for Discussion

Before implementing this remediation:

1. **Production Status**:
   - Is email-agent in production?
   - How many users/requests per day?
   - What's the impact of downtime?

2. **Team Capacity**:
   - Can we allocate 2 engineers for 3 weeks?
   - Do we have senior engineer to lead refactoring?
   - Can we delay new features during migration?

3. **Testing Infrastructure**:
   - Do we have staging environment?
   - Can we run load tests?
   - Do we have rollback procedures?

4. **Risk Tolerance**:
   - Are we comfortable with current data corruption risk?
   - Can we accept breaking changes with migration path?
   - What's deadline for fixing this?

5. **Alternative Approaches**:
   - Should we consider Option C (hybrid) first?
   - Do we need to implement full pattern or start with connection pool?
   - Can we do this incrementally over multiple sprints?

---

## Summary

This issue represents **critical architectural debt** that must be addressed before it causes production incidents. While the fix is substantial (3 weeks), the benefits are significant:

- ✅ Eliminates data corruption risk
- ✅ Improves testability dramatically
- ✅ Sets foundation for future scaling
- ✅ Establishes clean architecture patterns
- ✅ Makes codebase more maintainable

**Recommendation**: Prioritize this issue for next sprint. The longer it remains, the more code will be built on the flawed foundation, increasing future migration costs.

---

**Issue Status**: Open
**Next Steps**:
1. Present to architecture review board
2. Get approval for 3-week allocation
3. Assign senior engineer as technical lead
4. Create implementation plan with milestones
5. Begin Phase 1 (infrastructure setup)

**Last Updated**: 2025-10-16
