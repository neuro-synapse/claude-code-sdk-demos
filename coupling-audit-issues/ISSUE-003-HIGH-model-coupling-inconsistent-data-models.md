# [COUPLING] [HIGH]: Model coupling - Inconsistent data model definitions across services

## Problem Statement

Email and SMS data structures are defined inconsistently across services, using different naming conventions (camelCase vs snake_case), different field types, and different structural patterns. This model coupling creates friction when integrating services, increases cognitive load, and makes it difficult to create shared tooling or libraries.

## Current State

**Location**:
- Files: `email-agent/database/database-manager.ts:5-36` (EmailRecord interface)
- Files: `email-agent/database/email-db.ts:6-50` (EmailRecord + Recipient interfaces)
- Files: `sms-agent/database/db.ts:5-23` (Contact + Message interfaces)
- Files: `sms-agent-python/database/models.py` (Python data models)
- Owner: Multiple teams (each service owns their models)

**Coupling Type**: Model coupling
**Degree**: CoN (Name) + CoT (Type) - Inconsistent naming and type definitions across boundaries

**Evidence**:
```typescript
// email-agent/database-manager.ts - Uses camelCase TypeScript style
export interface EmailRecord {
  messageId: string;
  fromAddress: string;
  toAddresses?: string;
  dateSent: Date | string;
  isRead: boolean;
}

// email-agent/database/email-db.ts - SAME entity, DIFFERENT naming
export interface EmailRecord {
  id?: number;
  message_id: string;      // snake_case!
  from_address: string;    // snake_case!
  date_sent: Date | string;
  is_read?: boolean;
}

// sms-agent/database/db.ts - Inconsistent patterns
export interface Contact {
  phone_number: string;  // snake_case
  name?: string;
  trust_level?: number;
}

export interface Message {
  contact_id: number;
  phone_number: string;  // snake_case
  message_text: string;  // snake_case
  direction: 'incoming' | 'outgoing';
}
```

**Specific Inconsistencies**:
1. Naming convention: camelCase vs snake_case within same service
2. Optional vs required fields differ between equivalent models
3. Date types: `Date | string` vs `datetime` vs `string`
4. ID fields: sometimes optional, sometimes required
5. Nested objects vs flat structures for addresses

## Impact Assessment

**Severity**: HIGH

**Why This Matters**:
- **Integration Friction**: Cannot share data models across services
- **Cognitive Load**: Developers must context-switch between conventions
- **Type Safety Lost**: Can't leverage TypeScript's type system across boundaries
- **Serialization Issues**: JSON serialization behaves differently for different models
- **Shared Tooling Impossible**: Can't create common libraries due to model differences

**Blast Radius**:
- Modules affected: 8+ (all database and API layers)
- Teams affected: 2 (email-agent and sms-agent teams)
- Deployment coupling: Low (services independent) but integration coupling HIGH

**Risk Factors**:
- Change frequency: MEDIUM - data models change with new features
- Failure probability: MEDIUM - type mismatches cause runtime errors
- Detection difficulty: EASY - TypeScript catches some, but not cross-language issues

## Current Behavior vs. Expected Behavior

**Current**: Each service defines data models independently with inconsistent conventions, leading to transformation overhead and type mismatches at integration points.

**Expected**: Consistent data modeling conventions across all services with shared type definitions for common entities, enabling type-safe integration and code reuse.

**Violated Principle(s)**:
- Principle of Least Astonishment - naming varies unpredictably
- Consistency - no unified approach to data modeling
- Interface Segregation - no shared contracts

## Remediation Plan

### Recommended Solution

Establish consistent data modeling conventions and create shared type library for common entities.

**Design Strategy**:
1. Define organization-wide data modeling standards
2. Create shared types package for common entities
3. Implement automatic conversion at service boundaries
4. Migrate existing code incrementally to new standards

### Specific Steps

1. **Step 1: Define data modeling standards**
   ```typescript
   // shared-types/standards.md

   ## Naming Conventions
   - TypeScript/JavaScript: camelCase for properties
   - Database columns: snake_case
   - Python: snake_case for all

   ## Type Conventions
   - Dates: ISO 8601 strings in JSON, Date objects internally
   - IDs: Always number type, required for persisted entities
   - Booleans: Never optional unless truly nullable
   - Phone numbers: E.164 format strings
   ```

2. **Step 2: Create shared types package**
   ```typescript
   // packages/shared-types/src/email.ts
   export interface EmailRecord {
     id: number;                    // Required for persisted
     messageId: string;             // camelCase
     fromAddress: string;
     toAddresses: string[];         // Array, not comma-delimited
     dateSent: Date;               // Consistent type
     isRead: boolean;              // Never optional
   }

   // Database mapping utility
   export function toDbModel(email: EmailRecord): DbEmailRecord {
     return {
       id: email.id,
       message_id: email.messageId,  // Auto-convert to snake_case
       from_address: email.fromAddress,
       // ...
     };
   }
   ```

3. **Step 3: Create conversion utilities**
   ```typescript
   // shared-types/src/converters.ts
   export class ModelConverter {
     static toCamelCase<T>(obj: any): T {
       // Deep conversion from snake_case to camelCase
     }

     static toSnakeCase<T>(obj: any): T {
       // Deep conversion from camelCase to snake_case
     }
   }
   ```

4. **Step 4: Update database layers to use converters**
   ```typescript
   // email-agent/database/database-manager.ts
   import { EmailRecord, toDbModel, fromDbModel } from '@shared/types';

   public upsertEmail(email: EmailRecord): number {
     const dbModel = toDbModel(email);
     // Work with snake_case internally
     const result = this.db.prepare(/* ... */).run(dbModel);
     return result.id;
   }

   public getEmail(id: number): EmailRecord {
     const dbModel = this.db.prepare(/* ... */).get(id);
     return fromDbModel(dbModel);  // Convert back to camelCase
   }
   ```

5. **Step 5: Migrate incrementally, one interface at a time**
   - Start with most-used interfaces (EmailRecord, Contact)
   - Update all consumers
   - Add deprecation warnings to old interfaces
   - Remove old interfaces after migration

### Alternative Approaches

**Option A**: Complete rewrite with new models (Not Recommended)
- Pros: Clean slate, perfect consistency
- Cons: Too disruptive, high risk

**Option B**: Keep inconsistency, document it well
- Pros: No code changes needed
- Cons: Doesn't solve the problem, technical debt persists

**Option C**: Use GraphQL schema as single source of truth
- Pros: Schema-first design, auto-generated types
- Cons: Adds GraphQL dependency, may be overkill

**Recommendation**: Shared types package (Option from plan above) - provides consistency without massive rewrites.

## Acceptance Criteria

- [ ] Shared types package created and published
- [ ] All services use consistent naming convention for equivalent fields
- [ ] Database column names use snake_case, application code uses camelCase
- [ ] Automatic conversion happens at database boundary
- [ ] No manual case conversion in business logic
- [ ] TypeScript strict mode passes for all models
- [ ] Documentation clearly states conventions

**Definition of Done**:
- [ ] Shared types package implemented
- [ ] Conversion utilities tested
- [ ] All database layers updated to use converters
- [ ] API responses use consistent camelCase
- [ ] Database remains snake_case
- [ ] Migration guide published
- [ ] ADR created: "Consistent Data Modeling Standards"

## Effort Estimation

**Size**: Medium (1-2 weeks)

**Reasoning**:
- Shared types package: straightforward
- Conversion utilities: well-understood problem
- Migration: can be done incrementally
- Risk is low, impact is high

**Estimated Complexity**:
- Standards definition: 1 day
- Shared types package: 2 days
- Conversion utilities: 2 days
- Database layer updates: 3 days
- Testing: 2 days
- Documentation: 1 day

## Dependencies

**Blocks**:
- Cross-service data sharing initiatives
- Shared tooling development

**Blocked By**:
- None (can start immediately)

**Related Issues**:
- ISSUE-001: Database intrusive coupling
- ISSUE-002: Duplicate SMS logic

## Migration Strategy

**Phase 1**: Create shared types package with core entities
**Phase 2**: Add conversion utilities
**Phase 3**: Update email-agent database layer
**Phase 4**: Update sms-agent database layer
**Phase 5**: Update Python services to use consistent naming
**Phase 6**: Deprecate old inconsistent interfaces

## Prevention Strategy

- [ ] Add ESLint rule: enforce camelCase in TypeScript
- [ ] Add database migration linter: enforce snake_case
- [ ] Code review checklist: "Does this follow naming standards?"
- [ ] Automated tests: verify conversion utilities work correctly
- [ ] ADR: "Data Modeling Standards and Conventions"
- [ ] Team training on model conventions

## Additional Context

**Related Documentation**:
- TypeScript style guide
- Database naming conventions
- JSON API specification (camelCase standard)

**Historical Context**:
- Inconsistency likely emerged from:
  - Different developers with different preferences
  - Database-first vs code-first approaches
  - Lack of established conventions early on
- No shared types library was ever created

**Questions for Discussion**:
- Should we use a schema definition language (JSON Schema, Protocol Buffers)?
- How do we handle Python's strong preference for snake_case?
- Should API contracts follow database naming or code naming?
- What's the migration strategy for already-deployed clients?
