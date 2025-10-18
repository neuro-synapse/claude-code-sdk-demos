# [COUPLING] [HIGH]: Business rules scattered across processor and agent layers

**Issue ID**: COUPLING-004
**Severity**: High
**Type**: Functional Coupling / Responsibility Fragmentation
**Date Identified**: 2025-10-18
**Applications**: sms-agent, sms-agent-python

---

## Problem Statement

Auto-reply decision logic is split between the `SMSProcessor` (orchestration layer) and `SMSAgent` (AI layer) in both SMS implementations. This creates functional coupling where the business rule "should we auto-reply?" is partially implemented in two different classes with different responsibilities, making it difficult to understand, modify, and test the complete auto-reply logic.

## Current State

**Location**:
- Files:
  - TypeScript: `sms-agent/agent/sms-processor.ts:45-85` and `sms-agent/agent/sms-agent.ts:78-101`
  - Python: `sms-agent-python/agent/sms_processor.py:78-79` and `sms-agent-python/agent/sms_agent.py:120-151`
- Modules: agent layer in both applications
- Owner: sms-agent team

**Coupling Type**: Functional Coupling
**Degree**: Split responsibility for single business decision

**Evidence**:

**TypeScript - Split Logic:**
```typescript
// sms-agent/agent/sms-processor.ts:45-85
async processSMS(sms: IncomingSMS): Promise<ProcessingResult> {
  // ... get contact, save message, get history ...

  // Business logic check #1: Should we auto-reply?
  const shouldReply = await this.agent.shouldAutoReply(context);

  if (shouldReply) {
    const response = await this.agent.generateResponse(context);

    // Business logic check #2: Do we have callback? (in processor)
    if (this.onSendSMS && response) {
      await this.onSendSMS({
        to: sms.from,
        body: response
      });
      // ... save outgoing message ...
      result.auto_reply_sent = true;
    }
  }

  return result;
}

// sms-agent/agent/sms-agent.ts:78-101
async shouldAutoReply(context: SMSContext): Promise<boolean> {
  const message = context.incomingMessage.toLowerCase().trim();

  // Business logic check #3: Message length (in agent)
  if (message.length < 3) return false;

  // Business logic check #4: Trust level (in agent)
  if (context.contact.trust_level === 0 && !context.contact.relationship) {
    return false;
  }

  // Business logic check #5: Urgent keywords (in agent)
  const urgentKeywords = ['urgent', 'emergency', ...];
  if (urgentKeywords.some(keyword => message.includes(keyword))) {
    return false;
  }

  return true;
}
```

**Scattered Concerns:**
1. **Processor** decides: "Do I have a send callback configured?"
2. **Agent** decides: "Is message long enough?"
3. **Agent** decides: "Is contact trusted enough?"
4. **Agent** decides: "Does message contain urgent keywords?"
5. **Processor** orchestrates: "Should I call agent's shouldAutoReply?"

## Impact Assessment

**Severity**: High

**Why This Matters**:
- **Difficult to understand**: Complete auto-reply logic requires reading 2 files
- **Hard to test**: Must test both classes to verify all auto-reply scenarios
- **Maintenance burden**: Changes to auto-reply rules may require updates in multiple places
- **Unclear ownership**: Who owns the "should auto-reply" decision?
- **Code navigation**: Developers must jump between files to understand behavior

**Blast Radius**:
- Modules affected: 4 files (2 in TypeScript, 2 in Python)
- Responsibility fragmentation across 2 layers
- All auto-reply functionality affected

**Risk Factors**:
- Change frequency: High - auto-reply rules will evolve with user feedback
- Failure probability: Medium - easy to miss one location when updating rules
- Detection difficulty: Medium - incomplete changes may not fail tests immediately

## Current Behavior vs. Expected Behavior

**Current**: Auto-reply decision split between SMSProcessor and SMSAgent with unclear boundaries.

**Expected**: Single cohesive component owns the complete "should auto-reply" decision logic.

**Violated Principle(s)**:
- **Single Responsibility Principle**: Auto-reply logic is a single responsibility split across classes
- **Cohesion**: Related logic should be grouped together
- **Separation of Concerns**: Mixing orchestration with business rules

## Remediation Plan

### Recommended Solution

Create a dedicated `AutoReplyPolicy` class that encapsulates ALL auto-reply decision logic.

**Design Strategy**:
1. Extract all auto-reply logic to new `AutoReplyPolicy` class
2. Policy class contains all checks in one place
3. Both Processor and Agent delegate to Policy
4. Clear separation: Policy = decisions, Agent = AI generation, Processor = orchestration

### Specific Steps

1. **Step 1**: Create AutoReplyPolicy class (TypeScript)
   ```typescript
   // sms-agent/agent/auto-reply-policy.ts (NEW FILE)

   export interface AutoReplyDecision {
     shouldReply: boolean;
     reason: string;
   }

   export class AutoReplyPolicy {
     /**
      * Determine if we should auto-reply to this message.
      * Centralized logic for all auto-reply decisions.
      */
     evaluate(context: SMSContext, hasCallback: boolean): AutoReplyDecision {
       const message = context.incomingMessage.toLowerCase().trim();

       // Check 1: Callback configured?
       if (!hasCallback) {
         return {
           shouldReply: false,
           reason: 'No SMS sending callback configured'
         };
       }

       // Check 2: Message length
       if (message.length < 3) {
         return {
           shouldReply: false,
           reason: 'Message too short (might be accidental)'
         };
       }

       // Check 3: Unknown contact
       if (context.contact.trust_level === 0 && !context.contact.relationship) {
         return {
           shouldReply: false,
           reason: 'Unknown contact with no relationship history'
         };
       }

       // Check 4: Urgent keywords
       const urgentKeywords = [
         'urgent', 'emergency', 'important', 'asap', 'help', 'call me',
         'need you', 'problem', 'issue', 'trouble', 'hospital', 'accident'
       ];
       if (urgentKeywords.some(keyword => message.includes(keyword))) {
         return {
           shouldReply: false,
           reason: 'Message contains urgent keywords - needs human attention'
         };
       }

       // All checks passed
       return {
         shouldReply: true,
         reason: 'Casual message from known contact'
       };
     }
   }
   ```

2. **Step 2**: Update SMSProcessor to use policy
   ```typescript
   // sms-agent/agent/sms-processor.ts

   import { AutoReplyPolicy } from './auto-reply-policy';

   export class SMSProcessor {
     private db: SMSDatabase;
     private agent: SMSAgent;
     private onSendSMS?: (sms: OutgoingSMS) => Promise<void>;
     + private autoReplyPolicy: AutoReplyPolicy;

     constructor(
       database: SMSDatabase,
       sendSMSCallback?: (sms: OutgoingSMS) => Promise<void>
     ) {
       this.db = database;
       this.agent = new SMSAgent();
       this.onSendSMS = sendSMSCallback;
       + this.autoReplyPolicy = new AutoReplyPolicy();
     }

     async processSMS(sms: IncomingSMS): Promise<ProcessingResult> {
       // ... get contact, save message, get history ...

       const context = {
         contact,
         conversationHistory,
         incomingMessage: sms.body
       };

       // FIXED: Single centralized decision
       - const shouldReply = await this.agent.shouldAutoReply(context);
       + const decision = this.autoReplyPolicy.evaluate(
       +   context,
       +   this.onSendSMS !== undefined
       + );

       - if (shouldReply) {
       + if (decision.shouldReply) {
         const response = await this.agent.generateResponse(context);

         - if (this.onSendSMS && response) {
         + if (response) {  // Already checked in policy
           await this.onSendSMS({
             to: sms.from,
             body: response
           });
           // ... save message ...
         }
       + } else {
       +   console.log(`Auto-reply skipped: ${decision.reason}`);
       }

       return result;
     }
   }
   ```

3. **Step 3**: Remove shouldAutoReply from SMSAgent
   ```typescript
   // sms-agent/agent/sms-agent.ts

   export class SMSAgent {
     // REMOVED: shouldAutoReply method
     - async shouldAutoReply(context: SMSContext): Promise<boolean> {
     -   // ... all the business logic ...
     - }

     // KEEP: Only AI generation responsibility
     async generateResponse(context: SMSContext): Promise<string> {
       // ... Claude API call ...
     }
   }
   ```

4. **Step 4**: Implement same pattern in Python
   ```python
   # sms-agent-python/agent/auto_reply_policy.py (NEW FILE)

   from dataclasses import dataclass
   from .sms_agent import SMSContext

   @dataclass
   class AutoReplyDecision:
       """Result of auto-reply policy evaluation."""
       should_reply: bool
       reason: str

   class AutoReplyPolicy:
       """Centralized auto-reply decision logic."""

       def evaluate(self, context: SMSContext, has_callback: bool) -> AutoReplyDecision:
           """Determine if we should auto-reply to this message."""
           message = context.incoming_message.lower().strip()

           # Check 1: Callback configured?
           if not has_callback:
               return AutoReplyDecision(
                   should_reply=False,
                   reason="No SMS sending callback configured"
               )

           # Check 2: Message length
           if len(message) < 3:
               return AutoReplyDecision(
                   should_reply=False,
                   reason="Message too short (might be accidental)"
               )

           # Check 3: Unknown contact
           if context.contact.trust_level == 0 and not context.contact.relationship:
               return AutoReplyDecision(
                   should_reply=False,
                   reason="Unknown contact with no relationship history"
               )

           # Check 4: Urgent keywords
           urgent_keywords = [
               'urgent', 'emergency', 'important', 'asap', 'help', 'call me',
               'need you', 'problem', 'issue', 'trouble', 'hospital', 'accident'
           ]
           if any(keyword in message for keyword in urgent_keywords):
               return AutoReplyDecision(
                   should_reply=False,
                   reason="Message contains urgent keywords - needs human attention"
               )

           # Check 5: Sensitive keywords
           sensitive_keywords = [
               'password', 'ssn', 'social security', 'bank', 'credit card',
               'pin', 'address', 'personal', 'private'
           ]
           if any(keyword in message for keyword in sensitive_keywords):
               return AutoReplyDecision(
                   should_reply=False,
                   reason="Message requests sensitive information"
               )

           # All checks passed
           return AutoReplyDecision(
               should_reply=True,
               reason="Casual message from known contact"
           )
   ```

5. **Step 5**: Add comprehensive tests
   ```typescript
   // sms-agent/agent/auto-reply-policy.test.ts

   describe('AutoReplyPolicy', () => {
     let policy: AutoReplyPolicy;

     beforeEach(() => {
       policy = new AutoReplyPolicy();
     });

     test('rejects when no callback configured', () => {
       const context = createTestContext('Hello!');
       const decision = policy.evaluate(context, false);

       expect(decision.shouldReply).toBe(false);
       expect(decision.reason).toContain('callback');
     });

     test('rejects very short messages', () => {
       const context = createTestContext('Hi');
       const decision = policy.evaluate(context, true);

       expect(decision.shouldReply).toBe(false);
       expect(decision.reason).toContain('too short');
     });

     test('rejects unknown contacts', () => {
       const context = createTestContext('Hello', {
         trust_level: 0,
         relationship: undefined
       });
       const decision = policy.evaluate(context, true);

       expect(decision.shouldReply).toBe(false);
       expect(decision.reason).toContain('Unknown contact');
     });

     test('rejects urgent messages', () => {
       const context = createTestContext('This is urgent!');
       const decision = policy.evaluate(context, true);

       expect(decision.shouldReply).toBe(false);
       expect(decision.reason).toContain('urgent');
     });

     test('accepts casual messages from known contacts', () => {
       const context = createTestContext('Hey, how are you?', {
         trust_level: 2,
         relationship: 'friend'
       });
       const decision = policy.evaluate(context, true);

       expect(decision.shouldReply).toBe(true);
     });
   });
   ```

### Alternative Approaches

**Option A**: Keep current split but document it
- Pros: No code changes
- Cons: Doesn't address maintenance issues
- **Not recommended**

**Option B**: Move all logic to Processor
- Pros: Centralized in orchestration layer
- Cons: Processor becomes bloated, mixing concerns
- **Not recommended**

**Option C**: Move all logic to Agent
- Pros: Business logic stays with AI layer
- Cons: Agent shouldn't know about callback availability
- **Not recommended**

**Recommendation**: Create dedicated Policy class (recommended solution) - clear separation of concerns.

## Acceptance Criteria

- [ ] `AutoReplyPolicy` class created in both TypeScript and Python
- [ ] All auto-reply logic moved to Policy class
- [ ] `SMSProcessor` delegates decision to Policy
- [ ] `SMSAgent.shouldAutoReply()` method removed
- [ ] Policy returns decision WITH reason (for logging/debugging)
- [ ] All auto-reply test scenarios pass
- [ ] Decision logging includes reason
- [ ] Documentation updated

**Definition of Done**:
- [ ] Code changes implemented in both projects
- [ ] Comprehensive unit tests for Policy class
- [ ] Integration tests verify end-to-end flow
- [ ] All existing tests updated and passing
- [ ] ADR created documenting Policy pattern
- [ ] Code review approved

## Effort Estimation

**Size**: Medium

**Estimated Complexity**:
- 3-4 days across both implementations
- Clear solution but touches multiple files
- Need to update tests
- Both TypeScript and Python

**Breakdown**:
- Design Policy class interface: 2 hours
- Implement TypeScript Policy: 3 hours
- Implement Python Policy: 3 hours
- Update both Processors: 2 hours
- Update both Agents: 1 hour
- Write Policy tests: 4 hours
- Update integration tests: 3 hours
- Documentation: 2 hours

## Dependencies

**Blocks**: None

**Blocked By**:
- COUPLING-002 (shared rules) would complement this but not required

**Related Issues**:
- COUPLING-002: Duplicated business logic (can be solved together)
- Consider combining Policy class with shared rules approach

## Migration Strategy

**Phase 1**: Create Policy class (non-breaking addition)
**Phase 2**: Update Processor to use Policy
**Phase 3**: Remove shouldAutoReply from Agent
**Phase 4**: Deploy and monitor
**Phase 5**: Update documentation

No breaking external API changes.

## Prevention Strategy

- [ ] Document "Policy Pattern for Business Rules" in architecture guide
- [ ] Add code review checklist: "Business logic centralized in appropriate layer?"
- [ ] Create ADR explaining Policy pattern usage
- [ ] Add linting rule to detect split responsibilities (difficult but possible)
- [ ] Team training on separation of concerns

## Additional Context

**Related Documentation**:
- Policy pattern: https://en.wikipedia.org/wiki/Policy_pattern
- Strategy pattern: https://refactoring.guru/design-patterns/strategy

**Historical Context**:
- Initial implementation had logic in Agent because it seemed "AI-related"
- Processor grew to need some checks (callback availability)
- No refactoring occurred when logic started splitting
- Both implementations independently developed the same split

**Questions for Discussion**:
- Should Policy be stateless or maintain configuration?
- Should we support runtime rule updates?
- Should different deployment environments have different policies?
- Should Policy be injectable for testing?

## Benefits of This Refactoring

1. **Single Responsibility**: Policy owns ALL auto-reply decisions
2. **Testability**: One class to test for all scenarios
3. **Maintainability**: One place to update when rules change
4. **Clarity**: Clear contract with `AutoReplyDecision` return type
5. **Debugging**: Decision reason included for logging
6. **Extensibility**: Easy to add new checks to Policy

## Pattern

This follows the **Policy Pattern** / **Strategy Pattern** where a separate object encapsulates an algorithm or business rule, allowing it to vary independently from the clients that use it.

```
┌─────────────────┐
│  SMSProcessor   │──┐
│  (orchestrate)  │  │
└─────────────────┘  │
                     │ uses
┌─────────────────┐  │
│   SMSAgent      │  │
│  (generate AI)  │  │
└─────────────────┘  │
                     ▼
               ┌──────────────────┐
               │ AutoReplyPolicy  │
               │  (decide rules)  │
               └──────────────────┘
```
