# Deterministic Test Oracle Types

| Oracle Kind | Source / Basis | Definition & Example |
| :--- | :--- | :--- |
| **`specified`** | Documentation or Spec | Expected result quoted verbatim from a functional spec or README (`"Returns HTTP 404 on missing ID"`). |
| **`derived`** | Implementation Source | Expected outcome mathematically derived from source code logic (`tax = amount * rate` -> 100 * 0.2 = 20). |
| **`metamorphic`** | Invariant Relation | Relationship between consecutive executions: determinism (same input -> same output), irrelevant-input invariance, or ordering invariance. |
| **`golden`** | Manual Formula Derivation | Hand-derived result from an established domain algorithm or reference test vector. |
