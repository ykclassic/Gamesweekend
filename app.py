import html
import json
import logging
import os
import random
import secrets
import smtplib
import threading
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parseaddr
from functools import wraps

import gspread
from flask import Flask, render_template, request, session, redirect, url_for
from google.oauth2.service_account import Credentials

app = Flask(__name__)
app.config.update(
    MAX_CONTENT_LENGTH=16 * 1024,
    SECRET_KEY=os.environ.get("FLASK_SECRET_KEY", "").strip(),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "true").lower() == "true",
)
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)
TEAMS = ("Honour", "Love", "Breakthrough", "Dominion")
HEADERS = ("Timestamp", "Full Name", "Email", "Team")
ASSIGNMENT_LOCK = threading.Lock()


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable {name} is missing.")
    return value


def get_google_sheet():
    raw_json = _required_env("GOOGLE_SERVICE_ACCOUNT_JSON")
    sheet_id = _required_env("GOOGLE_SHEETS_ID")
    try:
        info = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON.") from exc
    if not isinstance(info, dict):
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON must contain a JSON object.")
    credentials = Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    worksheet = gspread.authorize(credentials).open_by_key(sheet_id).sheet1
    headers = worksheet.row_values(1)
    if not headers:
        worksheet.update("A1:D1", [list(HEADERS)])
    elif tuple(headers[:4]) != HEADERS:
        raise RuntimeError("The first row of the Google Sheet must be exactly: Timestamp, Full Name, Email, Team")
    return worksheet


def get_team_counts(worksheet):
    counts = {team: 0 for team in TEAMS}
    for record in worksheet.get_all_records(expected_headers=list(HEADERS)):
        team = str(record.get("Team", "")).strip()
        if team in counts:
            counts[team] += 1
    return counts


def choose_team(counts):
    minimum = min(counts.values())
    return random.choice([team for team in TEAMS if counts[team] == minimum])


def valid_email(value: str) -> bool:
    _, address = parseaddr(value)
    return bool(address and "@" in address and not any(ch.isspace() for ch in address))


def send_confirmation_email(full_name: str, email_address: str, team: str) -> None:
    """Send the confirmation using Gmail SMTP and a Google App Password."""
    host = os.environ.get("GMAIL_SMTP_HOST", "smtp.gmail.com").strip()
    try:
        port = int(os.environ.get("GMAIL_SMTP_PORT", "587"))
    except ValueError as exc:
        raise RuntimeError("GMAIL_SMTP_PORT must be an integer.") from exc
    username = _required_env("GMAIL_SMTP_USERNAME")
    password = _required_env("GMAIL_SMTP_APP_PASSWORD").replace(" ", "")
    from_address = os.environ.get("GMAIL_FROM_EMAIL", username).strip()
    message = EmailMessage()
    message["From"] = from_address
    message["To"] = email_address
    message["Subject"] = "Your Games Weekend Team"
    message.set_content(f"You're checked in, {full_name}!\n\nYour Games Weekend team is: {team}\n\nWe look forward to seeing you.")
    message.add_alternative(
        f'<div style="font-family:Arial,sans-serif;line-height:1.6;max-width:560px;margin:auto">'
        f'<h2>You\'re checked in, {html.escape(full_name)}!</h2><p>Your Games Weekend team is:</p>'
        f'<p style="font-size:28px;font-weight:700">{html.escape(team)}</p></div>', subtype="html")
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(username, password)
        smtp.send_message(message)


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_csrf_token():
    token = session.get("admin_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["admin_csrf_token"] = token
    return token


def validate_admin_csrf():
    token = request.form.get("csrf_token", "")
    expected = session.get("admin_csrf_token", "")
    return bool(token and expected and secrets.compare_digest(token, expected))


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
        with ASSIGNMENT_LOCK:
            worksheet = get_google_sheet()
            counts = get_team_counts(worksheet)
            records = worksheet.get_all_records(expected_headers=list(HEADERS))
            if any(str(row.get("Email", "")).strip().lower() == email_address for row in records):
                return render_error("This email address has already been checked in. Please contact the organizers if you need help.", 409)
            team = choose_team(counts)
            timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            worksheet.append_row([timestamp, full_name, email_address, team], value_input_option="USER_ENTERED", insert_data_option="INSERT_ROWS")
        try:
            send_confirmation_email(full_name, email_address, team)
        except Exception:
            logger.exception("Check-in saved but Gmail confirmation failed for %s", email_address)
            return render_template("email_error.html", full_name=full_name, team=team), 503
        return render_template("confirmation.html", full_name=full_name, team=team)
    except gspread.exceptions.APIError:
        logger.exception("Google Sheets API failure during check-in")
        return render_error("We could not complete your check-in because the registration service is temporarily unavailable. Please try again.", 503)
    except Exception:
        logger.exception("Unexpected check-in failure")
        return render_error("We could not complete your check-in right now. Please try again or contact the organizers.", 503)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "GET":
        return render_template("admin_login.html")
    try:
        configured_password = _required_env("ADMIN_PASSWORD")
        if request.form.get("password", "") != configured_password:
            return render_template("admin_login.html", error="Invalid admin password."), 401
        session.clear()
        session["is_admin"] = True
        session["admin_csrf_token"] = secrets.token_urlsafe(32)
        next_url = request.form.get("next", "")
        if not next_url.startswith("/") or next_url.startswith("//"):
            next_url = url_for("teams")
        return redirect(next_url)
    except Exception:
        logger.exception("Admin login configuration failure")
        return render_error("Admin access is not configured correctly.", 503)


@app.post("/admin/logout")
@admin_required
def admin_logout():
    if not validate_admin_csrf():
        return render_error("Invalid admin security token. Please sign in again.", 403)
    session.clear()
    return redirect(url_for("index"))


@app.get("/teams")
@admin_required
def teams():
    try:
        worksheet = get_google_sheet()
        counts = get_team_counts(worksheet)
        return render_template("teams.html", teams=counts, total=sum(counts.values()), csrf_token=admin_csrf_token())
    except Exception:
        logger.exception("Unable to load team counts")
        return render_error("Live team counts are temporarily unavailable. Please refresh shortly.", 503)


@app.post("/admin/reset-teams")
@admin_required
def reset_teams():
    if not validate_admin_csrf():
        return render_error("Invalid admin security token. Please sign in again.", 403)
    try:
        with ASSIGNMENT_LOCK:
            worksheet = get_google_sheet()
            worksheet.batch_clear(["A2:D"])
        logger.warning("Admin reset all team registrations to zero")
        return redirect(url_for("teams", reset="1"))
    except Exception:
        logger.exception("Unable to reset team counts")
        return render_error("The team reset could not be completed. No reset confirmation was issued.", 503)


@app.get("/health")
def health():
    return {"status": "ok"}, 200


@app.errorhandler(413)
def request_too_large(_error):
    return render_error("The submitted form is too large.", 413)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")), debug=False)
