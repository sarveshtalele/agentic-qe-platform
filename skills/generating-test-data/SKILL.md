---
name: generating-test-data
description: Generates deterministic synthetic test fixtures, schema mocks, and boundary edge datasets. Use when preparing test data for test execution.
metadata:
  author: Sarvesh Talele
  version: "1.4.0"
---

# Generating Test Data

Synthesizes high-fidelity mock fixtures conforming to application JSON schemas, TypeScript types, or database tables.

## When to use
Activate when the data stage runs (plugin command `qe-data`), or when creating mock payloads and test fixtures for test automation suites.

## Features
- **Schema Conformance:** Strictly respects required fields, types, formats, and ranges.
- **Negative & Edge Fixtures:** Generates out-of-bound numbers, malformed emails, nulls, and special characters.
- **Data Privacy & Masking:** Never embeds actual secrets or real user PII in synthetic fixtures.

## Workflow
1. Read the schemas, types or migrations the cases refer to. Take field rules from [assets/schema-templates.json](assets/schema-templates.json).
2. Build valid, invalid and boundary datasets, masking anything that looks like PII or a credential.
3. Produce `04-design/fixtures.json` (ask before creating it).

## Platform code step
The platform generates the datasets in code (planned: `qe/test_data.py`, not yet built). Given `{"kind":"user|boundary|pagination|auth", ...}`, it returns deterministic JSON and writes nothing. The shape for each kind is defined by that port once it exists.
