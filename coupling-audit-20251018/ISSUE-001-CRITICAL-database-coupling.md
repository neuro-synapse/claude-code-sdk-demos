# [COUPLING] [CRITICAL]: Multiple Database instances bypass Singleton pattern in email-agent

**Issue ID**: COUPLING-001
**Severity**: Critical
**Type**: Intrusive Coupling / Resource Coupling
**Date Identified**: 2025-10-18
**Application**: email-agent

---

## Problem Statement

The email-agent creates multiple independent `Database` instances to access the same SQLite file, bypassing the Singleton `DatabaseManager` pattern. This creates resource coupling, potential lock contention, and architectural inconsistency that undermines the benefits of the Singleton pattern.

## Current State

**Location**:
- File(s):
  - `email-agent/server/endpoints/emails.ts:12`
  - `email-agent/ccsdk/websocket-handler.ts:17`
  - `email-agent/database/database-manager.ts:68-85` (Singleton pattern exists but bypassed)
- Module(s): server/endpoints, ccsdk, database
- Owner(s): email-agent team

**Coupling Type**: Intrusive Coupling / Resource Coupling
**Degree**: Direct resource access bypassing encapsulation boundary

**Evidence**:
```typescript
// email-agent/server/endpoints/emails.ts:12
const db = new Database(DATABASE_PATH);  // Direct instantiation
const dbManager = DatabaseManager.getInstance();  // Also using singleton!
const imapManager = ImapManager.getInstance();

// email-agent/ccsdk/websocket-handler.ts:16-17
constructor(dbPath: string = DATABASE_PATH) {
  this.db = new Database(dbPath);  // Another direct instantiation
  // ...
}

// email-agent/database/database-manager.ts:68-85
export class DatabaseManager {
  private static instance: DatabaseManager;  // Singleton pattern
  private db: Database;

  public static getInstance(dbPath?: string): DatabaseManager {
    if (!DatabaseManager.instance) {
      DatabaseManager.instance = new DatabaseManager(dbPath);
    }
    return DatabaseManager.instance;
  }
}
```

## Impact Assessment

**Severity**: Critical

**Why This Matters**:
- **Data integrity**: Multiple connections to SQLite can cause locking issues and write conflicts
- **Resource management**: Each Database instance consumes file handles and memory
- **Architectural consistency**: Undermines the Singleton pattern's purpose
- **Maintainability**: Mixed access patterns make the codebase confusing and error-prone

**Blast Radius**:
- Modules affected: 3 (server/endpoints, ccsdk/websocket-handler, database)
- Files with database access: 4+
- Pattern inconsistency across entire application

**Risk Factors**:
- Change frequency: High - database queries are frequently added/modified
- Failure probability: Medium - SQLite WAL mode mitigates but doesn't eliminate risks
- Detection difficulty: High - lock contention may be intermittent and hard to reproduce

## Current Behavior vs. Expected Behavior

**Current**: Mixed pattern with both direct `new Database()` instantiation and `DatabaseManager.getInstance()` usage, creating multiple connections to the same SQLite file.

**Expected**: All database access should go through the Singleton `DatabaseManager.getInstance()`, ensuring a single managed connection point.

**Violated Principle(s)**:
- **Single Responsibility Principle**: Direct Database usage spreads database connection management across modules
- **Encapsulation**: Bypasses the DatabaseManager abstraction layer
- **Don't Repeat Yourself**: Database connection logic duplicated

## Remediation Plan

### Recommended Solution

Consolidate all database access through the DatabaseManager singleton and remove direct Database instantiations.

**Design Strategy**:
1. Add any missing query methods to DatabaseManager that are currently using direct Database access
2. Update all modules to use DatabaseManager.getInstance() exclusively
3. Make Database instantiation internal to DatabaseManager only
4. Remove all direct Database imports from application code
5. Add architectural fitness function to prevent future violations

### Specific Steps

1. **Step 1**: Add missing query methods to DatabaseManager
   ```typescript
   // In database-manager.ts, add:
   public getRecentEmailsRaw(limit: number = 30): any[] {
     return this.db.prepare(`
       SELECT message_id as id, message_id, subject, from_address,
              from_name, date_sent, snippet, is_read, is_starred,
              has_attachments, folder
       FROM emails
       ORDER BY date_sent DESC
       LIMIT ?
     `).all(limit);
   }

   public getEmailDetails(messageId: string): any {
     return this.db.prepare(`
       SELECT id, message_id, subject, from_address, from_name,
              date_sent, body_text, body_html, snippet, is_read,
              is_starred, has_attachments, attachment_count, folder
       FROM emails
       WHERE message_id = ?
     `).get(messageId);
   }

   public getEmailRecipients(messageId: string): any[] {
     return this.db.prepare(`
       SELECT r.type, r.address
       FROM recipients r
       JOIN emails e ON r.email_id = e.id
       WHERE e.message_id = ?
     `).all(messageId);
   }
   ```

2. **Step 2**: Update email-agent/server/endpoints/emails.ts
   ```typescript
   // Remove direct Database import
   - import { Database } from "bun:sqlite";
   - const db = new Database(DATABASE_PATH);

   // Use only DatabaseManager
   const dbManager = DatabaseManager.getInstance();
   const imapManager = ImapManager.getInstance();

   // In handleEmailDetailsEndpoint:
   export async function handleEmailDetailsEndpoint(req: Request, emailId: string): Promise<Response> {
     if (!emailId) {
       return new Response(JSON.stringify({ error: 'Invalid email ID' }), { status: 400 });
     }

     try {
       - const email = db.prepare(`SELECT ...`).get(emailId);
       + const email = dbManager.getEmailDetails(emailId);

       if (!email) {
         return new Response(JSON.stringify({ error: 'Email not found' }), { status: 404 });
       }

       - const recipients = db.prepare(`SELECT ...`).all(emailId);
       + const recipients = dbManager.getEmailRecipients(emailId);

       // ... rest of method
     }
   }
   ```

3. **Step 3**: Update email-agent/ccsdk/websocket-handler.ts
   ```typescript
   import { DatabaseManager } from "../database/database-manager";

   export class WebSocketHandler {
     - private db: Database;
     + private dbManager: DatabaseManager;
     private sessions: Map<string, Session> = new Map();
     private clients: Map<string, WSClient> = new Map();

     constructor() {
       - this.db = new Database(dbPath);
       + this.dbManager = DatabaseManager.getInstance();
       this.initProfileWatcher();
       this.initEmailWatcher();
     }

     private async getRecentEmails(limit: number = 30) {
       try {
         - const emails = this.db.prepare(`
         -   SELECT message_id as id, message_id, subject, from_address,
         -          from_name, date_sent, snippet, is_read, is_starred,
         -          has_attachments, folder
         -   FROM emails
         -   ORDER BY date_sent DESC
         -   LIMIT ?
         - `).all(limit);
         + const emails = this.dbManager.getRecentEmailsRaw(limit);

         return emails;
       } catch (error) {
         console.error('Error fetching recent emails:', error);
         return [];
       }
     }
   }
   ```

4. **Step 4**: Ensure Session class also uses DatabaseManager
   ```typescript
   // In ccsdk/session.ts - verify it's using DatabaseManager, not direct Database
   // If it has direct Database access, refactor similarly
   ```

### Alternative Approaches

**Option A**: Keep current pattern but document it
- Pros: No code changes required
- Cons: Maintains technical debt, doesn't address actual risks
- **Not recommended**

**Option B**: Use dependency injection for Database
- Pros: More testable, explicit dependencies
- Cons: More complex, requires larger refactoring
- **Future consideration** after fixing current issue

**Recommendation**: Proceed with recommended solution - it's the cleanest path to architectural consistency.

## Acceptance Criteria

- [ ] All direct `new Database()` instantiations removed from application code
- [ ] All database queries go through `DatabaseManager.getInstance()`
- [ ] Only the database module imports `bun:sqlite`
- [ ] WebSocketHandler uses DatabaseManager instead of direct Database
- [ ] Email endpoints use DatabaseManager methods exclusively
- [ ] No TypeScript errors after refactoring
- [ ] All existing tests pass
- [ ] Add test to verify only one Database instance exists

**Definition of Done**:
- [ ] Code changes implemented
- [ ] Unit tests added/updated
- [ ] Integration tests verify singleton behavior
- [ ] Documentation updated (if DatabaseManager API changed)
- [ ] ADR created documenting the database access pattern
- [ ] Team reviewed and approved

## Effort Estimation

**Size**: Small

**Estimated Complexity**:
- 1-2 days of development
- Clear solution path
- Low risk (SQLite WAL mode provides safety during transition)
- Single team affected

**Breakdown**:
- Add missing methods to DatabaseManager: 2 hours
- Refactor endpoints/emails.ts: 1 hour
- Refactor websocket-handler.ts: 2 hours
- Testing and verification: 2 hours
- Code review and documentation: 1 hour

## Dependencies

**Blocks**:
- Future database optimizations (connection pooling would require single access point)

**Blocked By**: None

**Related Issues**:
- Similar pattern review needed for ImapManager (currently correctly using Singleton)

## Migration Strategy

**Phase 1**: Add all needed methods to DatabaseManager (non-breaking)
**Phase 2**: Update endpoints/emails.ts to use DatabaseManager
**Phase 3**: Update websocket-handler.ts to use DatabaseManager
**Phase 4**: Remove unused Database imports
**Phase 5**: Add linting rules to prevent regression

No breaking changes required - this is internal refactoring.

## Prevention Strategy

- [ ] Add ESLint rule to prevent direct Database imports outside /database module
- [ ] Add architectural fitness function in CI to detect multiple Database instances
- [ ] Update development guidelines to mandate DatabaseManager usage
- [ ] Create ADR documenting "Database Access Patterns"
- [ ] Add code review checklist item for database access patterns

## Additional Context

**Related Documentation**:
- Singleton pattern: https://refactoring.guru/design-patterns/singleton
- SQLite WAL mode docs: https://www.sqlite.org/wal.html

**Historical Context**:
- The Singleton pattern was already implemented in DatabaseManager
- Direct Database usage appears to be convenience/copy-paste from early development
- SQLite WAL mode currently prevents most locking issues, but this is defensive rather than by design

**Questions for Discussion**:
- Should we eventually abstract Database completely behind an interface?
- Do we need database connection pooling for future scaling?
