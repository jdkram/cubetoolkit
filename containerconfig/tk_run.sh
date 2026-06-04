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
        echo "Checking media directories"
        /venv/bin/python3 /site/manage.py check_media_dirs --create
        exec /venv/bin/python3 /site/manage.py runserver 0.0.0.0:8000
        ;;
    gunicorn)
        # Production-equivalent. Static files must be baked into the image via
        # collectstatic at build time (see Dockerfile).
        echo "Running database migrations"
        /venv/bin/python3 /site/manage.py migrate
        echo "Checking media directories"
        /venv/bin/python3 /site/manage.py check_media_dirs --create
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
    scheduler)
        # Periodic maintenance jobs. All behaviour is controlled by SiteConfiguration
        # (set volunteer_dormancy_days=0 to make auto_dormancy a no-op, etc.); this
        # container only controls *when* jobs fire. To change the schedule, edit this
        # file and restart the container — no image rebuild needed.
        #
        # Schedule:
        #   auto_dormancy        — daily at 03:00
        #   send_volunteer_digest — daily at 09:00 (which day it sends is controlled
        #                           by SiteConfiguration.volunteer_digest_day; set to
        #                           0 in Django admin to disable without restarting)
        echo "Scheduler started."
        echo "  auto_dormancy:         daily at 03:00"
        echo "  send_volunteer_digest: daily at 09:00 (day controlled by SiteConfiguration)"

        _sleep_until() {
            # Sleep until the next occurrence of HH:MM today (or tomorrow if past).
            local label="$1" time="$2"
            local now target
            now=$(date +%s)
            target=$(date -d "today ${time}" +%s)
            [ "$now" -ge "$target" ] && target=$(date -d "tomorrow ${time}" +%s)
            echo "[scheduler] ${label}: next run at $(date -d @${target} '+%Y-%m-%d %H:%M') ($(( target - now ))s)"
            sleep $(( target - now ))
        }

        _run() {
            local label="$1"; shift
            echo "[$(date '+%Y-%m-%d %H:%M')] [${label}] starting"
            "$@" \
                && echo "[$(date '+%Y-%m-%d %H:%M')] [${label}] done" \
                || echo "[$(date '+%Y-%m-%d %H:%M')] [${label}] FAILED (exit $?)"
        }

        while true; do
            _sleep_until "auto_dormancy" "03:00"
            _run "auto_dormancy" /venv/bin/python3 /site/manage.py auto_dormancy

            # Run the digest command daily at 09:00. The command checks
            # SiteConfiguration.volunteer_digest_day and exits quietly if today
            # is not the configured send day (or if digest is disabled).
            _sleep_until "volunteer_digest" "09:00"
            _run "volunteer_digest" /venv/bin/python3 /site/manage.py send_volunteer_digest
        done
        ;;
    *)
        echo "Unknown option; expected runserver, gunicorn, mailerd, or scheduler"
        exit 5
        ;;
esac
