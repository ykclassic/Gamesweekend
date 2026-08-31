"""Production WSGI entry point.

Import the core Flask application first, then register participant-facing
routes/context processors before exposing the application to Gunicorn.
This keeps the application working even when Render uses this WSGI module
instead of importing participant_routes directly.
"""

from app import app
import participant_routes  # noqa: F401,E402  # registers routes on app

__all__ = ["app"]
