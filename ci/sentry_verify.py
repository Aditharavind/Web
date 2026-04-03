"""Simple Sentry verification script: checks SENTRY_DSN and tries to capture a test event."""
import os
import sentry_sdk

DSN = os.getenv("SENTRY_DSN", "")
if not DSN:
    print("SENTRY_DSN not set; skipping Sentry verification.")
    raise SystemExit(0)

sentry_sdk.init(DSN, traces_sample_rate=0.0)
print("Sentry initialized; sending test message...")
try:
    with sentry_sdk.push_scope() as scope:
        scope.set_tag("ci-check", "true")
        sentry_sdk.capture_message("Sentry test event from CI")
    print("Test event captured (may take a few seconds to appear in Sentry).")
except Exception as exc:
    print("Sentry verification failed:", exc)
    raise
