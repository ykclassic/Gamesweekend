"""Runtime compatibility and participant-route registration.

Python imports sitecustomize automatically during interpreter startup. We use
that hook for the legacy gspread compatibility shim and to register the
participant-facing routes regardless of whether the WSGI server is started
as ``app:app`` or ``wsgi:app``.
"""

try:
    from gspread.worksheet import Worksheet

    _original_update = Worksheet.update

    def _looks_like_a1_range(value):
        if not isinstance(value, str) or not value:
            return False
        import re
        return bool(
            re.fullmatch(
                r"(?:[A-Za-z]{1,3}\d+(?::[A-Za-z]{1,3}\d+)?|[A-Za-z]{1,3}(?::[A-Za-z]{1,3})?)",
                value,
            )
        )

    def _update_compat(self, values, range_name=None, *args, **kwargs):
        # The application historically used worksheet.update(range, values),
        # while gspread 6.x uses worksheet.update(values, range). Keep both
        # forms safe for deployments that still have the compatibility layer.
        if isinstance(values, str) and range_name is not None:
            if isinstance(range_name, (list, tuple)):
                values, range_name = range_name, values
            elif (
                isinstance(range_name, str)
                and _looks_like_a1_range(values)
                and not _looks_like_a1_range(range_name)
            ):
                values, range_name = range_name, values
        return _original_update(self, values, range_name, *args, **kwargs)

    Worksheet.update = _update_compat
except Exception:
    # Never prevent the application from starting if gspread changes its API.
    pass

# Register participant routes even when Render starts Gunicorn with the legacy
# ``app:app`` command. Importing after the compatibility setup also ensures
# participant route initialization sees the same runtime environment.
try:
    import participant_routes  # noqa: F401,E402
except Exception:
    # Route registration errors must be visible in logs but must not make the
    # entire web process fail to boot.
    import logging
    logging.getLogger(__name__).exception("Unable to register participant routes")
