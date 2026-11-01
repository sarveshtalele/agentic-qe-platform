# Runner Adapter Command Registry

Only these commands are allowed by the skill's `allowed-tools`. Use no other runner command.

| Framework | Default Command | Report Format / Output Path |
| :--- | :--- | :--- |
| **Playwright** | `npx --no-install playwright test` | JUnit reporter is set in the generated `playwright.config.ts` template: `results/junit.xml`, plus `results/playwright.json` |
| **Vitest** | `npx --no-install vitest run --reporter=junit --outputFile=results/junit.xml` | `results/junit.xml` |
| **PyTest** | `python -m pytest` (or `pytest`) with `--junitxml=results/junit.xml -v` | `results/junit.xml` |
| **JUnit (Maven)** | `mvn test` | `target/surefire-reports/*.xml` |
| **JUnit (Gradle)** | `./gradlew test` | `build/test-results/test/*.xml` |
| **Node test runner** | `node --test` | TAP on stdout |
| **.NET (NUnit, xUnit, MSTest)** | `dotnet test <test-project> --filter "Category=<Level>" --logger "trx;LogFileName=<level>-dotnet.xml" --results-directory results` | `results/<level>-dotnet.xml`: TRX content with an `.xml` name, so the panel, gate reports and `parse-junit.ts` read it like JUnit. Run `dotnet build` first only when the user approves it; `dotnet test` builds by itself. Build with `dotnet build <proj> -nodeReuse:false` (MSBuild node reuse hangs in sandboxes). nopCommerce-style plugin projects need `-p:SolutionDir=<repo>/src/` when built outside the solution |
