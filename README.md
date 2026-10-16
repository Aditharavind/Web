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

## Corporate content and design

The redesigned public website uses locally served Inter and Manrope fonts and local
SVG icons. Key editorial content is in `app/core/content.py`; reusable interface
styles are in `app/static/css/corporate.css`. See `docs/content-review.md` for the proposed
mission, vision, values and the identity/contact details requiring confirmation.
Design screenshots are review artifacts and are not included in the application source.

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
| `docs/` | Content review notes |
| `uploads/` | Runtime product images; contents excluded from Git |

`requirements.txt` declares direct runtime dependencies; `requirements.lock` pins
the tested runtime environment. `dev_requirements.txt` adds test tools.
CI installs the locked dependencies, checks migrations and runs tests. Optional
Sentry monitoring is configured in the application through `SENTRY_DSN`.

The stylesheets have separate responsibilities: `app.css` contains shared controls,
product views and admin layouts; `corporate.css` contains public website styling;
`fonts.css` defines the locally served fonts. Obsolete pre-redesign selectors have
been removed, while shared rules needed by the admin panel are retained.
