# Deployment preparation

## Current status

The code has had a full review (security headers, CSRF, sessions, uploads, queries,
dependency advisories) and the test suite and linter pass. Before launch, still verify
PostgreSQL, Redis, the proxy forwarding setup and browser behavior on the real host.
Contact enquiries use direct WhatsApp/email links; no form delivery service is needed.

## Configuration

Use Python 3.11 or 3.12. Provide the variables in `.env.example` through a protected
process environment or a root-owned systemd EnvironmentFile. Do not commit secrets.
`ENVIRONMENT=production` is canonical; `APP_ENV` is accepted only as a legacy alias.
Set SITE_URL and TRUSTED_HOSTS to the real domain, SECURE_COOKIES=1, a unique random
SECRET_KEY, a nondefault ADMIN_USERNAME and a bcrypt ADMIN_PASSWORD_HASH.

Generate a secret and password hash locally without putting the password in shell history:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(48))'
python -c 'from getpass import getpass; from passlib.hash import bcrypt; print(bcrypt.hash(getpass("Admin password: ")))'
```

Production startup rejects missing configuration/default passwords and checks Redis.
Keep Redis and PostgreSQL private. Use a dedicated database owner for migrations and
a separate application role with only SELECT/INSERT/UPDATE/DELETE and sequence usage
on the application schema. The application role must also read `alembic_version`.
Do not grant application CREATE, ALTER, superuser or BYPASSRLS privileges.

There is a single configured administrator and a public catalogue; no tenant or user
ownership schema exists. RLS is not implemented. Define ownership rules first if
multiple customer accounts are introduced. HTTPS/TLS is required for this deployment.

## Database lifecycle

For a fresh installation, initialize a new empty database with the migrations below.
Existing local product records and uploads must be backed up before any transfer.
A SQLite-to-PostgreSQL data transfer needs a separate reviewed plan if those records
are to be retained. Do not stamp an unknown existing schema or run destructive resets
against customer databases.

```bash
python -m pip install -r requirements.lock
alembic upgrade head
alembic check
```

Run migrations once, as a deployment step using the migration role. Production startup
only checks the expected migration version; it does not change tables or data.
Development uses SQLAlchemy create_all for convenience.

## AWS host layout

Choose the instance size, region and budget before provisioning. A small single-host
layout can run Nginx, the app, PostgreSQL and Redis; it requires persistent storage,
resource monitoring and independent backups. No AWS resources are provisioned here.

Use a dedicated unprivileged system user, a virtualenv under `/opt/nawa`, and a writable
persistent upload directory such as `/var/lib/nawa/uploads`. Never place uploads in a
release checkout that will be replaced on deployment. Restrict the AWS security group
to HTTPS/HTTP and administrator SSH access; do not expose ports 8000, 5432 or 6379.

Run behind a reverse proxy, with proxy forwarding trusted only from loopback:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips=127.0.0.1
```

Example systemd unit (adjust paths):

```ini
[Unit]
Description=NAWA Global
After=network.target

[Service]
User=nawa
Group=nawa
WorkingDirectory=/opt/nawa/current
EnvironmentFile=/etc/nawa.env
ExecStart=/opt/nawa/venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=on-failure
UMask=0027
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/nawa/uploads

[Install]
WantedBy=multi-user.target
```

Nginx must terminate TLS with a valid certificate and forward Host, X-Forwarded-Proto
and a validated client address. For a single direct-facing Nginx proxy, overwrite
X-Forwarded-For with `$remote_addr`; do not trust arbitrary incoming forwarding headers.
Set `client_max_body_size 50m` and `proxy_read_timeout 120s` to bound multipart bodies:
10 images of 4 MiB each for a single product, or the Excel product import (a workbook of up
to 5 MB plus an images ZIP of up to 40 MB, 200 products per upload). Adjust these proxy
limits if upload settings change. Individual images
are limited to 20 megapixels and are re-encoded as JPEG. Redirect HTTP to HTTPS. Proxy static files through the app initially;
unversioned CSS/JS revalidate on requests, avoiding stale year-long browser caches.

## Verification and recovery

Before switching DNS, verify public pages, mobile layout, static assets, admin login,
logout, invalid credentials, image add/edit/delete, CSRF rejection, rate limiting,
HTTPS redirects, secure cookies and `/health` using the configured Host header.
Visitor timestamps and aggregates use UTC. IPs are addresses, not identified people.

Back up PostgreSQL and uploads together to restricted storage outside the instance. The
`uploads/_w*` folders only hold regenerable smaller WebP copies, so a backup can skip them
(`tar --exclude='uploads/_w*'`).

Browsers keep versioned CSS/JS, fonts and uploaded photos for a year (`immutable`). Do not add
an Nginx `expires` rule or any `proxy_cache` for `/static` or `/uploads` that overrides the
application's `Cache-Control` headers.
Define retention and test a restore. Keep the previous release available; database
rollback requires a reviewed migration/restore plan. Use journald for logs and optionally
Sentry. Monitor disk usage and database growth, and choose visitor-data retention before
traffic grows. Admin sessions are stored as token hashes in `admin_sessions`;
logout removes the session record and clears the browser cookie. Other sessions
remain active. Password-hash or SECRET_KEY rotation invalidates existing cookies.
Expired session records are pruned on successful login.

## Remaining launch gates

- Confirm AWS account/region and budget; configure DNS for nawaglobalgtd.com.
- Complete the final requirements review and recheck dependency advisories at launch.
- Run PostgreSQL/Redis integration checks and repeat visual review after final content approval.
- Provision backups, TLS, monitoring and a tested restore path.
- Confirm whether an interactive image crop editor is required; it is not implemented.

## Session migration introduced during final verification

Migration `0003_admin_sessions` adds the session table and expiry index without
changing products, categories, visits or image paths. Run `alembic upgrade head`
with the migration role before starting production, and grant the application role
access to the new table. Existing cookies require a new login after this release.
In development, the normal schema initialization creates missing tables; do not
run migrations blindly against an existing unversioned local SQLite database.
