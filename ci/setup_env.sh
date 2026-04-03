#!/usr/bin/env bash
# Helper used by CI or locally to set env for tests
export DATABASE_URL=${DATABASE_URL:-sqlite:///./test.db}
export REDIS_URL=${REDIS_URL:-redis://127.0.0.1:6379/0}
export SECRET_KEY=${SECRET_KEY:-test-secret}
export ADMIN_USERNAME=${ADMIN_USERNAME:-admin}
export ADMIN_PASSWORD_HASH=${ADMIN_PASSWORD_HASH:-$(python - <<'PY'
import hashlib
print(hashlib.sha256(b"admin123").hexdigest())
PY
)}
