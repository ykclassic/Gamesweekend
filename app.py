import os
import sys
import json
import traceback
from flask import Flask, render_template, request, flash

import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "fallback_dev_key_12345")

def get_google_sheet():
    creds_json_str = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_json_str:
        raise ValueError("Environment variable GOOGLE_SERVICE_ACCOUNT_JSON is missing.")
    
    try:
        creds_dict = json.loads(creds_json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse GOOGLE_SERVICE_ACCOUNT_JSON. Invalid JSON format: {e}")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(credentials)
    
    sheet_id = os.environ.get("GOOGLE_SHEETS_ID")
    if not sheet_id:
        raise ValueError("Environment variable GOOGLE_SHEETS_ID is missing.")
        
    workbook = gc.open_by_key(sheet_id)
    return workbook.sheet1

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            full_name = request.form.get("full_name")
            email_address = request.form.get("email_address")
            
            if not full_name or not email_address:
                flash("System error: Missing name or email. Please try again.")
                return render_template("index.html")

            sheet = get_google_sheet()
            
            # INSERT YOUR TEAM ASSIGNMENT LOGIC HERE
            
            flash(f"Success! {full_name}, you are checked in.")
            return render_template("index.html")
            
        except Exception as e:
            print("=== CRITICAL DATABASE ERROR TRACEBACK ===", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            print("=========================================", file=sys.stderr)
            return f"A runtime exception occurred: {str(e)} <br><br> Please check Render logs for the full traceback.", 500

    return render_template("index.html")

@app.route("/teams", methods=["GET"])
def teams():
    # Renders teams.html if it exists in the templates folder.
    # Otherwise, falls back to a plain text response to prevent a 500 crash.
    try:
        return render_template("teams.html")
    except Exception:
        return "Live Team Counts dashboard is under construction.", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
