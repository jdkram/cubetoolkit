#!/bin/bash
set -eu

COMMAND=${1:-}

echo "Running as: $(id)"

if [[ -v DB_HOST && -v DB_PORT && -n $DB_HOST && -n $DB_PORT ]] ; then
  if ! wait-for-it $DB_HOST:$DB_PORT --timeout=360 ; then
    echo "Database host not available"
    exit 3
  fi
elif ! [[ -S /var/run/mysqld/mysqld.sock ]] ; then
  echo "Database socket not available"
  exit 3
fi

case "$COMMAND" in
    gunicorn)
        echo "Running database migrations"
        /venv/bin/python3 /site/manage.py migrate
        GUNICORN_EXTRA_ARGS=()
        if [[ "${GUNICORN_RELOAD:-}" == "1" ]]; then
            echo "Hot-reload enabled (development mode)"
            GUNICORN_EXTRA_ARGS+=("--reload")
        fi
        exec /venv/bin/gunicorn wsgi --bind 0.0.0.0:8000 --chdir /site "${GUNICORN_EXTRA_ARGS[@]}"
        ;;
    mailerd)
        exec /venv/bin/python3 /site/manage.py mailerd
        ;;
    *)
        echo "Unknown option; expected gunicorn or mailerd"
        exit 5
        ;;
esac
