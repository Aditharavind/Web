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
Run `ruff check .` for linting and `python -m pytest -q` for isolated tests. Tests never use the development database.
Run `node --test tests/js/*.test.cjs` for JavaScript checks (Node 22; no npm install needed).

## Production

See [DEPLOYMENT.md](DEPLOYMENT.md). Configuration names are in `.env.example`.
Environment files are not loaded automatically. A process manager must supply them.

Contact enquiries use direct email and WhatsApp links. No contact form is exposed.

## Content and design

The public site uses locally served Inter and Manrope fonts and local SVG icons.
Editable wording is in `app/core/content.py` (company intro, mission, vision,
supply categories, reasons) and in `app/templates/`. Public styles are in
`app/static/css/corporate.css`; shared controls and the admin panel are in
`app/static/css/app.css`. Visitors contact the company by WhatsApp or email only.

## Project structure

| Path | Responsibility |
| --- | --- |
| `app/api/routes/` | Public pages, admin endpoints and health checks |
| `app/core/` | Configuration, security, logging and shared editorial content |
| `app/database/` | Database connection and SQLAlchemy table definitions |
| `app/models/schemas.py` | Validated input/output schemas |
| `app/services/` | Authentication, product/image handling and visitor analytics |
| `app/templates/` | Page templates and reusable partials |
| `app/static/` | Styles, scripts, icons and locally served fonts |
| `app/utils/` | Pagination and text/URL helpers |
| `alembic/` | Versioned database migrations |
| `tests/` | Isolated automated checks |
| `uploads/` | Runtime product images; contents excluded from Git |

`requirements.txt` declares direct runtime dependencies; `requirements.lock` pins
the tested runtime environment. `dev_requirements.txt` adds test tools.
CI checks Python 3.11 and 3.12, installs the locked dependencies, checks migrations,
and runs Python and JavaScript tests. Optional
Sentry monitoring is configured in the application through `SENTRY_DSN`.

## Files kept outside Git

`uploads/.gitkeep` preserves the empty runtime directory in a fresh checkout.
Product images belong in the persistent upload directory and must be backed up
with the database; do not delete them during cleanup. Virtual environments,
Python caches, local databases and secrets are excluded from Git.

The admin supports image previews, automatic resizing and orientation correction,
and choosing the primary image, but has no interactive crop editor. Remaining launch
checks are listed in DEPLOYMENT.md. Stay on Python 3.11/3.12 (Passlib 1.7.4).
HTTPX is test-only; the documented server uses Uvicorn directly.
