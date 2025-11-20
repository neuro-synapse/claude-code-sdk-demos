# Coupling Violations - Detailed Issue Specifications

This directory contains detailed specifications for all coupling violations identified in the audit.

**Audit Date**: 2025-10-16
**Total Issues**: 12

---

## 📑 Issue Index

### Critical Priority (Fix Immediately)

| ID | Title | Type | Module | Effort |
|----|-------|------|--------|--------|
| [#001](./ISSUE_001_DATABASE_INTRUSIVE_COUPLING.md) | Multiple Uncoordinated Database Instances | Intrusive | email-agent | 2-3 weeks |
| [#002](./ISSUE_002_MODEL_COUPLING_DUPLICATED_INTERFACES.md) | Duplicated EmailRecord Interfaces with Inconsistent Naming | Model | email-agent/database | 1 week |

### High Priority (Address Soon)

| ID | Title | Type | Module | Effort |
|----|-------|------|--------|--------|
| #003 | Duplicated Business Logic Across Language Implementations | Functional | sms-agent, sms-agent-python | 1 week |
| #004 | Raw SQL Queries Scattered Throughout Codebase | Intrusive | email-agent | Covered by #001 |
| #005 | No Dependency Injection - Hardcoded Singletons | Structural | email-agent | 1 week |
| #006 | Circular Dependency Between Database Layers | Structural | email-agent/database | Covered by #001 |
| #007 | Global WebSocket State Without Persistence | Temporal | email-agent/ccsdk | 1 week |

### Medium Priority (Plan and Schedule)

| ID | Title | Type | Module | Effort |
|----|-------|------|--------|--------|
| #008 | Missing API Versioning | Contract | All services | 3 days |
| #009 | Configuration Scattered Across Modules | Configuration | All services | 3 days |
| #010 | CCSDK Module Coupled to Database Layer | Layering | email-agent/ccsdk | 1 week |

### Low Priority (Nice to Have)

| ID | Title | Type | Module | Effort |
|----|-------|------|--------|--------|
| #011 | Inconsistent Naming Conventions | Style | SMS agents | 2 days |
| #012 | Missing Architectural Documentation | Documentation | All services | 2 days |

---

## 📊 Issue Distribution by Service

### email-agent
- **Critical**: 2 (#001, #002)
- **High**: 4 (#004, #005, #006, #007)
- **Medium**: 2 (#008, #010)
- **Low**: 1 (#012)
- **Total**: 9 issues

### sms-agent + sms-agent-python
- **High**: 1 (#003)
- **Medium**: 1 (#008, #009)
- **Low**: 2 (#011, #012)
- **Total**: 4 issues (counting shared issues once)

---

## 📝 Issue Specifications

Each issue file contains:

1. **Problem Statement** - What's wrong and why it matters
2. **Current State** - Exact file locations and evidence
3. **Impact Assessment** - Business, technical, and team impact
4. **Current vs Expected Behavior** - What should change
5. **Remediation Plan** - Step-by-step fix with code examples
6. **Alternative Approaches** - Multiple solutions with pros/cons
7. **Acceptance Criteria** - How to verify the fix
8. **Effort Estimation** - Time and resource requirements
9. **Dependencies** - What blocks/is blocked by this issue
10. **Migration Strategy** - Phased rollout plan
11. **Prevention Strategy** - How to prevent recurrence
12. **Additional Context** - Historical context and discussion questions

---

## 🔍 Detailed Issue Summaries

### #001: Multiple Uncoordinated Database Instances (CRITICAL)

**Problem**: 7 independent SQLite Database connections without coordination.

**Evidence**:
```typescript
// server.ts
const db = new Database(DATABASE_PATH);              // #1
const dbManager = DatabaseManager.getInstance();     // #2 (internal)
const wsHandler = new WebSocketHandler(DATABASE_PATH);   // #3
const syncService = new EmailSyncService(DATABASE_PATH); // #4 (internal)
// + 3 more in endpoints
```

**Impact**: Data corruption, race conditions, "database is locked" errors.

**Solution**: Implement `DatabaseConnectionPool` singleton + Repository Pattern

**Details**: [ISSUE_001_DATABASE_INTRUSIVE_COUPLING.md](./ISSUE_001_DATABASE_INTRUSIVE_COUPLING.md)

---

### #002: Duplicated EmailRecord Interfaces (CRITICAL)

**Problem**: EmailRecord defined twice with conflicting field names.

**Evidence**:
```typescript
// database-manager.ts (camelCase)
interface EmailRecord {
  messageId: string;
  fromAddress: string;
  bodyText?: string;
}

// email-db.ts (snake_case)
interface EmailRecord {
  message_id: string;
  from_address: string;
  body_text?: string;
}
```

**Impact**: Serialization errors, type safety gaps, maintenance burden.

**Solution**: Create canonical domain model in `domain/models/email.ts`

**Details**: [ISSUE_002_MODEL_COUPLING_DUPLICATED_INTERFACES.md](./ISSUE_002_MODEL_COUPLING_DUPLICATED_INTERFACES.md)

---

### #003: Duplicated Business Logic Across Implementations (HIGH)

**Problem**: SMS auto-reply logic duplicated in TypeScript and Python with divergence.

**Evidence**:
- Keyword lists differ (TypeScript has 5 keywords, Python has 11)
- System prompts nearly identical but with slight variations
- Relationship classification only in Python
- Sensitive keyword detection only in Python

**Impact**: Inconsistent behavior, double maintenance burden.

**Solution**: Extract shared business rules to configuration, create single source of truth.

**Effort**: 1 week

---

### #004: Raw SQL Queries Scattered Throughout (HIGH)

**Problem**: SQL queries embedded directly in business logic (endpoints, WebSocket handler).

**Evidence**:
```typescript
// websocket-handler.ts
const emails = this.db.prepare(`
  SELECT message_id as id, subject, from_address
  FROM emails ORDER BY date_sent DESC LIMIT ?
`).all(limit);

// endpoints/emails.ts
const email = db.prepare(`
  SELECT * FROM emails WHERE message_id = ?
`).get(emailId);
```

**Impact**: SQL injection risk, difficult to optimize, testing challenges.

**Solution**: Repository pattern (superseded by #001).

**Effort**: Covered by fixing #001

---

### #005: Hardcoded Singletons - No Dependency Injection (HIGH)

**Problem**: Extensive use of `getInstance()` pattern throughout codebase.

**Evidence**:
```typescript
const dbManager = DatabaseManager.getInstance();
const imapManager = ImapManager.getInstance();
// No way to inject mock for testing
```

**Impact**: Difficult to test, tight coupling, global state.

**Solution**: Replace with constructor injection.

**Effort**: 1 week

---

### #006: Circular Dependency Between Database Layers (HIGH)

**Problem**: Two database abstractions (DatabaseManager and EmailDatabase) with same responsibility.

**Evidence**:
- Both implement email CRUD operations
- Different naming conventions (camelCase vs snake_case)
- EmailSyncService uses EmailDatabase
- ImapManager uses DatabaseManager
- Circular confusion: which is canonical?

**Impact**: Confusion, maintenance complexity.

**Solution**: Consolidate into single repository layer (superseded by #001).

**Effort**: Covered by fixing #001

---

### #007: Global WebSocket State Without Persistence (HIGH)

**Problem**: In-memory session storage + 5-second polling broadcasts to all clients.

**Evidence**:
```typescript
// websocket-handler.ts
private sessions: Map<string, Session> = new Map();  // Lost on restart
private clients: Map<string, WSClient> = new Map();

// Periodic broadcast every 5 seconds
setInterval(() => {
  this.broadcastInboxUpdate();
}, 5000);
```

**Impact**: Session loss on restart, scalability issues.

**Solution**: Persist sessions to database, use WebSocket push instead of polling.

**Effort**: 1 week

---

### #008: Missing API Versioning (MEDIUM)

**Problem**: No `/v1/` prefix or version headers on any endpoint.

**Evidence**:
```typescript
// No versioning
if (url.pathname === '/api/sync') { ... }
if (url.pathname === '/api/emails/inbox') { ... }
```

**Impact**: Breaking changes affect all consumers, no migration path.

**Solution**: Add `/v1/` prefix, implement version negotiation.

**Effort**: 3 days

---

### #009: Configuration Scattered Across Modules (MEDIUM)

**Problem**: `DATABASE_PATH` imported in 7+ files, no validation layer.

**Evidence**:
```typescript
// Imported everywhere
import { DATABASE_PATH } from "./config";
const db = new Database(DATABASE_PATH);
```

**Impact**: Hard to configure, inconsistent defaults.

**Solution**: Centralized configuration service with validation.

**Effort**: 3 days

---

### #010: CCSDK Module Coupled to Database Layer (MEDIUM)

**Problem**: AI tools (custom-tools.ts) have direct database dependencies.

**Evidence**:
```
custom-tools.ts → email-api.ts → database access
```

**Impact**: AI layer shouldn't know about data storage.

**Solution**: Create service layer between CCSDK and data access.

**Effort**: 1 week

---

### #011: Inconsistent Naming Conventions (LOW)

**Problem**: TypeScript uses camelCase, Python uses snake_case, no unified standard.

**Impact**: Reduced readability, cognitive overhead.

**Solution**: Establish style guide, apply linting rules.

**Effort**: 2 days

---

### #012: Missing Architectural Documentation (LOW)

**Problem**: Architecture exists only in code, no ADRs or diagrams.

**Impact**: New developers struggle to understand boundaries.

**Solution**: Create architecture decision records (ADRs), diagrams.

**Effort**: 2 days

---

## 🎯 Recommended Fix Order

Based on dependencies and impact:

1. **#001** - Database Connection Pool (blocks #004, #006)
2. **#002** - Domain Model Layer (can parallel with #001)
3. **#005** - Dependency Injection (after #001)
4. **#003** - Unified Business Logic (independent)
5. **#007** - Session Management (after #001)
6. **#008** - API Versioning (independent)
7. **#010** - Decouple CCSDK (after #001, #005)
8. **#009** - Configuration (independent)
9. **#011** - Naming Consistency (low priority)
10. **#012** - Documentation (ongoing)

---

## 📈 Progress Tracking

As issues are resolved, update this table:

| Issue | Status | Assigned | Started | Completed | PR Link |
|-------|--------|----------|---------|-----------|---------|
| #001 | Open | - | - | - | - |
| #002 | Open | - | - | - | - |
| #003 | Open | - | - | - | - |
| #004 | Open | - | - | - | - |
| #005 | Open | - | - | - | - |
| #006 | Open | - | - | - | - |
| #007 | Open | - | - | - | - |
| #008 | Open | - | - | - | - |
| #009 | Open | - | - | - | - |
| #010 | Open | - | - | - | - |
| #011 | Open | - | - | - | - |
| #012 | Open | - | - | - | - |

---

## 🔄 Audit Updates

This audit represents the **baseline** (Version 1.0.0).

Future audits will:
- Track issue resolution
- Identify new violations
- Measure health score improvement
- Validate prevention measures

**Next Audit Scheduled**: 2026-01-16 (3 months)

---

**Directory Created**: 2025-10-16
**Last Updated**: 2025-10-16
**Audit Version**: 1.0.0
