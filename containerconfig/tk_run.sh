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
    runserver)
        # Development only. Django's runserver serves static files directly from
        # source directories (no collectstatic needed) and auto-reloads on changes.
        echo "Running database migrations"
        /venv/bin/python3 /site/manage.py migrate
        exec /venv/bin/python3 /site/manage.py runserver 0.0.0.0:8000
        ;;
    gunicorn)
        # Production-equivalent. Static files must be baked into the image via
        # collectstatic at build time (see Dockerfile).
        echo "Running database migrations"
        /venv/bin/python3 /site/manage.py migrate
        GUNICORN_EXTRA_ARGS=()
        if [[ "${GUNICORN_RELOAD:-}" == "1" ]]; then
            echo "Hot-reload enabled"
            GUNICORN_EXTRA_ARGS+=("--reload")
        fi
        # Worker count: gunicorn's rule of thumb is (2 × CPU cores) + 1.
        # On a 1-core VM that's 3; on a 2-core VM that's 5.
        # Check with: nproc --all
        # Each sync worker holds one DB connection and ~50-100MB RSS.
        # Stay within available RAM — check with: free -h
        #
        # --timeout: kill and respawn any worker that doesn't respond within
        #   N seconds. Gunicorn's default is already 30s, set explicitly here
        #   so it's visible and intentional. This is the key protection against
        #   a stuck request taking the site down.
        #
        # --max-requests / --max-requests-jitter: recycle workers after N
        #   requests (±jitter) to prevent slow memory growth over long uptimes.
        #   Jitter staggers recycling so all workers don't restart at once.
        exec /venv/bin/gunicorn wsgi \
            --bind 0.0.0.0:8000 \
            --chdir /site \
            --workers 3 \
            --timeout 30 \
            --max-requests 5000 \
            --max-requests-jitter 500 \
            "${GUNICORN_EXTRA_ARGS[@]}"
        ;;
    mailerd)
        exec /venv/bin/python3 /site/manage.py mailerd
        ;;
    *)
        echo "Unknown option; expected runserver, gunicorn, or mailerd"
        exit 5
        ;;
esac
