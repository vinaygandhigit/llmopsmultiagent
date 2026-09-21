"""Small shared helpers for talking to LangSmith outside of @traceable's
automatic instrumentation (feedback and quality scoring need a live Client).
"""
from __future__ import annotations

import os

from langsmith import Client

_project_id_cache: str | None = None
_project_id_resolved = False


def resolve_project_id(client: Client) -> str | None:
    """Resolve the LangSmith project (session) UUID for LANGSMITH_PROJECT.

    RunTree objects only carry the project *name* locally (session_id is
    assigned server-side), but Client.create_feedback wants the project UUID
    as `session_id` to avoid a deprecation warning. Resolved once per process
    and cached, since the project doesn't change at runtime.
    """
    global _project_id_cache, _project_id_resolved
    if _project_id_resolved:
        return _project_id_cache

    project_name = os.getenv("LANGSMITH_PROJECT")
    if project_name:
        try:
            _project_id_cache = str(client.read_project(project_name=project_name).id)
        except Exception:
            _project_id_cache = None
    _project_id_resolved = True
    return _project_id_cache