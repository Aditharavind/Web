# Dependency review — 16 October 2026

The runtime requirements were compared with application imports, Alembic usage,
and the documented Uvicorn launch command. HTTPX remains in the test-only list;
Gunicorn was removed because that deployment does not use it. Transitive HTTP Core
was removed from the runtime lock. Runtime packages retained have an application,
server, migration, PostgreSQL, or transitive dependency role.

Direct runtime and test requirements are pinned. The runtime lock was regenerated
with platform and Python-version markers. Deploy with `requirements.lock`; add
`dev_requirements.txt` only for development and automated checks.

## Verification

- Fresh Python 3.11.17 and 3.12.14 environments installed successfully.
- All 126 Python checks passed on both versions; dependency consistency checks passed.
- A runtime-only Python 3.12 installation contained 31 packages. A real Uvicorn
  process served public pages, the admin login, health and CSS without HTTPX or Gunicorn.
- pip-audit reported zero known vulnerabilities for the 31 runtime packages
  applicable to the audit environment, with no skipped packages. The final fully
  pinned lock was audited with `--no-deps --disable-pip`; conditional packages for
  other environments were not covered by this run.

The audit uses public package advisory data; it is not a complete security audit.
Recheck before deployment. Tool reference: https://github.com/pypa/pip-audit

Passlib 1.7.4 still emits a `crypt` deprecation warning. Its existing bcrypt setup
is retained to preserve compatibility. Python 3.13 is not supported or validated;
stay on Python 3.11/3.12 until the password stack is separately modernized.

Live PostgreSQL/Redis, TLS and backups remain deployment gates described in
DEPLOYMENT.md. The later final verification pass adds session revocation and
records browser results in final-verification.md. This dependency review does not
claim the remaining host checks have passed.
