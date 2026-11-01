# Stack Detection Signals & Rules

| Language | Manifests | Dominant Test Frameworks | Entrypoint Patterns |
| :--- | :--- | :--- | :--- |
| **TypeScript / Node** | `package.json`, `tsconfig.json` | `vitest`, `jest`, `@playwright/test`, `cypress` | `src/index.ts`, `app/page.tsx`, `server.ts` |
| **Python** | `pyproject.toml`, `requirements.txt`, `Pipfile` | `pytest`, `unittest`, `behave` | `main.py`, `app.py`, `wsgi.py`, `src/__init__.py` |
| **Java** | `pom.xml`, `build.gradle` | `junit-jupiter`, `testng`, `cucumber-java` | `src/main/java/**/Application.java` |
| **C# / .NET** | `*.csproj`, `*.sln` | `xunit`, `nunit`, `mstest` | `Program.cs`, `Startup.cs` |
| **Go** | `go.mod` | `testing` (Go native), `testify`, `ginkgo` | `main.go`, `cmd/*/main.go` |
| **Rust** | `Cargo.toml` | `cargo test` (`#[test]`) | `src/main.rs`, `src/lib.rs` |
