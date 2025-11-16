# [COUPLING] [CRITICAL]: Duplicated SMS auto-reply business logic across TypeScript and Python implementations

**Issue ID**: COUPLING-002
**Severity**: Critical
**Type**: Symmetric Functional Coupling
**Date Identified**: 2025-10-18
**Applications**: sms-agent, sms-agent-python

---

## Problem Statement

Identical business rules for SMS auto-reply logic are independently implemented in both the TypeScript (`sms-agent`) and Python (`sms-agent-python`) versions of the SMS Response Assistant. This creates symmetric functional coupling where the same business logic exists in multiple places, increasing the risk of inconsistency, bugs, and maintenance burden.

## Current State

**Location**:
- Files:
  - `sms-agent/agent/sms-agent.ts:78-101` (shouldAutoReply method)
  - `sms-agent-python/agent/sms_agent.py:120-151` (should_auto_reply method)
- Module(s): agent layer in both applications
- Owner(s): sms-agent team

**Coupling Type**: Symmetric Functional Coupling (Duplicated Business Logic)
**Degree**: Connascence of Algorithm (CoA) - same algorithms implemented independently

**Evidence**:

**TypeScript Implementation:**
```typescript
// sms-agent/agent/sms-agent.ts:78-101
async shouldAutoReply(context: SMSContext): Promise<boolean> {
  const message = context.incomingMessage.toLowerCase().trim();

  // Don't auto-reply to very short messages (might be accidental)
  if (message.length < 3) {
    return false;
  }

  // Don't auto-reply to unknown contacts with no relationship
  if (context.contact.trust_level === 0 && !context.contact.relationship) {
    return false;
  }

  // Don't auto-reply to messages that seem urgent/need human attention
  const urgentKeywords = [
    'urgent', 'emergency', 'important', 'asap', 'help', 'call me',
    'need you', 'problem', 'issue', 'trouble', 'hospital', 'accident'
  ];

  if (urgentKeywords.some(keyword => message.includes(keyword))) {
    return false;
  }

  // Auto-reply to casual messages from known contacts
  return true;
}
```

**Python Implementation:**
```python
# sms-agent-python/agent/sms_agent.py:120-151
async def should_auto_reply(self, context: SMSContext) -> bool:
    """Determine if we should automatically reply to this message."""
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

    # Don't auto-reply to questions about sensitive information
    sensitive_keywords = [
        'password', 'ssn', 'social security', 'bank', 'credit card',
        'pin', 'address', 'personal', 'private'
    ]

    if any(keyword in message for keyword in sensitive_keywords):
        return False

    # Auto-reply to casual messages from known contacts
    return True
```

**Discrepancy Found**: Python version has additional sensitive_keywords check that TypeScript version lacks!

## Impact Assessment

**Severity**: Critical

**Why This Matters**:
- **Business rule inconsistency**: The two implementations already differ (sensitive keywords missing in TS)
- **Maintenance burden**: Every business rule change must be made twice, in two languages
- **Increased bug risk**: Easy to update one implementation and forget the other
- **Testing complexity**: Must maintain identical test suites in two languages
- **User experience**: Behavior differs between Python and TypeScript deployments

**Blast Radius**:
- Modules affected: 2 complete applications
- Teams affected: 1 team maintaining 2 implementations
- Deployment environments: Any environment could use either implementation with different behavior

**Risk Factors**:
- Change frequency: High - business rules for auto-reply will evolve based on user feedback
- Failure probability: High - already out of sync (sensitive keywords check missing)
- Detection difficulty: High - requires cross-language code review to notice discrepancies

## Current Behavior vs. Expected Behavior

**Current**:
- TypeScript: Checks trust level, message length, and urgent keywords
- Python: Checks trust level, message length, urgent keywords, AND sensitive keywords

**Expected**: Identical business logic across both implementations, with single source of truth for rules

**Violated Principle(s)**:
- **Don't Repeat Yourself (DRY)**: Same business logic implemented twice
- **Single Source of Truth**: Business rules should be defined once
- **Consistency**: Different implementations produce different behavior

## Remediation Plan

### Recommended Solution

Create a shared, language-agnostic business rules configuration that both implementations consume.

**Design Strategy**:
1. Extract business rules to shared configuration file (YAML or JSON)
2. Both implementations load and interpret the same rules file
3. Centralize rule schema and validation
4. Add tests to ensure both implementations interpret rules identically
5. Document the shared rules format

### Specific Steps

1. **Step 1**: Create shared rules configuration
   ```yaml
   # shared-config/sms-auto-reply-rules.yaml
   auto_reply_rules:
     version: "1.0"

     checks:
       - name: "minimum_message_length"
         type: "length_check"
         threshold: 3
         fail_action: "skip_auto_reply"
         reason: "Message too short (might be accidental)"

       - name: "unknown_contact_check"
         type: "contact_trust"
         condition:
           trust_level: 0
           relationship: null
         fail_action: "skip_auto_reply"
         reason: "Unknown contact with no relationship"

       - name: "urgent_keywords"
         type: "keyword_match"
         keywords:
           - urgent
           - emergency
           - important
           - asap
           - help
           - call me
           - need you
           - problem
           - issue
           - trouble
           - hospital
           - accident
         fail_action: "skip_auto_reply"
         reason: "Message contains urgent keywords requiring human attention"

       - name: "sensitive_keywords"
         type: "keyword_match"
         keywords:
           - password
           - ssn
           - social security
           - bank
           - credit card
           - pin
           - address
           - personal
           - private
         fail_action: "skip_auto_reply"
         reason: "Message requests sensitive information"
   ```

2. **Step 2**: Update TypeScript implementation
   ```typescript
   // sms-agent/agent/auto-reply-rules.ts (NEW FILE)
   import * as fs from 'fs';
   import * as yaml from 'yaml';
   import type { SMSContext } from './sms-agent';

   interface AutoReplyRules {
     auto_reply_rules: {
       version: string;
       checks: RuleCheck[];
     };
   }

   interface RuleCheck {
     name: string;
     type: string;
     threshold?: number;
     condition?: any;
     keywords?: string[];
     fail_action: string;
     reason: string;
   }

   export class AutoReplyRuleEngine {
     private rules: AutoReplyRules;

     constructor(rulesPath: string = '../../shared-config/sms-auto-reply-rules.yaml') {
       const rulesFile = fs.readFileSync(rulesPath, 'utf8');
       this.rules = yaml.parse(rulesFile);
     }

     shouldAutoReply(context: SMSContext): boolean {
       const message = context.incomingMessage.toLowerCase().trim();

       for (const check of this.rules.auto_reply_rules.checks) {
         if (!this.passesCheck(check, context, message)) {
           console.log(`Auto-reply skipped: ${check.reason}`);
           return false;
         }
       }

       return true;
     }

     private passesCheck(check: RuleCheck, context: SMSContext, message: string): boolean {
       switch (check.type) {
         case 'length_check':
           return message.length >= (check.threshold || 0);

         case 'contact_trust':
           if (check.condition) {
             return !(context.contact.trust_level === check.condition.trust_level &&
                      !context.contact.relationship);
           }
           return true;

         case 'keyword_match':
           if (check.keywords) {
             return !check.keywords.some(keyword => message.includes(keyword));
           }
           return true;

         default:
           console.warn(`Unknown check type: ${check.type}`);
           return true;
       }
     }
   }

   // Update sms-agent.ts:
   import { AutoReplyRuleEngine } from './auto-reply-rules';

   export class SMSAgent {
     private ruleEngine: AutoReplyRuleEngine;

     constructor() {
       this.system_prompt = `...`;
       this.ruleEngine = new AutoReplyRuleEngine();
     }

     async shouldAutoReply(context: SMSContext): Promise<boolean> {
       return this.ruleEngine.shouldAutoReply(context);
     }
   }
   ```

3. **Step 3**: Update Python implementation
   ```python
   # sms-agent-python/agent/auto_reply_rules.py (NEW FILE)
   import yaml
   from pathlib import Path
   from typing import Dict, Any, List
   from .sms_agent import SMSContext

   class AutoReplyRuleEngine:
       """Rule engine for SMS auto-reply logic."""

       def __init__(self, rules_path: str = "../../shared-config/sms-auto-reply-rules.yaml"):
           with open(rules_path, 'r') as f:
               self.rules = yaml.safe_load(f)

       def should_auto_reply(self, context: SMSContext) -> bool:
           """Determine if we should automatically reply based on rules."""
           message = context.incoming_message.lower().strip()

           for check in self.rules['auto_reply_rules']['checks']:
               if not self._passes_check(check, context, message):
                   print(f"Auto-reply skipped: {check['reason']}")
                   return False

           return True

       def _passes_check(self, check: Dict[str, Any], context: SMSContext, message: str) -> bool:
           """Evaluate a single rule check."""
           check_type = check['type']

           if check_type == 'length_check':
               return len(message) >= check.get('threshold', 0)

           elif check_type == 'contact_trust':
               if 'condition' in check:
                   cond = check['condition']
                   return not (context.contact.trust_level == cond.get('trust_level') and
                              not context.contact.relationship)
               return True

           elif check_type == 'keyword_match':
               if 'keywords' in check:
                   return not any(keyword in message for keyword in check['keywords'])
               return True

           else:
               print(f"Unknown check type: {check_type}")
               return True

   # Update sms_agent.py:
   from .auto_reply_rules import AutoReplyRuleEngine

   class SMSAgent:
       """Claude-powered SMS response generator."""

       def __init__(self):
           self.system_prompt = """..."""
           self.rule_engine = AutoReplyRuleEngine()

       async def should_auto_reply(self, context: SMSContext) -> bool:
           """Determine if we should automatically reply to this message."""
           return self.rule_engine.should_auto_reply(context)
   ```

4. **Step 4**: Add cross-implementation tests
   ```typescript
   // shared-config/test-auto-reply-rules.test.ts
   import { AutoReplyRuleEngine } from '../sms-agent/agent/auto-reply-rules';

   describe('Auto-Reply Rules - Cross-Implementation Tests', () => {
     test('Both implementations should skip very short messages', () => {
       // Test case that should work identically in both TS and Python
     });

     test('Both implementations should skip urgent keywords', () => {
       // Ensure identical behavior
     });

     test('Both implementations should skip sensitive keywords', () => {
       // This currently fails for TypeScript!
     });
   });
   ```

### Alternative Approaches

**Option A**: Make Python canonical, port rules to TypeScript manually
- Pros: Quick fix, no infrastructure changes
- Cons: Doesn't solve root problem, will drift again
- **Not recommended**

**Option B**: Deprecate one implementation entirely
- Pros: Eliminates duplication permanently
- Cons: May not be feasible if both are deployed
- **Consider as longer-term strategy**

**Option C**: Generate code from rules using codegen tool
- Pros: True single source of truth
- Cons: Complex build pipeline, harder to debug
- **Future consideration** if rules become very complex

**Recommendation**: Option with shared configuration file (recommended solution above) - balances maintainability with practicality.

## Acceptance Criteria

- [ ] Shared rules configuration file created
- [ ] TypeScript implementation loads and interprets shared rules
- [ ] Python implementation loads and interprets shared rules
- [ ] Both implementations produce identical behavior for same inputs
- [ ] All auto-reply test cases pass in both implementations
- [ ] Cross-implementation test suite validates identical behavior
- [ ] Sensitive keywords check now present in TypeScript
- [ ] Documentation explains how to modify business rules

**Definition of Done**:
- [ ] Code changes implemented in both projects
- [ ] Shared config file version controlled
- [ ] Unit tests updated in both languages
- [ ] Cross-language integration tests added
- [ ] ADR created documenting shared rules approach
- [ ] Team training on how to update rules

## Effort Estimation

**Size**: Medium

**Estimated Complexity**:
- 1 week of development
- Requires changes in both codebases
- Need to set up shared configuration
- Cross-language testing infrastructure

**Breakdown**:
- Design shared rules schema: 4 hours
- Create YAML configuration: 2 hours
- Implement TypeScript rule engine: 6 hours
- Implement Python rule engine: 6 hours
- Cross-implementation tests: 8 hours
- Documentation: 4 hours
- Testing and validation: 6 hours

## Dependencies

**Blocks**:
- Future business rule changes (need single source of truth first)
- Potential third implementation in other language

**Blocked By**: None

**Related Issues**:
- COUPLING-004: Business rules split across layers (separate but related)

## Migration Strategy

**Phase 1**: Create shared rules file with current Python rules (most complete)
**Phase 2**: Implement rule engine in TypeScript (non-breaking addition)
**Phase 3**: Implement rule engine in Python (non-breaking addition)
**Phase 4**: Update both SMSAgent classes to use new rule engines
**Phase 5**: Remove old hardcoded rule methods
**Phase 6**: Add CI check to validate rule file schema

No breaking API changes - internal refactoring only.

## Prevention Strategy

- [ ] Add CI check to validate shared rules YAML schema
- [ ] Add cross-implementation test suite that runs on every PR
- [ ] Document "Adding New Auto-Reply Rules" process
- [ ] Create ADR documenting why shared config is used
- [ ] Add pre-commit hook to validate YAML syntax
- [ ] Set up monitoring to alert if implementations diverge in production

## Additional Context

**Related Documentation**:
- YAML for configuration: https://yaml.org/
- Strategy pattern: https://refactoring.guru/design-patterns/strategy

**Historical Context**:
- Python implementation was created after TypeScript
- Appears to have been manually ported with "improvements"
- No process existed to keep implementations in sync
- Discrepancy (sensitive keywords) was discovered during this audit

**Questions for Discussion**:
- Should we deprecate one implementation long-term?
- Should rules be editable at runtime or compile-time only?
- Do we need different rules for different deployment environments?
- Should the rule engine support more complex logic (boolean expressions)?
