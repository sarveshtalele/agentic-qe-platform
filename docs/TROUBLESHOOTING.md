# Troubleshooting

## `ModuleNotFoundError` or missing packages

Activate the virtual environment, then run `python -m pip install -r requirements.txt`. When several Python installations are present, use the same interpreter for both installation and startup: `python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000`.

## Port 8000 is already in use

Choose another port, e.g. `python -m uvicorn backend.app:app --host 127.0.0.1 --port 8001`, then open `http://127.0.0.1:8001`. If using the synthetic seeder, set `FORGESDLC_API_URL` to that port before running it.

## Local repository path is rejected

The repository must exist under the `SDLC_WORKSPACE_ROOT` directory shown in Settings. A relative path is resolved under that root. If you need a different parent directory, stop the app, set `SDLC_WORKSPACE_ROOT` in `.env` to a directory you trust, and restart it. Symlinks resolving outside the root are rejected.

## Repository ZIP upload fails

The archive must be a valid `.zip`, smaller than `SDLC_MAX_UPLOAD_MB`, and its extracted contents must remain below `SDLC_MAX_ARCHIVE_MB`. Traversal entries such as `../file`, absolute paths and symbolic links are rejected/skipped. Secrets, key files, generated caches and dependency folders are deliberately not extracted. A monorepo or archive with many entries may require a smaller curated ZIP.

## Document extraction fails or returns empty text

Confirm that the file extension is supported and the document is not corrupted/password-protected. Scanned PDFs can have no selectable text; this MVP does not include OCR. DOCX, XLSX and PPTX extraction focuses on text and tables and may not preserve styling or complex layouts. Re-upload a text/Markdown/CSV rendition if appropriate.

## Requirements generation says no candidates were found

Select the correct source document or enter a clear objective. Without a configured AI endpoint, the local heuristic favours concise sentences containing action/obligation language; it is intentionally not a full language model. Generated records remain drafts and may need manual rewriting. In Settings, verify `SDLC_LLM_BASE_URL` and `SDLC_LLM_MODEL` only if a compatible endpoint is configured and reachable.

## Test run is `Blocked`

Repository command execution is disabled by default. Review the repo first; if you trust it, set `SDLC_ENABLE_REPO_COMMANDS=true` in `.env`, restart the app and retry. Tests are not sandboxed and can access files or networks available to the app process. If enabled but no command is detected, the MVP supports Python pytest and `npm test` only.

## Test run failed

Open the Test Center run record and inspect the actual exit code, stdout and stderr. Common causes include missing test dependencies, environment variables, databases/services, or a test command whose expected setup isn't installed. A failed or blocked command is not reported as passing. The test-runner timeout is set by `SDLC_COMMAND_TIMEOUT_SECONDS`.

## ZIP export is missing files

Open `SDLC_EXPORT_MANIFEST.json` in the archive. `.git`, `node_modules`, virtual environments, build caches, sensitive files, local environment files, common key formats and files over the inspection limit are intentionally excluded. Source ZIPs are a snapshot package, not a full Git clone. The export endpoint checks the archive before registering the download.

## SQLite or storage permissions

Confirm the app user can write to `SDLC_DATA_DIR` and `SDLC_WORKSPACE_ROOT`. Stop Uvicorn before copying/restoring the data folder. Avoid opening multiple app processes against the same write workspace unless you understand SQLite concurrency and the shared files.

## Settings show no GitHub integration

This MVP does not implement the GitHub OAuth repository picker. A `GITHUB_TOKEN` environment variable only displays configuration status; it is not currently used to authenticate a remote repository operation. Use a local checkout inside the allowed workspace or upload a repository ZIP.
