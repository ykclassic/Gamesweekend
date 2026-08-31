from flask import render_template, request

from app import (
    app,
    get_event_status,
    get_google_sheet,
    get_participants,
    valid_email,
)


@app.get("/lookup")
def participant_lookup():
    result = None
    error = None
    try:
        worksheet = get_google_sheet()
        event_status = get_event_status(worksheet)
    except Exception:
        app.logger.exception("Unable to read registration status for participant page")
        return render_template(
            "index.html",
            registration_status=None,
            registration_status_error=True,
        )

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


# Register the participant landing page here so its displayed status is always
# obtained from the authoritative Google Sheet event-status cell.
@app.get("/participant")
def participant_landing():
    try:
        worksheet = get_google_sheet()
        registration_status = get_event_status(worksheet)
        return render_template(
            "index.html",
            registration_status=registration_status,
            registration_status_error=False,
        )
    except Exception:
        app.logger.exception("Unable to read registration status for participant landing page")
        return render_template(
            "index.html",
            registration_status=None,
            registration_status_error=True,
        )
