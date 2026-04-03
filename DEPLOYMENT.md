Production deployment checklist

1. HTTPS / TLS

- Use a reverse proxy (NGINX, Traefik) or cloud load balancer to terminate TLS.
- Ensure `SITE_URL` uses https:// and `TRUSTED_HOSTS` contains the host.
- Set `SECURE_COOKIES=1` in the environment for production.
- Add `HSTS` by leaving `APP_ENV=production` so Strict-Transport-Security header is enabled.

2. Secrets & env

- Provide `SECRET_KEY`, `DATABASE_URL`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD_HASH`.
- Do not commit secrets to source control.

3. Database migrations

- This project uses SQLAlchemy; for production use Alembic.
- Current code includes a pragmatic `ensure_database_schema` that patches known schema drift, but migrate to Alembic for versioned migrations.
- Suggested commands:
  - pip install alembic
  - alembic init alembic
  - configure alembic.ini to use DATABASE_URL

4. Logging & monitoring

- Provide `SENTRY_DSN` to enable Sentry error tracking.
- Configure log collection (structured logs) via your platform.

5. Rate limiting & brute-force

- Current in-memory limiter is suitable for small deployments or single-instance apps.
- For multiple replicas, use Redis-based rate limiting and lockouts.

6. Performance / Lighthouse

- Serve static assets via CDN or reverse proxy with long cache TTLs (already set for /static).
- Enable gzip/brotli at proxy or app level.
- Pre-render or carefully optimize templates and images. Verify Lighthouse locally (`lighthouse <url>`).

7. Run

- Use Uvicorn/ Gunicorn workers behind a proxy. Example:
  - uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

8. Tests

- Run `pytest` in CI. Provide a dedicated test DB for integration tests.

9. Reverse proxy examples

Nginx (example):

```
server {
  listen 80;
  server_name example.com www.example.com;
  return 301 https://$host$request_uri;
}

server {
  listen 443 ssl http2;
  server_name example.com www.example.com;

  ssl_certificate /etc/ssl/certs/fullchain.pem;
  ssl_certificate_key /etc/ssl/private/privkey.pem;

  location /static/ {
    root /var/www/yourapp;
    expires 1y;
    add_header Cache-Control "public, max-age=31536000, immutable";
  }

  location / {
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_pass http://127.0.0.1:8000;
  }
}
```

Caddy (automatic TLS):

```
example.com {
  reverse_proxy 127.0.0.1:8000
  encode zstd gzip
  file_server {
    root /var/www/yourapp/static
  }
}
```

HTTPS enforcement:

- Always terminate TLS at the proxy. Set `APP_ENV=production` and ensure `SITE_URL` uses https://.
- For cookies: set `SECURE_COOKIES=1` and ensure `session` cookie is marked Secure and SameSite=strict or Lax as appropriate.

CI / CD and Redis enforcement

- This repository includes a GitHub Actions workflow at `.github/workflows/ci.yml` which:
  - installs dependencies,
  - runs Alembic migrations against a test DB,
  - runs the test suite,
  - verifies Sentry connectivity (optional).

- In production the app now enforces Redis presence: if `APP_ENV=production` the app will raise an error at startup unless `REDIS_URL` is set and the `redis` package is installed. This prevents accidental runs without distributed rate-limiting and ensures consistency for lockouts in multi-replica deployments.
