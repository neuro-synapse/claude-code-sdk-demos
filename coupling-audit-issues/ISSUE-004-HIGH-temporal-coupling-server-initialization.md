# [COUPLING] [HIGH]: Temporal coupling in email-agent server initialization

## Problem Statement

The email-agent server initialization has implicit order dependencies where database managers and services must be initialized in a specific sequence, but this ordering is not enforced or documented. The server creates multiple database connections and singleton instances with hidden initialization dependencies, creating temporal coupling that can cause race conditions or initialization failures.

## Current State

**Location**:
- File: `email-agent/server/server.ts:18-34`
- Owner: email-agent service team

**Coupling Type**: Temporal (order dependency)
**Degree**: Implicit execution sequence required but not enforced

**Evidence**:
```typescript
// server/server.ts:18-34
const wsHandler = new WebSocketHandler(DATABASE_PATH);  // Line 18: Creates DB connection
const db = new Database(DATABASE_PATH);                  // Line 19: ANOTHER DB connection!

const dbManager = DatabaseManager.getInstance();         // Line 21: Singleton #1
const imapManager = ImapManager.getInstance();           // Line 22: Singleton #2

db.run(`CREATE TABLE IF NOT EXISTS sync_metadata...`);   // Line 24: Direct DB manipulation

const syncService = new EmailSyncService(DATABASE_PATH); // Line 34: THIRD DB connection
```

**Problems**:
1. Three separate Database instances created for same file (lines 18, 19, 34 via services)
2. No guaranteed initialization order for singletons
3. Direct SQL execution before singleton initialization
4. WebSocketHandler may access database before schema is ready
5. No error handling for initialization failures

## Impact Assessment

**Severity**: HIGH

**Why This Matters**:
- **Race Conditions**: WebSocket connections may arrive before database is initialized
- **SQLite Locking**: Multiple connections can cause "database is locked" errors
- **Initialization Failures**: Order-dependent code fails in unpredictable ways
- **Testing Difficulty**: Tests must mock initialization in exact order
- **Deployment Risk**: Server may partially initialize and accept requests before ready

**Blast Radius**:
- Modules affected: 5 (server, websocket-handler, database-manager, imap-manager, email-sync)
- Teams affected: 1 (email-agent team)
- Deployment coupling: High - server won't start reliably

**Risk Factors**:
- Change frequency: LOW - server initialization rarely changes
- Failure probability: MEDIUM - works most of the time, fails under load
- Detection difficulty: HARD - only fails in production under specific conditions

## Current Behavior vs. Expected Behavior

**Current**: Server initialization creates multiple database connections in undefined order with implicit dependencies, leading to potential race conditions and initialization failures.

**Expected**: Explicit initialization sequence with dependency injection, single database connection, and health checks before accepting traffic.

**Violated Principle(s)**:
- Explicit Dependencies - order requirements are hidden
- Fail-Fast - no validation that initialization succeeded
- Single Responsibility - server.ts doing too much

## Remediation Plan

### Recommended Solution

Create explicit initialization lifecycle with dependency injection and health checks.

**Design Strategy**:
1. Create central application container that manages initialization order
2. Use single database connection shared across all services
3. Implement explicit dependency injection
4. Add health check endpoint that validates initialization
5. Don't accept traffic until fully initialized

### Specific Steps

1. **Step 1: Create application container with explicit lifecycle**
   ```typescript
   // server/app-container.ts
   export class ApplicationContainer {
     private db: Database | null = null;
     private dbManager: DatabaseManager | null = null;
     private imapManager: ImapManager | null = null;
     private syncService: EmailSyncService | null = null;
     private wsHandler: WebSocketHandler | null = null;
     private isInitialized = false;

     async initialize(): Promise<void> {
       try {
         // Step 1: Create single database connection
         console.log('1/5 Initializing database...');
         this.db = new Database(DATABASE_PATH);
         this.db.exec("PRAGMA journal_mode = WAL");

         // Step 2: Initialize database schema via singleton
         console.log('2/5 Initializing database manager...');
         this.dbManager = DatabaseManager.getInstance(DATABASE_PATH);

         // Step 3: Initialize sync metadata table
         console.log('3/5 Creating sync metadata...');
         this.db.run(`CREATE TABLE IF NOT EXISTS sync_metadata...`);

         // Step 4: Initialize IMAP manager
         console.log('4/5 Initializing IMAP manager...');
         this.imapManager = ImapManager.getInstance();

         // Step 5: Initialize services with shared DB connection
         console.log('5/5 Initializing services...');
         this.syncService = new EmailSyncService(DATABASE_PATH);
         this.wsHandler = new WebSocketHandler(DATABASE_PATH);

         this.isInitialized = true;
         console.log('✅ Application initialized successfully');
       } catch (error) {
         console.error('❌ Initialization failed:', error);
         throw error;  // Fail-fast
       }
     }

     isReady(): boolean {
       return this.isInitialized;
     }

     getDatabase(): Database {
       if (!this.db) throw new Error('Database not initialized');
       return this.db;
     }

     getWebSocketHandler(): WebSocketHandler {
       if (!this.wsHandler) throw new Error('WebSocket handler not initialized');
       return this.wsHandler;
     }

     // ... other getters
   }
   ```

2. **Step 2: Update server.ts to use container**
   ```typescript
   // server/server.ts
   import { ApplicationContainer } from './app-container';

   const container = new ApplicationContainer();

   // Initialize before starting server
   await container.initialize();

   const server = Bun.serve({
     port: 3000,

     async fetch(req: Request, server: any) {
       // Health check endpoint
       if (req.url.endsWith('/health')) {
         return new Response(
           JSON.stringify({
             status: container.isReady() ? 'healthy' : 'initializing',
             timestamp: new Date().toISOString()
           }),
           {
             status: container.isReady() ? 200 : 503,
             headers: { 'Content-Type': 'application/json' }
           }
         );
       }

       // Reject requests if not ready
       if (!container.isReady()) {
         return new Response('Service initializing, please retry', { status: 503 });
       }

       // ... rest of routing
     },

     websocket: {
       open(ws: WSClient) {
         if (!container.isReady()) {
           ws.close(1011, 'Service not ready');
           return;
         }
         container.getWebSocketHandler().onOpen(ws);
       },
       // ...
     }
   });
   ```

3. **Step 3: Refactor singletons to accept injected dependencies**
   ```typescript
   // database/database-manager.ts
   export class DatabaseManager {
     private static instance: DatabaseManager;

     // Accept optional database instance
     private constructor(
       private db: Database,
       dbPath: string = DATABASE_PATH
     ) {
       if (!db) {
         this.db = new Database(dbPath);
       }
       this.initializeDatabase();
     }

     public static getInstance(db?: Database): DatabaseManager {
       if (!DatabaseManager.instance) {
         if (!db) {
           throw new Error('First call must provide database instance');
         }
         DatabaseManager.instance = new DatabaseManager(db);
       }
       return DatabaseManager.instance;
     }
   }
   ```

4. **Step 4: Add graceful shutdown**
   ```typescript
   // server/app-container.ts
   async shutdown(): Promise<void> {
     console.log('Shutting down gracefully...');

     if (this.imapManager) {
       this.imapManager.disconnect();
     }

     if (this.db) {
       this.db.close();
     }

     this.isInitialized = false;
     console.log('✅ Shutdown complete');
   }

   // server/server.ts
   process.on('SIGTERM', async () => {
     await container.shutdown();
     process.exit(0);
   });
   ```

5. **Step 5: Add initialization tests**
   ```typescript
   // server/__tests__/initialization.test.ts
   describe('Application Initialization', () => {
     it('should initialize in correct order', async () => {
       const container = new ApplicationContainer();
       await container.initialize();

       expect(container.isReady()).toBe(true);
       expect(container.getDatabase()).toBeDefined();
       expect(container.getWebSocketHandler()).toBeDefined();
     });

     it('should reject requests before initialization', async () => {
       const container = new ApplicationContainer();
       expect(container.isReady()).toBe(false);
     });

     it('should handle initialization failures gracefully', async () => {
       // Mock database failure
       await expect(container.initialize()).rejects.toThrow();
     });
   });
   ```

### Alternative Approaches

**Option A**: Use dependency injection framework (InversifyJS, Tsyringe)
- Pros: Mature solution, handles complex dependency graphs
- Cons: Additional dependency, learning curve

**Option B**: Keep current approach, add better error handling
- Pros: Minimal changes
- Cons: Doesn't solve temporal coupling

**Option C**: Lazy initialization on first request
- Pros: Simpler startup
- Cons: First request pays initialization cost, harder to debug

**Recommendation**: Application Container pattern (described above) - explicit, testable, no external dependencies.

## Acceptance Criteria

- [ ] Single database connection shared across all services
- [ ] Explicit initialization order documented and enforced
- [ ] Health check endpoint returns initialization status
- [ ] Server rejects requests until fully initialized
- [ ] Graceful shutdown closes all resources
- [ ] Initialization failures cause server to exit (fail-fast)
- [ ] Tests validate initialization order

**Definition of Done**:
- [ ] ApplicationContainer implemented
- [ ] Server.ts refactored to use container
- [ ] Singletons accept dependency injection
- [ ] Health check endpoint implemented
- [ ] Graceful shutdown implemented
- [ ] Unit tests for initialization lifecycle
- [ ] Documentation updated
- [ ] ADR created: "Explicit Initialization Lifecycle"

## Effort Estimation

**Size**: Medium (1 week)

**Reasoning**:
- Pattern is straightforward but touches many files
- Need careful testing to avoid breaking existing functionality
- Refactoring singletons requires care

**Estimated Complexity**:
- ApplicationContainer: 1 day
- Server refactoring: 1 day
- Singleton refactoring: 2 days
- Testing: 2 days
- Documentation: 1 day

## Dependencies

**Blocks**:
- None

**Blocked By**:
- None (can start immediately)

**Related Issues**:
- ISSUE-001: Database intrusive coupling (will help solve this)

## Migration Strategy

**Phase 1**: Create ApplicationContainer without changing existing code
**Phase 2**: Add health check endpoint
**Phase 3**: Refactor server.ts to use container for new code paths
**Phase 4**: Gradually migrate existing code to use container
**Phase 5**: Remove old initialization code
**Phase 6**: Add initialization tests

## Prevention Strategy

- [ ] Add startup lifecycle documentation
- [ ] Code review checklist: "Are initialization dependencies explicit?"
- [ ] Add lint rule: "No new Database() in server.ts"
- [ ] Create service initialization template for new services
- [ ] ADR: "Service Initialization Best Practices"
- [ ] Share pattern in team training

## Additional Context

**Related Documentation**:
- Dependency Injection patterns
- Application lifecycle management
- SQLite concurrent access best practices

**Historical Context**:
- Current approach likely evolved organically
- Multiple database connections suggest lack of awareness of SQLite limitations
- Singletons added later without considering initialization order
- No initialization issues reported, but that's luck not design

**Questions for Discussion**:
- Should we use a DI framework or keep it simple?
- How do we handle initialization failures in production?
- Should health check block until ready or return "initializing" status?
- What's the acceptable startup time before timing out?
