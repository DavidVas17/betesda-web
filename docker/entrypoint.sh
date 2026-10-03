#!/bin/sh
set -eu

if [ "${WAIT_FOR_DATABASE:-true}" = "true" ]; then
  python - <<'PY'
import os
import time

import psycopg

database_url = os.environ["DATABASE_URL"]
for attempt in range(30):
    try:
        with psycopg.connect(database_url, connect_timeout=3):
            break
    except psycopg.OperationalError:
        if attempt == 29:
            raise
        time.sleep(1)
PY
fi

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  python manage.py migrate --noinput
fi

if [ "${RUN_SETUP_ROLES:-true}" = "true" ]; then
  python manage.py setup_roles
fi

if [ "${COLLECT_STATIC:-false}" = "true" ]; then
  python manage.py collectstatic --noinput
fi

exec "$@"
