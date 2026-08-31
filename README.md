# Games Weekend Check-In

Production Flask application for public event check-in, balanced team assignment, Google Sheets persistence, confirmation email, and live team counts.

## How the assignment works

The four teams are **Honour**, **Love**, **Breakthrough**, and **Dominion**. On every successful submission the application reads the current Google Sheet rows, counts members in each team, finds the minimum count, and randomly chooses among all teams tied at that minimum. The new row is then appended with an ISO-8601 UTC timestamp.

The check-in write is serialized with an application lock. The recommended Render command uses one Gunicorn worker so concurrent requests cannot race the balancing decision inside the instance.

## 1. Create the Google Sheet

1. Create a new Google Sheet.
2. Give the first worksheet a header row exactly as follows:

   `Timestamp | Full Name | Email | Team`

3. Create a Google Cloud service account and download its JSON key.
4. Share the Google Sheet with the service account's `client_email` address as an **Editor**.
5. Copy the spreadsheet ID from the URL:

   `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit`

## 2. Create the Google Cloud service account

1. Open Google Cloud Console and create/select a project.
2. Enable the **Google Sheets API** for the project.
3. Go to **IAM & Admin → Service Accounts** and create a service account.
4. Open the service account → **Keys → Add key → Create new key → JSON**.
5. Store the downloaded JSON securely. Do not commit it to Git.
6. The full JSON document is supplied to the application through `GOOGLE_SERVICE_ACCOUNT_JSON`.

The application uses `google.oauth2.service_account.Credentials.from_service_account_info(...)`, so a JSON file on disk is not required in production.

## 3. Set up Resend

1. Create a Resend account.
2. Create an API key.
3. For production sending, add and verify a domain in Resend and use a sender address on that verified domain.
4. Set `RESEND_API_KEY` to the API key.
5. Set `RESEND_FROM_EMAIL` to the verified sender address, for example `Games Weekend <hello@example.com>`.

`RESEND_FROM_EMAIL` is optional in local testing and defaults to `onboarding@resend.dev`. A verified production sender is recommended.

## 4. Environment variables

Required:

- `RESEND_API_KEY`
- `GOOGLE_SHEETS_ID`
- `GOOGLE_SERVICE_ACCOUNT_JSON` — the complete service-account JSON object as one environment-variable value

Recommended for production:

- `RESEND_FROM_EMAIL` — verified Resend sender, e.g. `Games Weekend <hello@example.com>`
- `LOG_LEVEL` — normally `INFO`

Do not put API keys or service-account JSON in GitHub, `.env` files committed to Git, templates, or client-side JavaScript.

## 5. Run locally

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

The health endpoint is `GET /health` and returns `{"status":"ok"}` when the Flask process is running.

## 6. Deploy on Render

Create a **Web Service** connected to this GitHub repository.

**Build command**

```text
pip install -r requirements.txt
```

**Start command**

```text
gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120
```

Use one worker because the application lock protects the read/count/append sequence within the process. If you later scale to multiple instances, replace this with a distributed coordination strategy before allowing concurrent check-ins across instances.

Add these Render environment variables:

```text
RESEND_API_KEY=<your Resend API key>
RESEND_FROM_EMAIL=Games Weekend <your-verified-address@example.com>
GOOGLE_SHEETS_ID=<your spreadsheet ID>
GOOGLE_SERVICE_ACCOUNT_JSON=<complete service account JSON>
```

Do not add the Google JSON key to the repository.

## 7. Generate a QR code for the form

After Render deploys, copy the public service URL, for example:

`https://your-service.onrender.com/`

Generate a QR code pointing to that URL with any trusted QR generator, or locally with Python:

```bash
pip install qrcode[pil]
python -c "import qrcode; qrcode.make('https://your-service.onrender.com/').save('games-weekend-checkin.png')"
```

Print/display `games-weekend-checkin.png` at the event. Test the QR code with a phone before the event starts.

## 8. Operational checks

Before opening registration:

1. Visit `/health` and confirm HTTP 200.
2. Visit `/` and submit a real test participant.
3. Confirm the row appears in Google Sheets.
4. Confirm the team is one of the four allowed teams.
5. Confirm the confirmation email arrives.
6. Open `/teams` and verify counts.
7. Submit enough test registrations to verify that the lowest-count team is selected and that ties are randomized.
8. Remove test rows before the event if desired.

## Project structure

```text
app.py
requirements.txt
README.md
templates/
  index.html
  confirmation.html
  email_error.html
  error.html
  teams.html
```
