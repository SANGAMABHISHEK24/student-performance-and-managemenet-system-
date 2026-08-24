# Student Performance & Management System

Streamlit student management dashboard backed by Turso (libSQL).

## Features

- Admin login
- Student directory
- Add, edit and delete students
- Subject-wise scores and charts
- Attendance history and trends
- CSV bulk import
- CSV export
- Dashboard metrics and charts
- Persistent cloud database with Turso

## 1. Install locally

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Then:

```bash
pip install -r requirements.txt
```

## 2. Configure Turso

Create:

`.streamlit/secrets.toml`

```toml
TURSO_DATABASE_URL = "libsql://YOUR-DATABASE-YOURORG.turso.io"
TURSO_AUTH_TOKEN = "YOUR_TURSO_TOKEN"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "CHANGE_THIS_PASSWORD"
```

Never commit `secrets.toml`.

## 3. Run

```bash
streamlit run app.py
```

On first startup, the application creates:

- `students`
- `subjects`
- `attendance_log`

inside your Turso database.

## 4. Deploy

1. Push this folder to GitHub.
2. Open Streamlit Community Cloud.
3. Create a new app from the GitHub repository.
4. Select `app.py` as the main file.
5. Add the same values under the app's Secrets settings.
6. Deploy.

The database remains in Turso; Streamlit is the application host.

## Important security notes

- Never commit your Turso auth token.
- Never commit `.streamlit/secrets.toml`.
- Change the admin password before making the application public.
- If a Turso token is exposed, revoke/rotate it immediately.
