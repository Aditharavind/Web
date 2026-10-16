#!/usr/bin/env bash
# Source for local development only. Production must provide its own secrets.
export ENVIRONMENT=development
export DATABASE_URL=${DATABASE_URL:-sqlite:///./app.db}
