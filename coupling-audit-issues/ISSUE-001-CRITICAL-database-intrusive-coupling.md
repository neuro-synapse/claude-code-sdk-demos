# [COUPLING] [CRITICAL]: Intrusive database coupling - Duplicate database manager implementations in email-agent

## Problem Statement

The email-agent service contains two separate, incompatible database manager implementations (`DatabaseManager` and `EmailDatabase`) that operate on the same SQLite database with different schemas and access patterns. This creates intrusive coupling where both managers directly access and modify the same underlying database resource, leading to schema conflicts, data inconsistency risks, and unpredictable behavior.

## Current State

**Location**:
- File: `email-agent/database/database-manager.ts` (lines 67-613)
- File: `email-agent/database/email-db.ts` (lines 69-536)
- Owner: email-agent service team

**Coupling Type**: Intrusive (Critical)
**Degree**: CoP (Position) + CoA (Algorithm) - Both share database file but with different table structures and access patterns

**Evidence**:
```typescript
// database-manager.ts:74
this.db = new Database(dbPath);
this.db.exec("PRAGMA journal_mode = WAL");
// Uses snake_case columns: message_id, from_address, etc.

// email-db.ts:75
this.db = new Database(dbPath);
this.db.exec("PRAGMA journal_mode = WAL");
// Uses camelCase field names but snake_case database columns

// DIFFERENT SCHEMAS:
// DatabaseManager stores to/cc/bcc in TEXT columns (toAddresses, ccAddresses)
// EmailDatabase uses separate recipients table with foreign keys
```

## Impact Assessment

**Severity**: CRITICAL

**Why This Matters**:
- **Data Integrity**: Two different schemas operating on same database can corrupt data
- **Unpredictable Behavior**: Which manager's schema is active depends on execution order
- **Impossible to Evolve**: Cannot change either implementation without breaking the other
- **Testing Nightmare**: Integration tests would need to account for both schemas

**Blast Radius**:
- Modules affected: 3 (database-manager, email-db, email-sync)
- Teams affected: 1 (email-agent team)
- Deployment coupling: Single service but internal chaos

**Risk Factors**:
- Change frequency: HIGH - email data models change frequently
- Failure probability: HIGH - schema conflicts are inevitable
- Detection difficulty: HARD - only surfaces when both managers are used

## Current Behavior vs. Expected Behavior

**Current**: Two database managers with incompatible schemas can both initialize the same database file, leading to schema conflicts and potential data corruption.

**Expected**: Single database manager with a unified schema that serves as the single source of truth for all email data access.

**Violated Principle(s)**:
- Single Responsibility Principle - database should have one owner
- DRY (Don't Repeat Yourself) - duplicated database logic
- Encapsulation - no clear boundary around data access

## Remediation Plan

### Recommended Solution

Consolidate to a single database manager with unified schema and clear API contract.

**Design Strategy**:
1. Choose one implementation as the foundation (DatabaseManager appears more complete)
2. Merge beneficial features from EmailDatabase (domain-based search, recipient table)
3. Create unified schema migration
4. Update all consumers to use single manager
5. Remove duplicate implementation

### Specific Steps

1. **Step 1: Analyze feature differences and create unified schema**
   ```sql
   -- Keep DatabaseManager's core structure but add EmailDatabase's recipient table
   CREATE TABLE IF NOT EXISTS emails (
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     message_id TEXT UNIQUE NOT NULL,
     -- ... existing DatabaseManager columns ...
   );

   CREATE TABLE IF NOT EXISTS recipients (
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     email_id INTEGER NOT NULL,
     type TEXT CHECK(type IN ('to', 'cc', 'bcc')) NOT NULL,
     address TEXT NOT NULL,
     domain TEXT GENERATED ALWAYS AS (
       LOWER(SUBSTR(address, INSTR(address, '@') + 1))
     ) STORED,
     FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
   );
   ```

2. **Step 2: Extend DatabaseManager with domain search functionality**
   ```typescript
   // Add to database-manager.ts
   public searchByDomain(domain: string, limit: number = 30): EmailRecord[] {
     // Implement domain-based search using recipient table
   }
   ```

3. **Step 3: Create migration script**
   ```typescript
   // database-migration.ts
   export class DatabaseMigration {
     migrate(db: Database) {
       // Add recipient table
       // Migrate existing to/cc/bcc data to recipient table
       // Maintain backward compatibility
     }
   }
   ```

4. **Step 4: Update all consumers to use DatabaseManager only**
   ```typescript
   // email-sync.ts, server.ts, etc.
   import { DatabaseManager } from './database-manager';
   const dbManager = DatabaseManager.getInstance();
   ```

5. **Step 5: Remove email-db.ts after migration complete**

### Alternative Approaches

**Option A**: Keep EmailDatabase, deprecate DatabaseManager
- Pros: Recipients table is cleaner design
- Cons: EmailDatabase less feature-complete, more refactoring needed

**Option B**: Create new DatabaseV3 merging both
- Pros: Fresh start, no legacy baggage
- Cons: Highest effort, requires updating all consumers

**Recommendation**: Extend DatabaseManager (Option 1) - it's more widely used and feature-complete, just needs recipient table addition.

## Acceptance Criteria

- [ ] Only one database manager class exists
- [ ] All email data access goes through unified manager
- [ ] Schema supports both flat columns AND recipient table for advanced queries
- [ ] All existing tests pass with new unified manager
- [ ] No references to deleted EmailDatabase class remain
- [ ] Migration script successfully migrates existing data
- [ ] Domain-based search functionality preserved

**Definition of Done**:
- [ ] Code changes implemented
- [ ] Unit tests added/updated for unified manager
- [ ] Integration tests verify schema consistency
- [ ] Migration script tested on production-like dataset
- [ ] Documentation updated with new database architecture
- [ ] ADR created: "Consolidation of Database Managers"

## Effort Estimation

**Size**: Medium (1-2 weeks)

**Reasoning**:
- Clear technical path forward
- Requires careful migration to avoid data loss
- Multiple file updates across service
- Need thorough testing of migration

**Estimated Complexity**:
- Schema merge: 2 days
- Code consolidation: 2 days
- Migration script + testing: 3 days
- Consumer updates: 2 days
- Buffer for issues: 1 day

## Dependencies

**Blocks**:
- None identified

**Blocked By**:
- None

**Related Issues**:
- ISSUE-003: Model coupling in email data structures

## Migration Strategy

**Phase 1**: Add recipient table to DatabaseManager without breaking changes
**Phase 2**: Update DatabaseManager to populate recipient table on insert/update
**Phase 3**: Migrate existing to/cc/bcc data to recipient table
**Phase 4**: Update all consumers to use DatabaseManager
**Phase 5**: Remove EmailDatabase class and file

## Prevention Strategy

- [ ] Add architectural fitness function: "Only one database manager per service"
- [ ] Update development guidelines: "Database access must go through single manager"
- [ ] Add linting rule to prevent multiple Database class instantiations
- [ ] Create ADR documenting: "Single Database Manager Pattern"
- [ ] Share learning in team retrospective

## Additional Context

**Related Documentation**:
- SQLite best practices for single-writer scenarios
- Database migration patterns

**Historical Context**:
- EmailDatabase appears to be newer implementation with better recipient modeling
- DatabaseManager is the primary implementation used by most of the codebase
- Likely created by different developers at different times without coordination

**Questions for Discussion**:
- Should we support backward compatibility with old schema?
- Do we need zero-downtime migration strategy?
- Should recipient table be mandatory or optional enhancement?
