"""Production WSGI entry point for the participant and admin application.

Participant-facing registration state is read explicitly from Google Sheets on
GET / instead of depending on a template context processor. This guarantees
that the landing page and admin dashboard use the same authoritative F1 value.
"""

import time

from flask import render_template, request

from app import app, get_event_status, get_google_sheet, get_participants, valid_email


def _read_registration_status_with_retry():
    """Read the authoritative event status from Google Sheets.

    A transient Google API/network failure should not immediately turn a healthy
    registration page into an unavailable page. We retry a small number of times
    while never inventing an OPEN/CLOSED status when the sheet cannot be read.
    """
    last_error = None
    for attempt in range(3):
        try:
            worksheet = get_google_sheet()
            return get_event_status(worksheet), False
        except Exception as exc:
            last_error = exc
            app.logger.warning(
                "Google Sheets event-status read failed (attempt %s/3): %s",
                attempt + 1,
                exc,
            )
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
    app.logger.exception("Unable to read authoritative registration status") if last_error else None
    return None, True


# Replace the GET behavior of the application route with an explicit
# Sheet-backed render. POST remains handled by the original registration logic.
_original_index = app.view_functions.get("index")
if _original_index is None:
    raise RuntimeError("The Flask application does not expose the index endpoint.")


def participant_index():
    if request.method == "GET":
        registration_status, status_error = _read_registration_status_with_retry()
        return render_template(
            "index.html",
            registration_status=registration_status,
            registration_status_error=status_error,
        )
    return _original_index()


app.view_functions["index"] = participant_index


# Register participant-facing routes directly on the production Flask app.
if "participant_lookup" not in app.view_functions:

    @app.get("/lookup", endpoint="participant_lookup")
    def participant_lookup():
        result = None
        error = None
        status, status_error = _read_registration_status_with_retry()
        if status_error:
            return render_template(
                "lookup.html",
                result=None,
                error="The registration service is temporarily unavailable. Please try again.",
            )

        email = request.args.get("email", "").strip().lower()
        if email:
            if len(email) > 254 or not valid_email(email):
                error = "Please enter the email address you used when registering."
            else:
                try:
                    worksheet = get_google_sheet()
                    participant = next(
                        (
                            participant
                            for participant in get_participants(worksheet)
                            if participant["email"].lower() == email
                        ),
                        None,
                    )
                    if participant:
                        result = participant
                    else:
                        error = "We could not find a registration for that email address."
                except Exception:
                    app.logger.exception("Participant team lookup failed")
                    error = "We could not look up your team right now. Please try again."

        return render_template("lookup.html", result=result, error=error)


__all__ = ["app"]
