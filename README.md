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

Products can be added one at a time or in bulk: **Admin → Products → Import from Excel**
gives a downloadable template (with instructions and an example). Clients fill it in, put the
product pictures in one ZIP, and list the file names in the Images column, so one product can
have several images. See `app/services/import_service.py` for the limits.

Contact enquiries use direct email and WhatsApp links. No contact form is exposed.

## Content and design

The public site uses locally served Inter and Manrope fonts and local SVG icons.
Editable wording is in `app/core/content.py` (company intro, mission, vision,
supply categories, reasons) and in `app/templates/`. Public styles are in
`app/static/css/site.css` (all public pages extend `templates/public.html`); the
admin panel styles are in `app/static/css/app.css`. The home page quote builder
(`static/js/quote.js`) prepares a WhatsApp or email message in the visitor's own
app. Visitors contact the company by WhatsApp or email only.

## Search visibility and speed

- `app/core/seo.py` builds page titles, meta descriptions and the Product/Breadcrumb structured
  data from stored product data only. Products are quote-only, so no prices, offers, ratings,
  reviews or availability are ever published. Google lists the missing `offers` as an optional
  warning; that is intentional.
- `/sitemap.xml` lists the pages, one listing page per category that has products, and every
  product with its photos. Free-text searches and combined filters are `noindex`.
- Product photos are stored once (1600 px JPEG). `/media/<width>/<file>` serves smaller WebP
  copies (160, 320, 480, 720, 960 px) created on first request and kept in `uploads/_w<width>/`.
  They can be deleted at any time and are rebuilt on demand.
- Files requested with `?v=<build>`, fonts and uploaded photos are cached for a year; the build
  version changes whenever any static file changes, so nothing stale is served.
- Admin → Products tags products whose description is very short, because Google shows more of a
  page that has real detail. Write descriptions from verified facts only.

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
