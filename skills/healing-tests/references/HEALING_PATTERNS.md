# Remediation & Healing Patterns

| Failure Category | Evidence Signature | Permitted Remediation | Forbidden Actions |
| :--- | :--- | :--- | :--- |
| **Selector Drift** | `TimeoutError: locator.click: Target closed` on `#submit-btn` | Update selector to new DOM attribute (e.g. `getByRole('button', { name: 'Submit' })`) | Deleting the interaction step |
| **Fixture Outdated** | `400 Bad Request` due to missing required schema field | Add missing mock attribute to test fixture payload | Removing the API request |
| **Real App Bug** | `500 Internal Server Error`, `NullPointerException` | **NO TEST MODIFICATION.** Log defect in `07-healing/audit_log.json` | Weakening assertion from `toBe(200)` to `toBeDefined()` |
