# LCM Booking Backend (Flask)

Production-ready starter for LCM Oven Cleaning booking system.

## Features
- 📅 Create bookings with multiple services
- ⏰ Enforces working hours (Mon–Fri, 08:15–14:00) and start date (>= 2025-08-18)
- 💷 Auto-calc total duration & price
- 📧 Email confirmations via SMTP (Hotmail/Office365 compatible)
- 📍 Postcode distance util (pgeocode) for future routing/grouping
- 🗂 File uploads (photos/videos) to `/app/uploads`
- 🔐 Simple admin access via `X-ADMIN-KEY` header
- 🟢 Ready for Render (Procfile, `render.yaml`)

## Endpoints

- `GET /health` — service health

- `GET /services` — list services

- `POST /bookings` — create booking

  ```json
  {
    "customer_name": "Jane Smith",
    "email": "jane@example.com",
    "phone": "0756...",
    "address": "1 High St, Town",
    "postcode": "E14 5AB",
    "date": "2025-08-19",
    "start_time": "09:00",
    "service_ids": [1, 5],
    "notes": "Please call on arrival"
  }
  ```
- `GET /bookings?date=YYYY-MM-DD` — list (admin, pass header `X-ADMIN-KEY`)
- `POST /upload-media` — multipart file upload (admin)
- `GET /uploads/<filename>` — fetch uploaded file

## Setup

1. **Install**
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

2. **Configure** `.env` variables (DB, SMTP, ADMIN_KEY).

3. **Run**
```bash
export FLASK_APP=app/app.py
python -m app.app
# or
gunicorn app.app:app
```

## Database
- Uses `DATABASE_URL` (Postgres on Render or SQLite fallback `sqlite:///lcm.db`).

## Render Deploy
- Connect repo → Python web service.
- Build: `pip install -r requirements.txt`
- Start: `gunicorn app.app:app`
- Set env vars as in `.env.example`.

## Google Calendar (optional)
- Use a service account or OAuth flow.
- Add your `GOOGLE_CALENDAR_ID` and mount credentials; create event after booking.

## Notes
- Distance grouping utilities are included in `utils.py` for route planning.
- Extend with auth/JWT and an admin UI later.
