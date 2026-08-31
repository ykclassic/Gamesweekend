import html
import json
import logging
import os
import random
import threading
from datetime import datetime, timezone
from email.utils import parseaddr

import gspread
import resend
from flask import Flask, render_template, request
from google.oauth2.service_account import Credentials

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024  # Prevent oversized form submissions.

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

TEAMS = ("Honour", "Love", "Breakthrough", "Dominion")
HEADERS = ("Timestamp", "Full Name", "Email", "Team")
# The lock is intentionally held across the read/count/append sequence so that
# the balancing decision is serialized when Gunicorn runs one process.
ASSIGNMENT_LOCK = threading.Lock()


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable {name} is missing.")
    return value


def get_google_sheet():
    """Authorize with the service-account JSON stored in the environment."""
    raw_json = _required_env("GOOGLE_SERVICE_ACCOUNT_JSON")
    sheet_id = _required_env("GOOGLE_SHEETS_ID")

    try:
        service_account_info = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc

    if not isinstance(service_account_info, dict):
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON must contain a JSON object.")

    credentials = Credentials.from_service_account_info(
        service_account_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    client = gspread.authorize(credentials)
    workbook = client.open_by_key(sheet_id)
    worksheet = workbook.sheet1

    # Ensure the required header row exists. Existing data is preserved.
    existing_headers = worksheet.row_values(1)
    if not existing_headers:
        worksheet.update("A1:D1", [list(HEADERS)])
    elif tuple(existing_headers[:4]) != HEADERS:
        raise RuntimeError(
            "The first row of the Google Sheet must be exactly: "
            "Timestamp, Full Name, Email, Team"
        )

    return worksheet


def get_team_counts(worksheet):
    """Read current membership counts from the Google Sheet."""
    counts = {team: 0 for team in TEAMS}
    records = worksheet.get_all_records(expected_headers=list(HEADERS))

    for record in records:
        team = str(record.get("Team", "")).strip()
        if team in counts:
            counts[team] += 1

    return counts


def choose_team(counts):
    """Choose randomly among the teams tied for the lowest count."""
    minimum = min(counts.values())
    candidates = [team for team in TEAMS if counts[team] == minimum]
    return random.choice(candidates)


def valid_email(value: str) -> bool:
    """Perform a conservative syntactic email validation."""
    _, address = parseaddr(value)
    return bool(address and "@" in address and not any(ch.isspace() for ch in address))


def send_confirmation_email(full_name: str, email_address: str, team: str) -> None:
    """Send the participant's confirmation using the Resend Python SDK."""
    api_key = _required_env("RESEND_API_KEY")
    from_address = os.environ.get("RESEND_FROM_EMAIL", "onboarding@resend.dev").strip()
    resend.api_key = api_key

    safe_name = html.escape(full_name)
    safe_team = html.escape(team)
    safe_email = html.escape(email_address)

    params = {
        "from": from_address,
        "to": [email_address],
        "subject": "Your Games Weekend Team",
        "html": f"""
        <div style=\"font-family:Arial,sans-serif;line-height:1.6;max-width:560px;margin:auto\">
          <h2>You're checked in, {safe_name}!</h2>
          <p>Your Games Weekend team is:</p>
          <p style=\"font-size:28px;font-weight:700\">{safe_team}</p>
          <p>We look forward to seeing you. This confirmation was sent to {safe_email}.</p>
        </div>
        """,
        "text": (
            f"You're checked in, {full_name}!\n\n"
            f"Your Games Weekend team is: {team}\n\n"
            "We look forward to seeing you."
        ),
    }

    # Resend's current Python SDK supports this synchronous API.
    result = resend.Emails.send(params)
    if not result:
        raise RuntimeError("Resend returned an empty response.")


def render_error(message: str, status_code: int = 500):
    return render_template("error.html", message=message), status_code


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template("index.html")

    full_name = " ".join(request.form.get("full_name", "").split())
    email_address = request.form.get("email_address", "").strip().lower()

    if not full_name or not email_address:
        return render_error("Full name and email address are required.", 400)
    if len(full_name) > 150:
        return render_error("Full name is too long.", 400)
    if len(email_address) > 254 or not valid_email(email_address):
        return render_error("Please enter a valid email address.", 400)

    try:
        # A single Gunicorn worker is recommended on Render so this lock also
        # serializes simultaneous check-ins and prevents balancing races.
        with ASSIGNMENT_LOCK:
            worksheet = get_google_sheet()
            counts = get_team_counts(worksheet)

            # Prevent accidental duplicate registrations for the same email.
            existing_records = worksheet.get_all_records(expected_headers=list(HEADERS))
            if any(
                str(row.get("Email", "")).strip().lower() == email_address
                for row in existing_records
            ):
                return render_error(
                    "This email address has already been checked in. Please contact the organizers if you need help.",
                    409,
                )

            team = choose_team(counts)
            timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            worksheet.append_row(
                [timestamp, full_name, email_address, team],
                value_input_option="USER_ENTERED",
                insert_data_option="INSERT_ROWS",
            )

        # Persist first. If email delivery fails, the assignment remains safe
        # and the participant receives an explicit recovery message.
        try:
            send_confirmation_email(full_name, email_address, team)
        except Exception:
            logger.exception("Check-in saved but confirmation email failed for %s", email_address)
            return render_template(
                "email_error.html", full_name=full_name, team=team
            ), 503

        return render_template("confirmation.html", full_name=full_name, team=team)

    except gspread.exceptions.APIError:
        logger.exception("Google Sheets API failure during check-in")
        return render_error(
            "We could not complete your check-in because the registration service is temporarily unavailable. Please try again.",
            503,
        )
    except Exception:
        logger.exception("Unexpected check-in failure")
        return render_error(
            "We could not complete your check-in right now. Please try again or contact the organizers.",
            503,
        )


@app.route("/teams", methods=["GET"])
def teams():
    try:
        worksheet = get_google_sheet()
        counts = get_team_counts(worksheet)
        return render_template(
            "teams.html",
            teams=counts,
            total=sum(counts.values()),
        )
    except Exception:
        logger.exception("Unable to load team counts")
        return render_error(
            "Live team counts are temporarily unavailable. Please refresh shortly.",
            503,
        )


@app.get("/health")
def health():
    """Lightweight process health endpoint for Render."""
    return {"status": "ok"}, 200


@app.errorhandler(413)
def request_too_large(_error):
    return render_error("The submitted form is too large.", 413)


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "10000")),
        debug=False,
    )
