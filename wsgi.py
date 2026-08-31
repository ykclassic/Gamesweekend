"""Production WSGI entry point.

The production process must expose the same Flask application regardless of
whether Render invokes ``wsgi:app`` or another compatible WSGI target.  The
participant lookup route is registered here explicitly so it cannot disappear
because of import-order or circular-import behavior.
"""

from flask import render_template, request

from app import app, get_event_status, get_google_sheet, get_participants, valid_email


# Register participant-facing routes directly on the production Flask app.
# Do not rely on participant_routes.py being imported for endpoint discovery.
if "participant_lookup" not in app.view_functions:

    @app.get("/lookup", endpoint="participant_lookup")
    def participant_lookup():
        result = None
        error = None
        try:
            worksheet = get_google_sheet()
            get_event_status(worksheet)
        except Exception:
            app.logger.exception("Unable to read registration status for team lookup")
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


# Register the Sheet-backed participant status context processor here as well.
# It is deliberately defined on the actual app object before Gunicorn receives it.
if not any(
    getattr(processor, "__name__", "") == "participant_registration_status"
    for processor in app.template_context_processors.get(None, [])
):

    @app.context_processor
    def participant_registration_status():
        try:
            worksheet = get_google_sheet()
            return {
                "registration_status": get_event_status(worksheet),
                "registration_status_error": False,
            }
        except Exception:
            app.logger.exception("Unable to read registration status for participant UI")
            return {
                "registration_status": None,
                "registration_status_error": True,
            }


__all__ = ["app"]
