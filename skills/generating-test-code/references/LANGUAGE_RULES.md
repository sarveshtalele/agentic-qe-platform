# Language & Framework Specific Generation Rules

Gate 4 approves the diff. After approval, compile first and treat compile errors as drift to heal before running the tests.

### TypeScript / JavaScript (Playwright & Vitest)
- ESM import syntax: `import { test, expect } from '@playwright/test';`
- Target base URL: read dynamically via `process.env.BASE_URL || 'http://localhost:3000'`.
- Resilient locators: prefer `getByRole`, `getByTestId`, `getByText` over brittle XPath.

#### Playwright UI tests (opt-in)
- Pinned versions are in [VERSIONS.md](VERSIONS.md). Read the base URL from `process.env.BASE_URL`.
- Prefer `getByRole`, `getByLabel`, `getByTestId`; avoid CSS/XPath chains.
- Copy [../assets/playwright.config.ts](../assets/playwright.config.ts) to the project root as `playwright.config.ts` for every UI suite (automatic screenshot on failure, trace on failure, JUnit + JSON + HTML reporters; step screenshots are attached explicitly).
- Wrap each meaningful step in `await test.step('<step text from the case>', async () => { ... })`.
- After key assertions attach a screenshot: `await test.info().attach('<CASE_ID> step N', { body: await page.screenshot(), contentType: 'image/png' })`.
- If the Playwright MCP server is connected (tools `mcp__playwright__browser_navigate`, `mcp__playwright__browser_snapshot`), call `browser_snapshot` to read the real accessibility tree before writing locators. Otherwise read the page source.
- MCP setup is opt-in and never auto-started; see [VERSIONS.md](VERSIONS.md).

### Python (PyTest)
- Module naming: `test_<feature>_<case_id>.py`.
- Fixture management: leverage `tmp_path`, `monkeypatch`, or standard pytest fixtures.
- Async support: use `@pytest.mark.asyncio` or `anyio`.

### Java (JUnit 5 / AssertJ)
- Annotations: `@Test`, `@DisplayName`, `@Tag`.
- Assertions: prefer AssertJ `assertThat(actual).isEqualTo(expected)`.

### C# (.NET: NUnit, xUnit, MSTest)
- Use the framework the project's test project already references (scan-repo reports `nunit`, `xunit` or `mstest`); add new tests to that test project, never a new one, so they build with the existing helpers and data provider.
- One test class per case, in its own file: `TcApp001<Scenario>Tests.cs`; the method name starts with the case ID, `Tc_App_001_<Scenario>`, so `parse-junit.ts` maps the TRX result back to `TC-APP-001`.
- Level: NUnit `[Category("Unit")]` / `[Category("Integration")]`; xUnit `[Trait("Category", "Unit")]`; MSTest `[TestCategory("Unit")]`. `dotnet test --filter "Category=Unit"` selects a level.
- Assertions: use the assertion library the project already uses (for example AwesomeAssertions or FluentAssertions `actual.Should().Be(expected)`, or `Assert.That`).
- Reuse the project's base test class and service resolution (for example `BaseNopTest.GetService<T>()`) instead of building a container by hand.
- Test settings in nopCommerce-style test bases are transient: set them inside each test, never rely on a value from another test or a one-time setup.
- Constructing a controller in a test can overflow the test thread stack; prefer service-level tests.
- E2E tooling (`node_modules`, reports, results) must not live inside the test source folder; put E2E output under `docs/qe/<app>/06-execution/evidence/`.
