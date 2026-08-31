# Games Weekend Check-In

Production Flask application for public event check-in, balanced team assignment, Google Sheets persistence, Gmail SMTP confirmation email, and live team counts.

## Gmail SMTP configuration

Resend has been completely removed. Confirmation emails are sent through Gmail SMTP using Python's standard `smtplib` and `email` libraries.

Set these environment variables:

- `GMAIL_SMTP_USERNAME` — Gmail/Google Workspace account used to send mail.
- `GMAIL_SMTP_APP_PASSWORD` — Google App Password for that account. Do not use the normal account password.
- `GMAIL_FROM_EMAIL` — optional sender address; defaults to `GMAIL_SMTP_USERNAME`.
- `GMAIL_SMTP_HOST` — optional; defaults to `smtp.gmail.com`.
- `GMAIL_SMTP_PORT` — optional; defaults to `587`.

For Gmail, enable 2-Step Verification and create a Google App Password. For Google Workspace, confirm that the organization's policy permits the selected SMTP authentication method.

## Google Sheets setup

1. Create a Google Sheet.
2. Set the first worksheet header row to exactly: `Timestamp | Full Name | Email | Team`.
3. Create a Google Cloud service account and enable the Google Sheets API.
4. Create a JSON service-account key and keep it secret.
5. Share the spreadsheet with the service account `client_email` as Editor.
6. Set `GOOGLE_SHEETS_ID` to the spreadsheet ID.
7. Set `GOOGLE_SERVICE_ACCOUNT_JSON` to the complete JSON object as one environment-variable value.

The application authenticates with `Credentials.from_service_account_info(...)`; no credential file is required in production.

## Environment variables

Required:

```text
GOOGLE_SHEETS_ID
GOOGLE_SERVICE_ACCOUNT_JSON
GMAIL_SMTP_USERNAME
GMAIL_SMTP_APP_PASSWORD
```

Optional:

```text
GMAIL_FROM_EMAIL
GMAIL_SMTP_HOST=smtp.gmail.com
GMAIL_SMTP_PORT=587
LOG_LEVEL=INFO
```

Never commit credentials or service-account JSON to GitHub.

## Run locally

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS/Linux
# source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:10000/`.

## Render deployment

Build command:

```text
pip install -r requirements.txt
```

Start command:

```text
gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120
```

Configure the four required environment variables above plus any optional Gmail variables in Render. Use one Gunicorn worker so the in-process assignment lock serializes the read/count/append operation. Do not scale to multiple instances without replacing that lock with distributed coordination.

## QR code

After deployment, point a QR code at the public form URL ending in `/`. For example:

```bash
pip install qrcode[pil]
python -c "import qrcode; qrcode.make('https://your-service.onrender.com/').save('games-weekend-checkin.png')"
```

## Operational verification

1. Check `/health` returns HTTP 200.
2. Submit a test registration at `/`.
3. Verify the Google Sheet row.
4. Verify the assigned team is one of the four teams.
5. Verify the Gmail confirmation email arrives.
6. Check `/teams`.
7. Test multiple registrations to verify lowest-count assignment and randomized ties.
8. Remove test records before the event if required.

## Project structure

```text
app.py
requirements.txt
README.md
render.yaml
templates/
  index.html
  confirmation.html
  email_error.html
  error.html
  teams.html
```
