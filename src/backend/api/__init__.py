"""REST API, one router per area."""
from backend.api import auth, chat, documents, findings, governance, logs, observability, projects, repository, runs, settings, templates

ROUTERS = [auth.router, chat.router, documents.router, findings.router, governance.router, logs.router, observability.router, projects.router, repository.router, runs.router, settings.router, templates.router]
