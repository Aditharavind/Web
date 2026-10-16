# Deployment preparation

## Current status

This branch is preparation for deployment, not a deployed or fully security-audited
release. Verify dependency advisories, PostgreSQL, Redis and browser behavior before
production launch. The contact enquiry delivery channel remains a business decision.

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

Use a new empty database: all previous committed database content and images were
test fixtures and were removed with owner authorization. Do not stamp an unknown
existing schema or run destructive resets against customer databases.

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
Set `client_max_body_size 45m` to bound multipart bodies (10 images, 4 MiB each plus
form overhead). Redirect HTTP to HTTPS. Proxy static files through the app initially;
unversioned CSS/JS revalidate on requests, avoiding stale year-long browser caches.

## Verification and recovery

Before switching DNS, verify public pages, mobile layout, static assets, admin login,
logout, invalid credentials, image add/edit/delete, CSRF rejection, rate limiting,
HTTPS redirects, secure cookies and `/health` using the configured Host header.
Visitor timestamps and aggregates use UTC. IPs are addresses, not identified people.

Back up PostgreSQL and uploads together to restricted storage outside the instance.
Define retention and test a restore. Keep the previous release available; database
rollback requires a reviewed migration/restore plan. Use journald for logs and optionally
Sentry. Monitor disk usage and database growth, and choose visitor-data retention before
traffic grows. A stolen stateless admin session remains usable until expiry; logout only
clears the browser cookie. Rotate SECRET_KEY to invalidate all sessions during an incident.

## Remaining launch gates

- Confirm domain, AWS account/region, budget and enquiry delivery channel.
- Recheck dependency advisories at launch (the local audit currently reports no known vulnerabilities).
- Run PostgreSQL/Redis integration checks and a visual browser review.
- Provision backups, TLS, monitoring and a tested restore path.
