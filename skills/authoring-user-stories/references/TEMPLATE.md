# User Story and Test Case Template

## Story
```
**US-<APP>-NNN**: As a <user/role>, I want to <functionality/action> so that <business benefit/value>.

Priority: P1 | P2 | P3
Acceptance criteria:
1. Given <context>, When <action>, Then <outcome>.
```

## Test case table
Exactly these columns, in this order:

| TC ID | User Story ID | Scenario | Type | Precondition | Test Data | Steps | Expected Result | Priority | Automation Candidate | Remarks |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |

- **Type:** `Positive`, `Negative`, `Exception`. Boundary cases are `Negative (Boundary)`.
- **Minimums per story:** 1 Positive, 2 Negative (boundary counts), 1 Exception.
- **Priority:** P1 (critical) to P3 (nice to have). Jira maps P1=High, P2=Medium, P3=Low.
- **Automation Candidate:** `Yes (<tool>)` e.g. `Yes (Playwright)`, or `No`.
- **Steps:** numbered list; in the Markdown table joined with `<br>`.

## cases.json (input of export-cases.ts)
```json
{
  "app": "CALC",
  "stories": [{"id": "US-CALC-001", "role": "user", "action": "add two numbers", "benefit": "I get a quick total", "acceptance": ["Given two numbers, When I press Add, Then the sum is shown"], "priority": "P1"}],
  "cases": [{"tc_id": "TC-001", "story_id": "US-CALC-001", "scenario": "Add 2 and 3", "type": "Positive", "precondition": "Calculator open", "test_data": "2, 3", "steps": ["Enter 2", "Enter 3", "Press Add"], "expected": "Result shows 5", "priority": "P1", "automation": "Yes (Playwright)", "remarks": ""}]
}
```

## Worked example: web calculator

**US-CALC-001**: As a user, I want to add two numbers so that I get a quick total. (P1)
1. Given two numbers, When I press Add, Then the sum is shown.

**US-CALC-002**: As a user, I want to divide two numbers so that I can split values. (P1)
1. Given a non-zero divisor, When I press Divide, Then the quotient is shown.
2. Given a divisor of 0, When I press Divide, Then "Cannot divide by zero" is shown.

| TC ID | User Story ID | Scenario | Type | Precondition | Test Data | Steps | Expected Result | Priority | Automation Candidate | Remarks |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| TC-001 | US-CALC-002 | Divide 10 by 2 | Positive | Calculator open | 10, 2 | 1. Enter 10<br>2. Enter 2<br>3. Press Divide | Result shows 5 | P1 | Yes (Playwright) | |
| TC-002 | US-CALC-002 | Divide by zero | Negative | Calculator open | 10, 0 | 1. Enter 10<br>2. Enter 0<br>3. Press Divide | Error "Cannot divide by zero" | P1 | Yes (Playwright) | |
| TC-003 | US-CALC-002 | Divide by smallest positive | Negative (Boundary) | Calculator open | 1, 0.0000001 | 1. Enter 1<br>2. Enter 0.0000001<br>3. Press Divide | Result 10000000 or overflow notice, no crash | P2 | Yes (Playwright) | |
| TC-004 | US-CALC-002 | Calculation service unavailable | Exception | Backend stubbed to return 500 | 10, 2 | 1. Enter 10 and 2<br>2. Press Divide | Friendly error shown, inputs kept | P2 | Yes (Playwright) | |

(US-CALC-001 needs its own 1 Positive, 2 Negative, 1 Exception rows in the same shape.)
