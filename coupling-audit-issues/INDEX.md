# Coupling Audit Issues - Quick Index

## By Severity

### 🔴 CRITICAL
- [ISSUE-001](ISSUE-001-CRITICAL-database-intrusive-coupling.md) - Duplicate database managers (1-2 weeks)
- [ISSUE-002](ISSUE-002-CRITICAL-functional-coupling-duplicate-sms-logic.md) - Duplicated SMS logic (2-3 weeks)

### 🟠 HIGH
- [ISSUE-003](ISSUE-003-HIGH-model-coupling-inconsistent-data-models.md) - Inconsistent data models (1-2 weeks)
- [ISSUE-004](ISSUE-004-HIGH-temporal-coupling-server-initialization.md) - Server init coupling (1 week)

### 🟡 MEDIUM
- [ISSUE-005](ISSUE-005-MEDIUM-missing-api-versioning.md) - No API versioning (3-5 days)
- [ISSUE-006](ISSUE-006-MEDIUM-database-access-pattern-violations.md) - Database access violations (2-3 days)

## By Component

### email-agent
- [ISSUE-001](ISSUE-001-CRITICAL-database-intrusive-coupling.md) - Database coupling
- [ISSUE-003](ISSUE-003-HIGH-model-coupling-inconsistent-data-models.md) - Model coupling
- [ISSUE-004](ISSUE-004-HIGH-temporal-coupling-server-initialization.md) - Init coupling
- [ISSUE-005](ISSUE-005-MEDIUM-missing-api-versioning.md) - API versioning
- [ISSUE-006](ISSUE-006-MEDIUM-database-access-pattern-violations.md) - Access violations

### sms-agent (TypeScript & Python)
- [ISSUE-002](ISSUE-002-CRITICAL-functional-coupling-duplicate-sms-logic.md) - Duplicated logic
- [ISSUE-003](ISSUE-003-HIGH-model-coupling-inconsistent-data-models.md) - Model coupling
- [ISSUE-005](ISSUE-005-MEDIUM-missing-api-versioning.md) - API versioning
- [ISSUE-006](ISSUE-006-MEDIUM-database-access-pattern-violations.md) - Access violations

## By Effort

### Quick Wins (< 1 week)
- [ISSUE-005](ISSUE-005-MEDIUM-missing-api-versioning.md) - 3-5 days
- [ISSUE-006](ISSUE-006-MEDIUM-database-access-pattern-violations.md) - 2-3 days

### Medium Effort (1-2 weeks)
- [ISSUE-001](ISSUE-001-CRITICAL-database-intrusive-coupling.md) - 1-2 weeks
- [ISSUE-003](ISSUE-003-HIGH-model-coupling-inconsistent-data-models.md) - 1-2 weeks
- [ISSUE-004](ISSUE-004-HIGH-temporal-coupling-server-initialization.md) - 1 week

### Large Effort (2-3 weeks)
- [ISSUE-002](ISSUE-002-CRITICAL-functional-coupling-duplicate-sms-logic.md) - 2-3 weeks
