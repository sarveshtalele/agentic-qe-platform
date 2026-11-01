# Test Level Allocation Guidelines

| Level | Suitable Scenarios | Unsuitable Scenarios | Prototypical Frameworks |
| :--- | :--- | :--- | :--- |
| **Unit** | Internal algorithms, arithmetic, string formatting, parsing, pure state machines | Database queries, network requests, multi-service workflows | Vitest, PyTest, JUnit Jupiter |
| **Integration / API** | Route endpoints, payload serialization, auth middleware, database persistence | UI animation, complex canvas rendering | Supertest, httpx, TestContainers |
| **UI / E2E** | Multi-screen customer journeys, browser navigation, interactive form wizards | Pure business math, backend boundary validation | Playwright, Cypress |
