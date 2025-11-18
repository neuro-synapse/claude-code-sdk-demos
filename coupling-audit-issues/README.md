# Coupling Compliance Audit Issues

This directory contains detailed issue reports from the coupling compliance audit conducted on 2025-10-11.

## Quick Summary

| Issue | Severity | Type | Effort | Priority |
|-------|----------|------|--------|----------|
| [ISSUE-001](ISSUE-001-CRITICAL-database-intrusive-coupling.md) | 🔴 CRITICAL | Intrusive Coupling | 1-2 weeks | P0 |
| [ISSUE-002](ISSUE-002-CRITICAL-functional-coupling-duplicate-sms-logic.md) | 🔴 CRITICAL | Functional Coupling | 2-3 weeks | P0 |
| [ISSUE-003](ISSUE-003-HIGH-model-coupling-inconsistent-data-models.md) | 🟠 HIGH | Model Coupling | 1-2 weeks | P1 |
| [ISSUE-004](ISSUE-004-HIGH-temporal-coupling-server-initialization.md) | 🟠 HIGH | Temporal Coupling | 1 week | P1 |
| [ISSUE-005](ISSUE-005-MEDIUM-missing-api-versioning.md) | 🟡 MEDIUM | Contract Coupling | 3-5 days | P2 |
| [ISSUE-006](ISSUE-006-MEDIUM-database-access-pattern-violations.md) | 🟡 MEDIUM | Boundary Erosion | 2-3 days | P2 |

## Issue Details

### ISSUE-001: Intrusive Database Coupling
**Problem**: Two incompatible database managers (DatabaseManager and EmailDatabase) operate on the same SQLite file with different schemas, creating data corruption risk.

**Impact**: Critical - data integrity at risk
**Recommendation**: Consolidate to single database manager with unified schema
**Effort**: 1-2 weeks

---

### ISSUE-002: Symmetric Functional Coupling
**Problem**: Identical SMS business logic duplicated across TypeScript and Python implementations, requiring manual synchronization of all rule changes.

**Impact**: Critical - business rules will diverge over time
**Recommendation**: Consolidate to single implementation (TypeScript) or extract to decision service
**Effort**: 2-3 weeks

---

### ISSUE-003: Model Coupling
**Problem**: Inconsistent data structure naming (camelCase vs snake_case) across and within services, preventing integration and code reuse.

**Impact**: High - integration friction, cognitive overhead
**Recommendation**: Establish standards, create shared types package with conversion utilities
**Effort**: 1-2 weeks

---

### ISSUE-004: Temporal Coupling
**Problem**: Server initialization has implicit order dependencies with multiple database connections created in undefined order.

**Impact**: High - race conditions, "database is locked" errors
**Recommendation**: Implement ApplicationContainer with explicit initialization lifecycle
**Effort**: 1 week

---

### ISSUE-005: Missing API Versioning
**Problem**: No API versioning on any HTTP endpoints, making all API changes potentially breaking.

**Impact**: Medium - blocks safe API evolution
**Recommendation**: Implement URL path versioning (/v1/, /v2/, etc.) with deprecation strategy
**Effort**: 3-5 days

---

### ISSUE-006: Database Access Violations
**Problem**: Direct database access bypassing DatabaseManager abstraction, breaking encapsulation.

**Impact**: Medium - fragile abstractions, difficult to refactor
**Recommendation**: Add missing methods to managers, refactor direct access, add linting rules
**Effort**: 2-3 days

---

## Recommended Resolution Order

### Phase 1: Critical Issues (Weeks 1-3)
1. **ISSUE-001** - Database intrusive coupling (P0, 1-2 weeks)
   - Highest data integrity risk
   - Blocks other database improvements

2. **ISSUE-002** - SMS logic duplication (P0, 2-3 weeks)
   - Prevents business rule divergence
   - Can be done in parallel with ISSUE-001

### Phase 2: High Priority (Weeks 4-6)
3. **ISSUE-003** - Model coupling (P1, 1-2 weeks)
   - Enables shared tooling
   - Improves developer experience

4. **ISSUE-004** - Temporal coupling (P1, 1 week)
   - Improves reliability
   - Simplifies testing

### Phase 3: Medium Priority (Week 7)
5. **ISSUE-005** - API versioning (P2, 3-5 days)
   - Enables safe API evolution
   - Quick win

6. **ISSUE-006** - Database access patterns (P2, 2-3 days)
   - Completes database layer cleanup
   - Protects abstractions
   - Should be done after ISSUE-001

---

## How to Use These Issues

Each issue file contains:

1. **Problem Statement** - Clear description of what's wrong
2. **Current State** - Evidence with file paths and line numbers
3. **Impact Assessment** - Why it matters and who it affects
4. **Remediation Plan** - Step-by-step fix with code examples
5. **Alternative Approaches** - Different solution options with tradeoffs
6. **Acceptance Criteria** - How to know when it's fixed
7. **Effort Estimation** - Time and complexity assessment
8. **Migration Strategy** - How to roll out the fix safely
9. **Prevention Strategy** - How to avoid this in the future

## Related Documentation

- [Main Audit Report](../COUPLING_AUDIT_REPORT.md) - Comprehensive analysis and recommendations
- [Coupling Principles](../COUPLING_AUDIT_REPORT.md#appendix-b-coupling-principles-reference) - Architectural principles used in assessment

## Architecture Decision Records (Recommended)

After resolving these issues, create ADRs for:

- ADR-001: Database Manager Consolidation
- ADR-002: SMS Service Architecture
- ADR-003: Data Modeling Standards
- ADR-004: Service Initialization Lifecycle
- ADR-005: API Versioning Strategy
- ADR-006: Database Access Patterns

## Next Steps

1. Review all issues with the team
2. Prioritize based on your specific context and roadmap
3. Create tasks/tickets in your project management system
4. Assign owners for each issue
5. Schedule regular architecture review meetings
6. Implement prevention strategies to avoid regression

---

**Audit Date**: 2025-10-11
**Auditor**: Coupling Compliance Audit Agent (Terragon Labs)
