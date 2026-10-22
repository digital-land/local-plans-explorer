#!/bin/sh
set -e
flask db upgrade

# Run the command the container was started with: gunicorn by default (see the
# Dockerfile CMD), or the debug server docker compose passes for local work.
exec "$@"
