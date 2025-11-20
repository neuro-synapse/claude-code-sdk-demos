# [COUPLING] [CRITICAL]: Duplicated EmailRecord Interfaces with Inconsistent Field Naming

**Issue ID**: #002
**Severity**: Critical
**Type**: Model Coupling
**Module**: email-agent/database
**Status**: Open
**Created**: 2025-10-16

---

## Problem Statement

The `EmailRecord` interface is defined **twice** in the email-agent codebase with **incompatible field naming conventions**:
- `database-manager.ts` uses **camelCase** (messageId, threadId, fromAddress)
- `email-db.ts` uses **snake_case** (message_id, thread_id, from_address)

This creates **model coupling** where multiple components depend on different representations of the same entity. The inconsistency forces multiple conversion layers, creates serialization errors, and makes the codebase fragile to changes.

Additionally, `SearchCriteria` and `Attachment` interfaces are also duplicated, compounding the problem.

---

## Current State

### Location

**EmailRecord Definition #1**: `/root/repo/email-agent/database/database-manager.ts:5-36`
```typescript
export interface EmailRecord {
  id?: number;
  messageId: string;              // camelCase
  threadId?: string;              // camelCase
  inReplyTo?: string;
  emailReferences?: string;
  dateSent: Date | string;
  dateReceived?: Date | string;
  subject?: string;
  fromAddress: string;            // camelCase
  fromName?: string;
  toAddresses?: string;           // camelCase
  ccAddresses?: string;
  bccAddresses?: string;
  replyTo?: string;
  bodyText?: string;              // camelCase
  bodyHtml?: string;
  snippet?: string;
  isRead: boolean;
  isStarred: boolean;
  isImportant: boolean;
  isDraft: boolean;
  isSent: boolean;
  isTrash: boolean;
  isSpam: boolean;
  sizeBytes: number;
  hasAttachments: boolean;
  attachmentCount: number;
  folder: string;
  labels?: string[];
  rawHeaders?: string;
}
```

**EmailRecord Definition #2**: `/root/repo/email-agent/database/email-db.ts:6-34`
```typescript
export interface EmailRecord {
  id?: number;
  message_id: string;             // snake_case
  thread_id?: string;             // snake_case
  in_reply_to?: string;
  email_references?: string;
  date_sent: Date | string;
  date_received?: Date | string;
  subject?: string;
  from_address: string;           // snake_case
  from_name?: string;
  reply_to?: string;
  body_text?: string;             // snake_case
  body_html?: string;
  snippet?: string;
  is_read?: boolean;
  is_starred?: boolean;
  is_important?: boolean;
  is_draft?: boolean;
  is_sent?: boolean;
  is_trash?: boolean;
  is_spam?: boolean;
  size_bytes?: number;
  has_attachments?: boolean;
  attachment_count?: number;
  folder?: string;
  labels?: string;
  raw_headers?: string;
}
```

**Usage Map**:
- `ImapManager` uses `SearchCriteria` from `database-manager.ts`
- `EmailSyncService` uses `EmailRecord` from `email-db.ts`
- `server/endpoints/emails.ts` uses fields from both (inconsistently)
- `websocket-handler.ts` manually maps fields in SQL queries

**Module(s)**: database, server, ccsdk

**Owner(s)**: Backend Infrastructure Team, Database Team

**Coupling Type**: Model (Shared data structures)

**Connascence Degree**: **Connascence of Type (CoT) + Connascence of Meaning (CoM)**
- CoT: Multiple components depend on incompatible type definitions
- CoM: Field names have different meanings (camelCase vs snake_case)

---

### Evidence

**Field Naming Comparison**:

| Concept | database-manager.ts | email-db.ts | Database Column |
|---------|---------------------|-------------|-----------------|
| Message ID | `messageId` | `message_id` | `message_id` |
| Thread ID | `threadId` | `thread_id` | `thread_id` |
| From Email | `fromAddress` | `from_address` | `from_address` |
| From Name | `fromName` | `from_name` | `from_name` |
| Body Text | `bodyText` | `body_text` | `body_text` |
| Body HTML | `bodyHtml` | `body_html` | `body_html` |
| To Addresses | `toAddresses` | N/A (separate table) | `to_addresses` |
| CC Addresses | `ccAddresses` | N/A (separate table) | `cc_addresses` |

**Consequence**: Code must constantly convert between representations:

**In database-manager.ts**:
```typescript
private mapRowToEmailRecord(row: any): EmailRecord {
  return {
    id: row.id,
    messageId: row.message_id,        // snake_case → camelCase
    threadId: row.thread_id,          // snake_case → camelCase
    inReplyTo: row.in_reply_to,
    emailReferences: row.email_references,
    dateSent: new Date(row.date_sent),
    dateReceived: row.date_received ? new Date(row.date_received) : undefined,
    subject: row.subject,
    fromAddress: row.from_address,    // snake_case → camelCase
    fromName: row.from_name,          // snake_case → camelCase
    // ... 20 more field mappings
  };
}
```

**In websocket-handler.ts** (manual field selection):
```typescript
const emails = this.db.prepare(`
  SELECT message_id as id,          -- Manually rename to 'id'
         subject,
         from_address,               -- snake_case returned as-is
         from_name,
         date_sent as date,          -- Manually rename to 'date'
         body_text as body,          -- Manually rename to 'body'
         is_read as read             -- Manually rename to 'read'
  FROM emails
  ORDER BY date_sent DESC
  LIMIT ?
`).all(limit);
```

**Result**: 3 different representations of the same data:
1. Database columns (snake_case)
2. EmailRecord from database-manager.ts (camelCase)
3. EmailRecord from email-db.ts (snake_case)
4. Ad-hoc field names in queries (varies by module)

---

## Impact Assessment

### Severity: Critical

#### Why This Matters

**Business Impact**:
- **Data Integrity Risk**: Field mapping errors can cause silent data loss
- **Serialization Failures**: JSON responses may have mixed field names
- **API Inconsistency**: Clients receive different field names depending on endpoint
- **Production Bugs**: TypeError: Cannot read property 'messageId' of undefined (vs 'message_id')

**Example Production Scenario**:
```typescript
// Endpoint A uses database-manager.ts
GET /api/emails/inbox
Response: [{ messageId: "123", fromAddress: "test@example.com" }]

// Endpoint B uses email-db.ts
GET /api/emails/search
Response: [{ message_id: "123", from_address: "test@example.com" }]

// Client-side code breaks because field names don't match!
```

**Technical Impact**:
- **Maintenance Burden**: Changes to email structure require updating 2+ interfaces
- **Type Safety Loss**: TypeScript can't catch mismatches between definitions
- **Code Duplication**: Mapping functions duplicated across modules
- **Fragile Refactoring**: Renaming a field requires finding all variations
- **Testing Complexity**: Tests must handle multiple representations

**Team Impact**:
- **Developer Confusion**: "Which EmailRecord should I use?"
- **Onboarding Friction**: New developers don't know canonical interface
- **Code Review Overhead**: Reviewers must check for mapping errors
- **Bug Introduction**: Easy to use wrong interface accidentally

---

### Blast Radius

**Modules Affected**: 5
- `database/database-manager.ts` (defines EmailRecord v1)
- `database/email-db.ts` (defines EmailRecord v2)
- `database/imap-manager.ts` (uses SearchCriteria from v1)
- `database/email-sync.ts` (uses EmailRecord from v2)
- `server/endpoints/` (uses both inconsistently)
- `ccsdk/websocket-handler.ts` (manually maps fields)

**Teams Affected**: 2
- Backend Infrastructure (owns database layer)
- Email Feature Team (consumes interfaces)

**Deployment Coupling**: High
- Cannot change email structure without updating all mapping functions
- API response format depends on which interface was used
- Database migrations must consider multiple field naming conventions

---

### Risk Factors

**Change Frequency**: High
- Email domain is core feature
- Schema evolves frequently (new fields, indexes)
- Each change requires updating 2+ interfaces

**Failure Probability**: High
- Human error: Using wrong interface
- Copy-paste errors in mapping functions
- Forgetting to update one of the definitions

**Detection Difficulty**: High
- TypeScript doesn't catch naming mismatches
- Tests may pass if they use same (wrong) interface
- Runtime errors may be intermittent
- Silent data loss (field not mapped → data dropped)

**Real Example of Silent Failure**:
```typescript
// Developer uses database-manager.ts EmailRecord
const email: EmailRecord = {
  messageId: "123",      // camelCase
  fromAddress: "test@example.com",
  // ... other fields
};

// But saves using email-db.ts method
emailDb.insertEmail(email);  // 💥

// email-db expects message_id, not messageId
// TypeScript doesn't complain (both are EmailRecord!)
// Fields are undefined in database
// Silent data loss
```

---

## Current Behavior vs. Expected Behavior

### Current Behavior

**Multiple Definitions**:
```typescript
// File 1: database-manager.ts
export interface EmailRecord {
  messageId: string;
  fromAddress: string;
  bodyText?: string;
}

// File 2: email-db.ts
export interface EmailRecord {
  message_id: string;
  from_address: string;
  body_text?: string;
}

// File 3: email-api.ts (client-side)
export interface Email {
  id: string;
  from: string;
  body: string;
}
```

**Conversion Layers Everywhere**:
```typescript
// Conversion 1: Database → DatabaseManager
private mapRowToEmailRecord(row: any): EmailRecord {
  return {
    messageId: row.message_id,  // Convert
    fromAddress: row.from_address,  // Convert
    bodyText: row.body_text,  // Convert
  };
}

// Conversion 2: EmailDatabase (no conversion, matches DB)
// Returns snake_case directly

// Conversion 3: API Response → Client
function toClientEmail(email: EmailRecord): ClientEmail {
  return {
    id: email.messageId,  // OR email.message_id?
    from: email.fromAddress,  // OR email.from_address?
    body: email.bodyText || email.body_text,  // Try both!
  };
}
```

**Result**: Conversion logic scattered across 5+ files, each slightly different.

---

### Expected Behavior

**Single Canonical Domain Model**:
```typescript
// domain/models/email.ts (SINGLE source of truth)
export interface EmailRecord {
  id?: number;
  messageId: string;              // ✅ Canonical: camelCase
  threadId?: string;
  inReplyTo?: string;
  emailReferences?: string;
  dateSent: Date;                 // ✅ Canonical: Date object
  dateReceived?: Date;
  subject?: string;
  fromAddress: string;
  fromName?: string;
  toAddresses?: string[];         // ✅ Canonical: Array
  ccAddresses?: string[];
  bccAddresses?: string[];
  replyTo?: string;
  bodyText?: string;
  bodyHtml?: string;
  snippet?: string;
  isRead: boolean;
  isStarred: boolean;
  isImportant: boolean;
  isDraft: boolean;
  isSent: boolean;
  isTrash: boolean;
  isSpam: boolean;
  sizeBytes: number;
  hasAttachments: boolean;
  attachmentCount: number;
  folder: string;
  labels?: string[];
  rawHeaders?: string;
}

// No other files define EmailRecord
// All modules import from domain/models/email.ts
```

**Single Mapping Layer** (Repository Pattern):
```typescript
// database/repositories/email-repository.ts
export class EmailRepository {
  constructor(private db: Database) {}

  // ONLY place where DB ↔ Domain conversion happens
  private mapRowToEmailRecord(row: any): EmailRecord {
    return {
      id: row.id,
      messageId: row.message_id,        // DB snake_case → Domain camelCase
      threadId: row.thread_id,
      fromAddress: row.from_address,
      bodyText: row.body_text,
      dateSent: new Date(row.date_sent), // String → Date
      toAddresses: row.to_addresses?.split(',') || [],  // String → Array
      labels: row.labels ? JSON.parse(row.labels) : [],  // JSON → Array
      // All conversions in ONE place
    };
  }

  async getEmailByMessageId(messageId: string): Promise<EmailRecord | null> {
    const row = this.db.prepare(`
      SELECT * FROM emails WHERE message_id = ?
    `).get(messageId);

    return row ? this.mapRowToEmailRecord(row) : null;
  }
}
```

**Benefits**:
- ✅ One source of truth for EmailRecord
- ✅ One mapping function
- ✅ TypeScript catches field mismatches
- ✅ Easy to refactor
- ✅ Consistent API responses

---

### Violated Principles

1. **Don't Repeat Yourself (DRY)**
   - EmailRecord defined twice
   - Mapping logic duplicated in multiple places

2. **Single Source of Truth**
   - No canonical data model
   - Each module has its own interpretation

3. **Separation of Concerns**
   - Business logic mixed with data mapping
   - Field name conversions scattered throughout

4. **Type Safety**
   - TypeScript thinks both EmailRecords are compatible
   - No compile-time checking of field name consistency

---

## Remediation Plan

### Recommended Solution: Create Canonical Domain Model Layer

**Design Strategy**:

1. **Create Domain Model Layer** - Single source of truth for all entities
2. **Choose Field Naming Convention** - Use camelCase (TypeScript standard)
3. **Create Mapping Layer** - Single function per entity in repository
4. **Migrate All Usages** - Update imports to use canonical model
5. **Delete Duplicates** - Remove duplicate interface definitions

---

### Specific Implementation Steps

#### Step 1: Create Domain Model Layer (1 day)

**File: `domain/models/email.ts`**
```typescript
/**
 * Canonical EmailRecord interface.
 * This is the ONLY definition of EmailRecord in the codebase.
 *
 * Field Naming Convention: camelCase (TypeScript standard)
 * All modules MUST import from this file.
 */
export interface EmailRecord {
  // Primary key
  id?: number;

  // Email identifiers
  messageId: string;
  threadId?: string;
  inReplyTo?: string;
  emailReferences?: string;

  // Timestamps
  dateSent: Date;                 // Always Date object (not string)
  dateReceived?: Date;

  // Email metadata
  subject?: string;
  folder: string;
  labels: string[];               // Always array (not JSON string)

  // Sender information
  fromAddress: string;
  fromName?: string;
  replyTo?: string;

  // Recipients (arrays, not comma-separated strings)
  toAddresses: string[];
  ccAddresses: string[];
  bccAddresses: string[];

  // Content
  bodyText?: string;
  bodyHtml?: string;
  snippet?: string;
  rawHeaders?: string;

  // Flags
  isRead: boolean;
  isStarred: boolean;
  isImportant: boolean;
  isDraft: boolean;
  isSent: boolean;
  isTrash: boolean;
  isSpam: boolean;

  // Attachments
  hasAttachments: boolean;
  attachmentCount: number;

  // Size
  sizeBytes: number;
}

/**
 * Search criteria for email queries.
 */
export interface SearchCriteria {
  query?: string;
  from?: string | string[] | 'me';
  to?: string | string[];
  subject?: string;
  dateRange?: { start: Date; end: Date };
  hasAttachments?: boolean;
  isUnread?: boolean;
  isStarred?: boolean;
  folder?: string;
  folders?: string[];
  labels?: string[];
  threadId?: string;
  limit?: number;
  offset?: number;
  minSize?: number;
  maxSize?: number;
}

/**
 * Email attachment.
 */
export interface Attachment {
  id?: number;
  emailId: number;
  filename: string;
  contentType?: string;
  sizeBytes: number;
  contentId?: string;
  isInline: boolean;
}
```

**File: `domain/models/index.ts`**
```typescript
// Central export point for all domain models
export * from './email';
// Future models exported here too
```

---

#### Step 2: Create Mapping Functions in Repository (1 day)

**File: `database/repositories/email-repository.ts`**
```typescript
import { Database } from "bun:sqlite";
import { EmailRecord, SearchCriteria, Attachment } from "../../domain/models";

export class EmailRepository {
  constructor(private db: Database) {}

  /**
   * Maps database row (snake_case) to domain model (camelCase).
   * This is the ONLY place where this mapping happens.
   */
  private mapRowToEmailRecord(row: any): EmailRecord {
    return {
      id: row.id,

      // Identifiers
      messageId: row.message_id,
      threadId: row.thread_id || undefined,
      inReplyTo: row.in_reply_to || undefined,
      emailReferences: row.email_references || undefined,

      // Timestamps (string → Date)
      dateSent: new Date(row.date_sent),
      dateReceived: row.date_received ? new Date(row.date_received) : undefined,

      // Metadata
      subject: row.subject || undefined,
      folder: row.folder || 'INBOX',
      labels: row.labels ? JSON.parse(row.labels) : [],  // JSON → Array

      // Sender
      fromAddress: row.from_address,
      fromName: row.from_name || undefined,
      replyTo: row.reply_to || undefined,

      // Recipients (comma-separated string → Array)
      toAddresses: row.to_addresses ? row.to_addresses.split(',').map((s: string) => s.trim()) : [],
      ccAddresses: row.cc_addresses ? row.cc_addresses.split(',').map((s: string) => s.trim()) : [],
      bccAddresses: row.bcc_addresses ? row.bcc_addresses.split(',').map((s: string) => s.trim()) : [],

      // Content
      bodyText: row.body_text || undefined,
      bodyHtml: row.body_html || undefined,
      snippet: row.snippet || undefined,
      rawHeaders: row.raw_headers || undefined,

      // Flags (number → boolean)
      isRead: Boolean(row.is_read),
      isStarred: Boolean(row.is_starred),
      isImportant: Boolean(row.is_important),
      isDraft: Boolean(row.is_draft),
      isSent: Boolean(row.is_sent),
      isTrash: Boolean(row.is_trash),
      isSpam: Boolean(row.is_spam),

      // Attachments
      hasAttachments: Boolean(row.has_attachments),
      attachmentCount: row.attachment_count || 0,

      // Size
      sizeBytes: row.size_bytes || 0,
    };
  }

  /**
   * Maps domain model (camelCase) to database row (snake_case).
   * Used for INSERT/UPDATE operations.
   */
  private mapEmailRecordToRow(email: EmailRecord): any {
    return {
      message_id: email.messageId,
      thread_id: email.threadId || null,
      in_reply_to: email.inReplyTo || null,
      email_references: email.emailReferences || null,
      date_sent: email.dateSent.toISOString(),
      date_received: email.dateReceived?.toISOString() || null,
      subject: email.subject || null,
      from_address: email.fromAddress,
      from_name: email.fromName || null,
      to_addresses: email.toAddresses.join(', '),  // Array → comma-separated
      cc_addresses: email.ccAddresses.join(', '),
      bcc_addresses: email.bccAddresses.join(', '),
      reply_to: email.replyTo || null,
      body_text: email.bodyText || null,
      body_html: email.bodyHtml || null,
      snippet: email.snippet || null,
      is_read: email.isRead ? 1 : 0,  // boolean → number
      is_starred: email.isStarred ? 1 : 0,
      is_important: email.isImportant ? 1 : 0,
      is_draft: email.isDraft ? 1 : 0,
      is_sent: email.isSent ? 1 : 0,
      is_trash: email.isTrash ? 1 : 0,
      is_spam: email.isSpam ? 1 : 0,
      size_bytes: email.sizeBytes || 0,
      has_attachments: email.hasAttachments ? 1 : 0,
      attachment_count: email.attachmentCount || 0,
      folder: email.folder || 'INBOX',
      labels: JSON.stringify(email.labels || []),  // Array → JSON
      raw_headers: email.rawHeaders || null,
    };
  }

  async getEmailByMessageId(messageId: string): Promise<EmailRecord | null> {
    const row = this.db.prepare(`
      SELECT * FROM emails WHERE message_id = ?
    `).get(messageId);

    return row ? this.mapRowToEmailRecord(row) : null;
  }

  // All other methods use the same mapping functions
}
```

---

#### Step 3: Update All Imports (2 days)

**Search and replace across codebase**:

```bash
# Find all files importing EmailRecord
grep -r "import.*EmailRecord" --include="*.ts" email-agent/

# Update each file to import from domain/models
# Old: import { EmailRecord } from "../database/database-manager";
# New: import { EmailRecord } from "../domain/models";

# Files to update:
# - database/imap-manager.ts
# - database/email-sync.ts
# - server/endpoints/emails.ts
# - server/endpoints/sync.ts
# - ccsdk/websocket-handler.ts
# - agent/email-api.ts
```

**Example Update (imap-manager.ts)**:
```typescript
// OLD
import { EmailRecord, SearchCriteria } from "./database-manager";

// NEW
import { EmailRecord, SearchCriteria } from "../domain/models";
```

---

#### Step 4: Delete Duplicate Definitions (0.5 days)

**Remove EmailRecord from**:
1. `database/database-manager.ts` - Delete lines 5-36
2. `database/email-db.ts` - Delete lines 6-34

**After deletion, add import**:
```typescript
// database/database-manager.ts
import { EmailRecord, SearchCriteria, Attachment } from "../domain/models";

// database/email-db.ts
import { EmailRecord, Attachment } from "../domain/models";
```

**Keep only mapping functions**:
- `DatabaseManager.mapRowToEmailRecord()` → Move to EmailRepository
- `EmailDatabase` → Delete entire class (superseded by repository)

---

#### Step 5: Update Documentation (0.5 days)

**File: `domain/models/README.md`**
```markdown
# Domain Models

This directory contains canonical data model definitions.

## Guidelines

### ✅ DO
- Import models from `domain/models`
- Use defined types everywhere
- Follow camelCase naming convention

### ❌ DON'T
- Define EmailRecord in other files
- Create alternative representations
- Use snake_case in TypeScript code

## EmailRecord

**Canonical interface for email entities.**

**Field Naming**: camelCase (TypeScript standard)
**Date Fields**: Always `Date` objects (not strings)
**Arrays**: Always arrays (not comma-separated strings or JSON)

### Usage

```typescript
import { EmailRecord } from 'domain/models';

function processEmail(email: EmailRecord) {
  console.log(email.messageId);  // ✅ camelCase
  console.log(email.fromAddress);  // ✅ camelCase
}
```

### Mapping

Database uses snake_case columns. Mapping happens in `EmailRepository`:

| Domain (camelCase) | Database (snake_case) |
|--------------------|-----------------------|
| messageId          | message_id            |
| fromAddress        | from_address          |
| bodyText           | body_text             |
| dateSent           | date_sent             |

**Important**: Only `EmailRepository` should perform this mapping.
No other code should convert between representations.
```

---

### Alternative Approaches

#### Option A: Use snake_case Everywhere

**Approach**:
- Adopt database's snake_case convention in TypeScript
- Delete camelCase version
- Update all code to use snake_case

**Pros**:
- Matches database directly (no conversion needed)
- Less mapping overhead

**Cons**:
- Violates TypeScript convention (camelCase is standard)
- Less idiomatic TypeScript code
- External APIs typically use camelCase
- Most JavaScript libraries expect camelCase

**Recommendation**: ❌ **Not Recommended**
TypeScript standard is camelCase. Going against convention makes codebase harder to understand and integrate with external libraries.

---

#### Option B: Keep Both, Add Explicit Type Aliases

**Approach**:
- Keep both interfaces
- Rename to make explicit:
  ```typescript
  type EmailRecordCamelCase = { messageId: string; ... };
  type EmailRecordSnakeCase = { message_id: string; ... };
  ```
- Use TypeScript type narrowing to convert

**Pros**:
- No breaking changes
- Makes distinction explicit

**Cons**:
- Doesn't solve root problem (still two definitions)
- More complex code
- Type conversions everywhere
- Increased cognitive load

**Recommendation**: ❌ **Not Recommended**
This is a band-aid, not a solution. The goal is to eliminate duplication, not formalize it.

---

#### Option C: Generate Types from Database Schema

**Approach**:
- Use tool like `kysely-codegen` or `prisma`
- Auto-generate TypeScript types from SQLite schema
- Use generated types as canonical

**Pros**:
- Single source of truth (database schema)
- Auto-updates when schema changes
- No manual type maintenance

**Cons**:
- Adds build-time dependency
- Generated code may not match desired domain model
- Loss of control over type definitions
- Might generate snake_case (unidiomatic for TypeScript)

**Recommendation**: ⚠️ **Consider for Future**
Good long-term solution but requires tooling setup. For immediate fix, manual domain model is faster.

---

### Recommended Approach: Canonical Domain Model

**Why This is Best**:

1. **Single Source of Truth**: One EmailRecord definition
2. **TypeScript Idiomatic**: Uses camelCase convention
3. **Clear Boundaries**: Domain model separate from database
4. **Maintainable**: Changes happen in one place
5. **Type Safe**: TypeScript catches all mismatches
6. **No External Dependencies**: Pure TypeScript
7. **Easy Migration**: Can be done incrementally

**Implementation Timeline**: 4-5 days
- Day 1: Create domain model layer
- Day 1-2: Create mapping functions in repository
- Day 3-4: Update all imports
- Day 4: Delete duplicate definitions
- Day 5: Documentation and testing

---

## Acceptance Criteria

### Functional Requirements
- [ ] EmailRecord defined only once (in domain/models/email.ts)
- [ ] All modules import from domain/models
- [ ] No duplicate SearchCriteria or Attachment interfaces
- [ ] Mapping happens only in repository layer
- [ ] All tests pass with updated interfaces

### Code Quality Requirements
- [ ] No references to deleted interfaces
- [ ] TypeScript compilation succeeds with no errors
- [ ] All field names use camelCase consistently
- [ ] Date fields are Date objects (not strings)
- [ ] Array fields are arrays (not comma-separated strings)

### Documentation Requirements
- [ ] Domain model layer documented
- [ ] Field naming convention documented
- [ ] Mapping strategy explained
- [ ] Migration guide created

---

## Definition of Done

- [ ] ✅ Domain model layer created in `domain/models/`
- [ ] ✅ EmailRecord has single canonical definition
- [ ] ✅ All imports updated to use domain model
- [ ] ✅ Duplicate definitions deleted from database modules
- [ ] ✅ Mapping functions consolidated in repository
- [ ] ✅ All tests pass
- [ ] ✅ TypeScript compilation succeeds
- [ ] ✅ API responses use consistent field names
- [ ] ✅ Code review approved
- [ ] ✅ Documentation updated
- [ ] ✅ Deployed to staging
- [ ] ✅ Production deployment successful

---

## Effort Estimation

### Size: Medium (1 week)

**Breakdown**:

| Task | Days | Engineer |
|------|------|----------|
| Create domain model layer | 1 | Mid-level |
| Create mapping functions | 1 | Mid-level |
| Update all imports | 2 | Junior |
| Delete duplicate definitions | 0.5 | Junior |
| Update documentation | 0.5 | Mid-level |
| **TOTAL** | **5 days** | **1 week** |

**Can be done by**: 1 mid-level engineer + 1 junior engineer in parallel

---

## Dependencies

### Blocks
- #003 - Duplicated Business Logic (needs consistent models)
- #TBD - API Response Standardization (needs canonical model)

### Blocked By
- None (can start immediately)

### Related Issues
- #001 - Database Intrusive Coupling (should fix together)
- #004 - Raw SQL Scattered (repositories solve both)

---

## Migration Strategy

### Phase 1: Create Domain Layer (No Breaking Changes)

**Timeline**: 1 day

1. Create `domain/models/` directory
2. Create `email.ts` with canonical EmailRecord
3. Create mapping functions in EmailRepository
4. Write tests for mapping functions

**Validation**: New code compiles, tests pass

---

### Phase 2: Migrate One Module (Proof of Concept)

**Timeline**: 1 day

1. Update `imap-manager.ts` to import from domain/models
2. Update `websocket-handler.ts` to use canonical EmailRecord
3. Run integration tests
4. Verify no breaking changes

**Validation**: Updated modules work, old modules still work

---

### Phase 3: Migrate All Modules

**Timeline**: 2 days

1. Update all remaining imports
2. Update all type annotations
3. Run full test suite
4. Fix any compilation errors

**Validation**: All tests pass, no TypeScript errors

---

### Phase 4: Delete Duplicates

**Timeline**: 0.5 days

1. Remove EmailRecord from database-manager.ts
2. Remove EmailRecord from email-db.ts
3. Verify no broken references
4. Update documentation

**Validation**: Code still compiles, tests still pass

---

## Prevention Strategy

### 1. ESLint Rule

```javascript
// .eslintrc.js
module.exports = {
  rules: {
    'no-duplicate-interfaces': {
      create(context) {
        const definedInterfaces = new Map();

        return {
          TSInterfaceDeclaration(node) {
            const name = node.id.name;

            if (definedInterfaces.has(name)) {
              context.report({
                node,
                message: `Interface '${name}' is already defined in ${definedInterfaces.get(name)}. Import from domain/models instead.`,
              });
            } else {
              definedInterfaces.set(name, context.getFilename());
            }
          },
        };
      },
    },
  },
};
```

### 2. Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

# Check for duplicate EmailRecord definitions
COUNT=$(grep -r "export interface EmailRecord" --include="*.ts" | grep -v "domain/models" | wc -l)

if [ $COUNT -gt 0 ]; then
  echo "❌ Error: EmailRecord defined outside domain/models"
  echo "   Import from domain/models instead"
  exit 1
fi
```

### 3. Documentation

Add to `DEVELOPMENT.md`:
```markdown
## Data Model Guidelines

### ✅ DO
- Import all models from `domain/models`
- Use camelCase for field names
- Use `Date` objects for dates
- Use arrays for lists

### ❌ DON'T
- Define models in other locations
- Create alternative representations
- Use snake_case in TypeScript
- Use comma-separated strings for arrays
```

---

## Additional Context

### Why This Happened

Likely causes:
1. Two developers working independently
2. One used TypeScript convention (camelCase)
3. Other mirrored database schema (snake_case)
4. No code review caught the duplication
5. Both worked in their local context

### Questions for Discussion

1. Should we auto-generate types from schema in future?
2. Do we need explicit conversion functions for API layer?
3. Should dates be ISO strings for API responses?
4. How should we handle optional vs required fields?

---

**Issue Status**: Open
**Next Steps**:
1. Get approval for 1-week allocation
2. Assign engineer pair (1 mid + 1 junior)
3. Create branch for migration
4. Begin Phase 1

**Last Updated**: 2025-10-16
