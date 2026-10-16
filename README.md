# NAWA Global

FastAPI website for NAWA Global General Trading, with a light public website,
searchable product catalogue, administrator product management and visitor analytics.

## Local development

Use Python 3.11 or 3.12. From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock -r dev_requirements.txt
python -m uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. The default local administrator route is `/admin12`.
Development defaults are `admin` / `admin123`; production rejects that password.
The local database and uploads are generated at runtime and excluded from Git.
Run `python -m pytest -q` for isolated tests. Tests never use the development database.

## Production

See [DEPLOYMENT.md](DEPLOYMENT.md). Configuration names are in `.env.example`.
Environment files are not loaded automatically. A process manager must supply them.

The contact form currently has no delivery integration. It explicitly directs users
to email or WhatsApp instead of claiming that a message was sent. Choose the delivery
channel before enabling form submissions in production.
