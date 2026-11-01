# Pinned versions

These pins are time-sensitive; update them here only. `scripts/mcp-evidence.ts` carries the same MCP pin in `DEFAULT_CMD`.

| Tool | Version | Use |
| :--- | :--- | :--- |
| `@playwright/test` | 1.64.1 | UI test runs, with `BASE_URL` set in the environment |
| `@playwright/mcp` | 0.0.83 | `mcp-evidence.ts` drives it headless; opt-in setup: `claude mcp add playwright -- npx -y @playwright/mcp@0.0.83` (project scope: add `--scope project`) |
