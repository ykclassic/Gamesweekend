from datetime import datetime, timezone

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
    if request.args.get("email"):
        email = request.args.get("email", "").strip().lower()
        if len(email) > 254 or not valid_email(email):
            error = "Please enter the email address you used when registering."
        else:
            try:
                worksheet = get_google_sheet()
                if get_event_status(worksheet) not in {"OPEN", "CLOSED"}:
                    error = "Registration is temporarily unavailable. Please try again."
                else:
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
