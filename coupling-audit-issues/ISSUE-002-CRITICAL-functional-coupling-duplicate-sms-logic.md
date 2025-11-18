# [COUPLING] [CRITICAL]: Symmetric functional coupling - Duplicated SMS agent business logic across TypeScript and Python implementations

## Problem Statement

The codebase contains two complete implementations of the SMS Response Assistant - one in TypeScript (`sms-agent`) and one in Python (`sms-agent-python`) - that duplicate identical business logic, decision rules, and processing workflows. This symmetric functional coupling means the same business rules must be maintained in two different languages, creating consistency risks and coordination overhead.

## Current State

**Location**:
- Files: `sms-agent/agent/sms-agent.ts` (lines 10-102)
- Files: `sms-agent-python/agent/sms_agent.py` (lines 24-193)
- Files: `sms-agent/agent/sms-processor.ts` (lines 15-121)
- Files: `sms-agent-python/agent/sms_processor.py`
- Owner: SMS agent team (unclear which is canonical)

**Coupling Type**: Functional - Symmetric (duplicated business logic)
**Degree**: CoM (Meaning) + CoA (Algorithm) - Same business rules, auto-reply logic, trust level semantics

**Evidence**:
```typescript
// sms-agent.ts:78-100 (TypeScript)
async shouldAutoReply(context: SMSContext): Promise<boolean> {
  const { contact, incomingMessage } = context;
  const message = incomingMessage.toLowerCase();

  // Don't auto-reply to unknown contacts with low trust
  if (contact.trust_level === 0 && !contact.relationship) {
    return false;
  }

  // Don't auto-reply to very short messages
  if (message.length < 3) {
    return false;
  }

  // Don't auto-reply to urgent messages
  const humanAttentionKeywords = ['urgent', 'emergency', 'important', 'asap', 'help'];
  if (humanAttentionKeywords.some(keyword => message.includes(keyword))) {
    return false;
  }

  return true;
}
```

```python
# sms_agent.py:120-151 (Python)
async def should_auto_reply(self, context: SMSContext) -> bool:
    message = context.incoming_message.lower().strip()

    # Don't auto-reply to very short messages (might be accidental)
    if len(message) < 3:
        return False

    # Don't auto-reply to unknown contacts with no relationship
    if context.contact.trust_level == 0 and not context.contact.relationship:
        return False

    # Don't auto-reply to messages that seem urgent/need human attention
    urgent_keywords = [
        'urgent', 'emergency', 'important', 'asap', 'help', 'call me',
        'need you', 'problem', 'issue', 'trouble', 'hospital', 'accident'
    ]

    if any(keyword in message for keyword in urgent_keywords):
        return False

    # ... MORE DUPLICATED LOGIC
```

**Same business rules duplicated**:
- Trust level semantics (0=unknown, 1=acquaintance, 2=trusted, 3=verified)
- Auto-reply decision logic
- Urgent keyword detection
- Message length validation
- Contact relationship handling
- Claude prompt construction

## Impact Assessment

**Severity**: CRITICAL

**Why This Matters**:
- **Business Rule Divergence**: Updates to one implementation won't automatically sync to the other
- **Inconsistent Behavior**: Users get different responses depending on which service handles their message
- **Double Maintenance**: Every business logic change requires updates in two languages
- **Testing Complexity**: Need parallel test suites validating same behavior
- **Deployment Risk**: Services can drift over time causing unpredictable behavior

**Blast Radius**:
- Modules affected: 6 (both agent + processor + database layers in each implementation)
- Teams affected: 1 (but split effort across two codebases)
- Deployment coupling: Loose coupling between services but tight coupling in business logic

**Risk Factors**:
- Change frequency: HIGH - business rules for SMS responses will evolve frequently
- Failure probability: HIGH - very easy for implementations to drift
- Detection difficulty: MEDIUM - only caught through end-to-end testing

## Current Behavior vs. Expected Behavior

**Current**: Same SMS response business logic implemented twice in different languages, requiring manual synchronization of all rule changes.

**Expected**: Single canonical implementation of business logic with clear service boundaries, or shared decision service that both implementations can call.

**Violated Principle(s)**:
- DRY (Don't Repeat Yourself) - core business logic duplicated
- Single Source of Truth - no clear canonical implementation
- Service Independence - both services implement identical logic

## Remediation Plan

### Recommended Solution

Designate one implementation as canonical and deprecate the other, OR extract business logic into shared decision service.

**Design Strategy**:
1. Assess which implementation is production-ready and feature-complete
2. Choose: consolidate to single implementation OR create decision service
3. Migrate consumers to chosen approach
4. Deprecate duplicate implementation

### Specific Steps

#### Option A: Consolidate to TypeScript Implementation

1. **Step 1: Feature parity analysis**
   ```bash
   # Compare features between implementations
   # Python has more sophisticated urgent keyword detection
   # TypeScript has relationship classification
   # Merge best features into TypeScript version
   ```

2. **Step 2: Enhance TypeScript implementation with Python features**
   ```typescript
   // sms-agent.ts - add missing urgent keywords from Python
   const humanAttentionKeywords = [
     'urgent', 'emergency', 'important', 'asap', 'help',
     'call me', 'need you', 'problem', 'issue', 'trouble',
     'hospital', 'accident'  // Added from Python version
   ];
   ```

3. **Step 3: Migrate Python consumers to TypeScript service**
   ```python
   # Replace direct agent calls with HTTP/gRPC calls to TypeScript service
   import httpx

   async def process_sms(sms: IncomingSMS):
       response = await httpx.post(
           'http://sms-agent-service/process',
           json={'from': sms.from_number, 'body': sms.body}
       )
   ```

4. **Step 4: Deprecate Python implementation**
   - Add deprecation warnings
   - Update documentation
   - Remove Python service after migration period

#### Option B: Extract Business Logic to Decision Service

1. **Step 1: Create shared decision service**
   ```typescript
   // decision-service/sms-rules.ts
   export class SMSDecisionService {
     shouldAutoReply(context: SMSContext): boolean {
       // Single source of truth for business rules
     }

     generateResponse(context: SMSContext): Promise<string> {
       // Claude integration in one place
     }
   }
   ```

2. **Step 2: Expose decision service via HTTP/gRPC**
   ```typescript
   // decision-service/api.ts
   app.post('/should-auto-reply', async (req, res) => {
     const result = await decisionService.shouldAutoReply(req.body);
     res.json({ shouldReply: result });
   });
   ```

3. **Step 3: Update both implementations to call decision service**
   ```typescript
   // TypeScript agent becomes thin wrapper
   async shouldAutoReply(context) {
     return await fetch('/decision-service/should-auto-reply', {
       method: 'POST',
       body: JSON.stringify(context)
     });
   }
   ```

### Alternative Approaches

**Option A**: Consolidate to TypeScript (Recommended)
- Pros: Single codebase, easier maintenance, TypeScript is used by other services
- Cons: Need to migrate Python consumers, lose Python ecosystem benefits

**Option B**: Consolidate to Python
- Pros: Python better for ML/AI integrations, async/await native
- Cons: Most other services are TypeScript, would create language island

**Option C**: Extract to Decision Service
- Pros: True separation of concerns, both implementations can coexist
- Cons: Adds network hop, more complex architecture

**Recommendation**: Option A (Consolidate to TypeScript) - matches ecosystem and has better feature completeness.

## Acceptance Criteria

- [ ] Only ONE implementation of SMS business logic exists
- [ ] All auto-reply decision rules consolidated in single location
- [ ] Trust level semantics defined once and referenced by all consumers
- [ ] Urgent keyword detection uses single authoritative list
- [ ] All existing functionality from both implementations preserved
- [ ] Migration path documented for any external consumers
- [ ] Performance benchmarks show no regression

**Definition of Done**:
- [ ] Code consolidation complete
- [ ] All tests from both implementations merged and passing
- [ ] Integration tests verify consistent behavior
- [ ] Deprecated implementation removed or marked deprecated
- [ ] Documentation updated with single service architecture
- [ ] ADR created: "SMS Agent Consolidation Decision"

## Effort Estimation

**Size**: Large (2-3 weeks)

**Reasoning**:
- Need to analyze and merge features from two implementations
- Requires careful migration to avoid breaking consumers
- Must ensure all business logic captured in final implementation
- Extensive testing needed to verify functional equivalence

**Estimated Complexity**:
- Feature analysis and comparison: 2 days
- Logic consolidation: 3 days
- Consumer migration: 4 days
- Testing and validation: 3 days
- Documentation and cleanup: 2 days
- Buffer: 2 days

## Dependencies

**Blocks**:
- Any new SMS business logic features (must wait for consolidation)

**Blocked By**:
- None

**Related Issues**:
- ISSUE-004: Model coupling in SMS data structures
- ISSUE-005: Missing API versioning

## Migration Strategy

**Phase 1**: Feature freeze on both implementations
**Phase 2**: Merge features into chosen implementation
**Phase 3**: Create adapter/proxy for deprecated implementation
**Phase 4**: Migrate consumers to new implementation
**Phase 5**: Deprecate old implementation
**Phase 6**: Remove deprecated code after grace period

## Prevention Strategy

- [ ] Add architectural fitness function: "No duplicate business logic across services"
- [ ] Code review checklist: "Is this logic already implemented elsewhere?"
- [ ] Create shared business rules library for common logic
- [ ] Document service boundaries and responsibilities clearly
- [ ] ADR: "When to create new service vs extend existing"

## Additional Context

**Related Documentation**:
- Microservices anti-patterns: Distributed monolith
- DRY principle in distributed systems

**Historical Context**:
- Python implementation appears to be a port of TypeScript version
- Likely created for experimentation or language preference
- No clear documentation on which is canonical
- Both actively maintained based on recent commits

**Questions for Discussion**:
- Which implementation is used in production?
- Are there language-specific requirements driving dual implementations?
- Can we tolerate slight behavioral differences during migration?
- What's the migration timeline for existing consumers?
