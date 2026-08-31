from flask import render_template, request

from app import (
    app,
    get_event_status,
    get_google_sheet,
    get_participants,
    valid_email,
)


@app.context_processor
def participant_registration_status():
    """Provide the landing page with the authoritative Sheet-backed status."""
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


@app.get("/lookup")
def participant_lookup():
    result = None
    error = None
    try:
        worksheet = get_google_sheet()
        get_event_status(worksheet)
    except Exception:
        app.logger.exception("Unable to read registration status for team lookup")
        error = "The registration service is temporarily unavailable. Please try again."
        return render_template("lookup.html", result=result, error=error)

    if request.args.get("email"):
        email = request.args.get("email", "").strip().lower()
        if len(email) > 254 or not valid_email(email):
            error = "Please enter the email address you used when registering."
        else:
            try:
                participant = next(
                    (p for p in get_participants(worksheet) if p["email"].lower() == email),
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


@app.get("/participant")
def participant_landing():
    # Kept as a convenience route; / is also backed by the context processor above.
    return render_template("index.html")
