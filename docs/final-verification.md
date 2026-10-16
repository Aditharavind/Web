# Local integrated verification — 16 October 2026

## Result

The staged source review and local integrated verification have passed. This is
not clearance for a particular production host: no AWS resources, DNS, production
PostgreSQL/Redis, TLS or backup/restore setup were provisioned or verified here.

## Final fixes

- Added database-backed admin sessions. Cookies include a random nonce; only token
  hashes are stored. Logout revokes the selected session across service instances.
  Other sessions remain active. Password-hash and secret rotation invalidate cookies.
- Added migration `0003_admin_sessions`. Upgrade testing preserved existing product
  rows; the new table matches the ORM model. Existing admin cookies need a new login.
- Invalid PNG checksums now produce upload validation errors instead of server errors.

## Verified

- Python 3.11 and 3.12: 130 tests passed on each version.
- JavaScript: two dependency-free Node checks passed.
- Real Chromium browser: Home, About, Services, Catalogue and Contact tested at
  1440, 768 and 390 pixel widths; one main landmark and H1, no horizontal overflow.
- Mobile navigation opened and closed with Escape. Mobile admin sign-out was visible.
- Browser admin flow: login, add product/image, edit description/specifications,
  append image, view public details and gallery, remove image, delete product, logout.
- No page-script or HTTP errors during the successful browser flow.
- Production-mode HTTP configuration: HTTPS redirect, trusted-host rejection,
  secure CSRF cookie, HSTS, CSP, no-store on admin pages and disabled API docs.
  These checks used temporary SQLite and did not test live Redis startup or PostgreSQL.
- Migration generation, upgrade/downgrade round trips, product preservation and
  migration/model alignment passed against temporary databases.
- Logout replay, session expiry, distinct concurrent sessions, and credential rotation
  were checked. Authentication database work on async product writes is offloaded.

Runtime dependency audit results are recorded separately in dependency-review.md.
The known Passlib deprecation warning remains; use Python 3.11/3.12.

## Before launch

1. Verify PostgreSQL migrations, grants, backup and restore on the selected host.
2. Verify Redis startup, rate limiting across workers and failure behavior.
3. Configure trusted proxy forwarding, TLS, secure cookies, persistent uploads,
   process supervision, log/disk limits and monitoring.
4. Confirm content/location, domain DNS, hosting account/region and budget.
5. Choose visitor-data retention. Current tracking keeps one row per tracked page;
   recording runs after the response but still uses a database write.
6. Decide whether interactive image cropping is required. Previews, resizing and
   orientation correction exist; an interactive crop editor is not implemented.

Do not delete the existing local database or uploads as part of deployment cleanup.
