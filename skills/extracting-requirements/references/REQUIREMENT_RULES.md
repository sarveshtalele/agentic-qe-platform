# Requirements Reverse-Engineering Rules

1. **Observable Behavior Rule:** Requirements must assert externally observable behavior (HTTP response codes, return values, emitted events, DOM changes). Never assert internal private variable state.
2. **Mandatory Source Quote Rule:** Every requirement must include:
   - `source_file`: relative path to real file.
   - `line_number`: 1-based start line.
   - `quote`: verbatim code snippet copied directly from source.
3. **Precedence Rule:** Executable code strictly takes precedence over comments. If a comment says "Always returns true" but code has an `if (...) return false;` branch, extract the real code behavior.
4. **Actors Rule:** Every requirement names exactly one actor or `system`.
