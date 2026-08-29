import os
import json
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from flask import Flask, request, render_template_string, redirect, url_for, flash
import gspread

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super-secret-fallback-key")

# --- Configuration & Environment Variables ---
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")

# --- Google Sheets Helper ---
def get_sheet():
    try:
        credentials_dict = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
        gc = gspread.service_account_from_dict(credentials_dict)
        sheet = gc.open_by_key(GOOGLE_SHEETS_ID).sheet1
        return sheet
    except Exception as e:
        print(f"Error connecting to Google Sheets: {e}")
        return None

# --- SMTP Email Helper ---
def send_confirmation_email(to_email, full_name, assigned_team):
    if not MAIL_USERNAME or not MAIL_PASSWORD:
        print("SMTP credentials not configured. Skipping email.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Your Games Weekend Team Assignment!"
    msg["From"] = MAIL_USERNAME
    msg["To"] = to_email

    html_body = f"""
    <html>
      <body style="font-family: sans-serif; color: #333;">
        <h2>Welcome, {full_name}!</h2>
        <p>We are excited to have you join us. You have been officially assigned to:</p>
        <h3 style="color: #2563eb; background: #eff6ff; padding: 15px; border-radius: 5px; display: inline-block;">
            Team {assigned_team}
        </h3>
        <p>See you at the games weekend!</p>
      </body>
    </html>
    """
    
    msg.attach(MIMEText(html_body, "html"))

    try:
        server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT)
        server.starttls()
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        server.sendmail(MAIL_USERNAME, to_email, msg.as_string())
        server.quit()
    except Exception as e:
        print(f"Failed to send email to {to_email} via SMTP: {e}")

# --- HTML Templates ---
# We use Python string replacement placeholders ({EXTRA_HEAD} and {CONTENT}) 
# instead of Jinja {% block %} tags to avoid Jinja's compilation collisions.
BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Games Weekend Check-In</title>
    <script src="https://cdn.tailwindcss.com"></script>
    {EXTRA_HEAD}
</head>
<body class="bg-gray-50 text-gray-800 font-sans antialiased flex flex-col min-h-screen">
    <main class="flex-grow flex items-center justify-center p-4">
        <div class="w-full max-w-md bg-white rounded-xl shadow-lg p-6 sm:p-8">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="mb-4 p-4 rounded {% if category == 'error' %}bg-red-100 text-red-700{% else %}bg-green-100 text-green-700{% endif %}">
                            {{ message }}
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
            {CONTENT}
        </div>
    </main>
</body>
</html>
"""

INDEX_TEMPLATE = """
<h1 class="text-2xl font-bold text-center mb-2">Welcome!</h1>
<p class="text-gray-500 text-center mb-6">Check in to discover your team for the weekend.</p>
<form method="POST" action="/" class="space-y-4">
    <div>
        <label for="full_name" class="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
        <input type="text" id="full_name" name="full_name" required class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition">
    </div>
    <div>
        <label for="email" class="block text-sm font-medium text-gray-700 mb-1">Email Address</label>
        <input type="email" id="email" name="email" required class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition">
    </div>
    <button type="submit" class="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded-lg transition duration-200">
        Check In & Find My Team
    </button>
</form>
<div class="mt-4 text-center">
    <a href="/teams" class="text-sm text-blue-600 hover:underline">View Live Team Counts</a>
</div>
"""

CONFIRMATION_TEMPLATE = """
<div class="text-center">
    <div class="inline-flex items-center justify-center w-16 h-16 rounded-full bg-green-100 mb-4">
        <svg class="w-8 h-8 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
        </svg>
    </div>
    <h1 class="text-2xl font-bold mb-2">You're in, {{ name }}!</h1>
    <p class="text-gray-600 mb-4">You have been assigned to:</p>
    <div class="bg-blue-50 border border-blue-200 text-blue-800 text-3xl font-black py-4 px-6 rounded-lg mb-6 shadow-inner">
        Team {{ team }}
    </div>
    <p class="text-sm text-gray-500 mb-6">A confirmation email has been sent to {{ email }}.</p>
    <a href="/" class="text-blue-600 font-medium hover:underline">← Back to check-in</a>
</div>
"""

TEAMS_TEMPLATE = """
<h1 class="text-2xl font-bold text-center mb-6">Live Team Counts</h1>
<div class="grid grid-cols-2 gap-4 mb-6">
    {% for team, count in team_counts.items() %}
    <div class="bg-gray-50 border border-gray-200 rounded-lg p-4 text-center shadow-sm">
        <h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wide">{{ team }}</h2>
        <p class="text-3xl font-black text-gray-800 mt-1">{{ count }}</p>
    </div>
    {% endfor %}
</div>
<div class="bg-blue-600 text-white rounded-lg p-4 text-center shadow">
    <h2 class="text-sm font-medium uppercase tracking-wide opacity-80">Total Participants</h2>
    <p class="text-4xl font-black mt-1">{{ total }}</p>
</div>
<p class="text-xs text-gray-400 text-center mt-4">Auto-refreshing every 30 seconds</p>
<div class="mt-4 text-center">
    <a href="/" class="text-sm text-blue-600 hover:underline">← Back to form</a>
</div>
"""

# --- Routes ---
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()

        if not full_name or not email:
            flash("Name and Email are required.", "error")
            return redirect(url_for("index"))

        sheet = get_sheet()
        if not sheet:
            flash("System error: Unable to connect to the database. Please try again.", "error")
            return redirect(url_for("index"))

        try:
            records = sheet.get_all_records()
            teams = ["Honour", "Love", "Breakthrough", "Dominion"]
            team_counts = {t: 0 for t in teams}
            
            for row in records:
                team_val = row.get("Team")
                if team_val in team_counts:
                    team_counts[team_val] += 1

            min_count = min(team_counts.values())
            candidates = [t for t, count in team_counts.items() if count == min_count]
            assigned_team = random.choice(candidates)

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            sheet.append_row([timestamp, full_name, email, assigned_team])

            send_confirmation_email(email, full_name, assigned_team)

            html_string = BASE_TEMPLATE.replace("{EXTRA_HEAD}", "").replace("{CONTENT}", CONFIRMATION_TEMPLATE)
            return render_template_string(
                html_string,
                name=full_name, 
                team=assigned_team, 
                email=email
            )

        except Exception as e:
            print(f"Error processing submission: {e}")
            flash("An unexpected error occurred. Please try again.", "error")
            return redirect(url_for("index"))

    html_string = BASE_TEMPLATE.replace("{EXTRA_HEAD}", "").replace("{CONTENT}", INDEX_TEMPLATE)
    return render_template_string(html_string)

@app.route("/teams", methods=["GET"])
def teams_view():
    sheet = get_sheet()
    teams = ["Honour", "Love", "Breakthrough", "Dominion"]
    team_counts = {t: 0 for t in teams}
    
    if sheet:
        try:
            records = sheet.get_all_records()
            for row in records:
                team_val = row.get("Team")
                if team_val in team_counts:
                    team_counts[team_val] += 1
        except Exception as e:
            print(f"Error fetching teams: {e}")
            flash("Unable to load live data.", "error")

    total = sum(team_counts.values())
    extra_head = '<meta http-equiv="refresh" content="30">'
    html_string = BASE_TEMPLATE.replace("{EXTRA_HEAD}", extra_head).replace("{CONTENT}", TEAMS_TEMPLATE)
    
    return render_template_string(
        html_string,
        team_counts=team_counts,
        total=total
    )

if __name__ == "__main__":
    app.run(debug=True)
