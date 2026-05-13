"""Runtime configuration endpoints — projects, roles, etc.

These surfaces let the dashboard render an operator-customized vocabulary
without rebuilding the frontend. The values are loaded at server import
time from yaml config; restart the server to pick up changes.
"""

from fastapi import APIRouter

from server.constants import PROJECTS
from server.roles import ROLES

router = APIRouter()


@router.get("/api/config/roles")
def get_roles() -> dict:
    """Return the operator-configured role vocabulary."""
    return {"roles": ROLES}


@router.get("/api/config/projects")
def get_projects() -> dict:
    """Return the operator-configured project registry.

    Frontend uses this to derive GitHub links and to render the project
    switcher — no more hardcoded project lists in the React bundle.
    """
    return {
        "projects": [
            {"slug": slug, "repo": repo} for slug, repo in sorted(PROJECTS.items())
        ]
    }
