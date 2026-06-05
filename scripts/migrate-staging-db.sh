#!/bin/bash
#
# migrate-staging-db.sh - Migrate S+S staging/production database to current codebase
#
# Purpose: Load a mysqldump from the old s+s branch into the current master
# codebase, handling migration name differences and schema updates.
#
# Usage: ./migrate-staging-db.sh <path-to-sql-dump> [path-to-media-dir]
#
# Example:
#   ./migrate-staging-db.sh ~/code/sns-staging-toolkit/backups/sns_staging_2026-03-30.sql \
#                           ~/code/sns-staging-toolkit/media
#
# WARNING: do not squash or flatten the Django migrations in this codebase.
#
# This script loads a production SQL dump from the old Django 2.2 s+s branch,
# which has its own migration history recorded in the django_migrations table.
# After loading, it runs `manage.py migrate` normally -- Django then runs every
# migration in this codebase that isn't already recorded in that table.
#
# That means the data migrations (RunPython/RunSQL) DO run on live data and
# are load-bearing: 0019_site_configuration creates the SiteConfiguration row
# the new code depends on; 0012/0021 transform volunteer status fields; others
# normalise data that the old schema stored differently.
#
# Squashing to a single 0001_initial per app would mean either: (a) Django
# tries to CREATE TABLE on tables that already exist and crashes, or (b) you
# use --fake-initial and silently skip all those data migrations, leaving the
# DB in a broken half-migrated state.
#
# Step 5 below also detects old migration names by exact string match -- that
# detection would silently break after a squash.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_DUMP="${1:-}"
MEDIA_DIR="${2:-}"
DB_NAME="${DB_NAME:-toolkit}"
DB_USER="${DB_USER:-root}"
DB_PASSWORD="${DB_PASSWORD:-rubbishpassword}"
DB_HOST="${DB_HOST:-mariadb}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validate arguments
if [[ -z "$SQL_DUMP" ]]; then
    log_error "Usage: $0 <path-to-sql-dump> [path-to-media-dir]"
    log_error ""
    log_error "Example:"
    log_error "  $0 ~/backups/sns_staging_2026-03-30.sql ~/backups/media"
    exit 1
fi

if [[ ! -f "$SQL_DUMP" ]]; then
    log_error "SQL dump not found: $SQL_DUMP"
    exit 1
fi

if [[ -n "$MEDIA_DIR" && ! -d "$MEDIA_DIR" ]]; then
    log_error "Media directory not found: $MEDIA_DIR"
    exit 1
fi

# Check Docker is running
if ! docker compose ps &>/dev/null; then
    log_error "Docker compose is not running. Please start it first:"
    log_error "  docker compose up -d mariadb"
    exit 1
fi

# Check database container is healthy
if ! docker compose exec mariadb mysql -u"$DB_USER" -p"$DB_PASSWORD" -e "SELECT 1" &>/dev/null; then
    log_error "Cannot connect to database. Is the mariadb container running?"
    exit 1
fi

log_info "Starting database migration from: $SQL_DUMP"
log_info "This will DESTROY the current toolkit database and replace it with the dump."
read -p "Are you sure? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Aborted."
    exit 0
fi

# Step 1: Stop toolkit container to avoid conflicts
log_info "Step 1: Stopping toolkit container..."
docker compose stop toolkit || true

# Step 2: Drop and recreate database
log_info "Step 2: Recreating database..."
docker compose exec mariadb mysql -u"$DB_USER" -p"$DB_PASSWORD" -e "
    DROP DATABASE IF EXISTS $DB_NAME;
    CREATE DATABASE $DB_NAME CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
"

# Step 3: Load the SQL dump
log_info "Step 3: Loading SQL dump (this may take a while)..."
docker compose exec -T mariadb mysql -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" < "$SQL_DUMP"
log_info "SQL dump loaded successfully"

# Step 4: Copy media files if provided
if [[ -n "$MEDIA_DIR" ]]; then
    log_info "Step 4: Copying media files..."
    docker run --rm \
        -v sns-toolkit_media_data:/media \
        -v "$MEDIA_DIR:/staging_media:ro" \
        busybox sh -c 'cp -r /staging_media/* /media/ 2>/dev/null || true; echo "Media files copied"'
else
    log_warn "Step 4: No media directory provided, skipping media copy"
fi

# Step 5: Fix migration history
# The old s+s branch had different migration names for some changes.
# We need to update django_migrations to match current codebase expectations.
log_info "Step 5: Fixing migration history..."

# Fix members app migrations
# Old: 0008_volunteer_user (adds user_id to Volunteers)
# New: 0009_volunteer_user (adds user_id to Volunteers) + 0008 is now squashed pronouns migration
# Old: 0009_member_email_is_mandatory
# New: 0010_make_email_mandatory

# Check if we have the old migration names
OLD_MIGRATIONS=$(docker compose exec mariadb mysql -u"$DB_USER" -p"$DB_PASSWORD" -N -e "
    SELECT COUNT(*) FROM $DB_NAME.django_migrations 
    WHERE app='members' AND name='0008_volunteer_user';
")

if [[ "$OLD_MIGRATIONS" -gt 0 ]]; then
    log_info "Detected old migration names, updating django_migrations table..."
    
    # Remove old migration records that have been renamed/reorganized
    docker compose exec mariadb mysql -u"$DB_USER" -p"$DB_PASSWORD" -e "
        DELETE FROM $DB_NAME.django_migrations 
        WHERE app='members' AND name IN ('0008_volunteer_user', '0009_member_email_is_mandatory');
    "
    
    # Insert records for current migration names (schema already exists from old migrations)
    docker compose exec mariadb mysql -u"$DB_USER" -p"$DB_PASSWORD" -e "
        INSERT IGNORE INTO $DB_NAME.django_migrations (app, name, applied) VALUES 
            ('members', '0008_member_preferred_pronouns_squashed_0009_auto_20220627_1114', NOW()),
            ('members', '0009_volunteer_user', NOW());
    "
    
    log_info "Migration history updated"
else
    log_info "Migration history looks correct, no fixes needed"
fi

# Step 6: Run Django migrations
log_info "Step 6: Running Django migrations..."
docker compose run --rm toolkit /venv/bin/python3 manage.py migrate --settings=toolkit.docker_settings_starandshadow

# Step 7: Collect static files
log_info "Step 7: Collecting static files..."
docker compose run --rm toolkit /venv/bin/python3 manage.py collectstatic --noinput --settings=toolkit.docker_settings_starandshadow

# Step 8: Restart toolkit
log_info "Step 8: Restarting toolkit container..."
docker compose up -d toolkit

# Step 9: Verify data
log_info "Step 9: Verifying data..."
sleep 3
DATA_CHECK=$(docker compose exec toolkit /venv/bin/python3 manage.py shell --settings=toolkit.docker_settings_starandshadow -c "
from toolkit.diary.models import Event, Showing
from toolkit.members.models import Member, Volunteer
print(f'Events: {Event.objects.count()}')
print(f'Showings: {Showing.objects.count()}')
print(f'Members: {Member.objects.count()}')
print(f'Volunteers: {Volunteer.objects.count()}')
" 2>&1 | grep -E "^(Events|Showings|Members|Volunteers):")

echo "$DATA_CHECK"

log_info "Migration complete!"
log_info ""
log_info "You can now access the site at:"
log_info "  Public site:  http://localhost:8000/programme/"
log_info "  Admin login:  http://localhost:8000/auth/login/"
log_info ""
log_info "Notes:"
log_info "  - User passwords from the old site will NOT work (different hashing)"
log_info "  - Run 'configure_toolkit_users' to create new admin accounts"
log_info "  - Some images may show thumbnail errors (normal for missing files)"
