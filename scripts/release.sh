#!/bin/bash
# Release helper — version bump + screenshot capture + commit + tag + push
#
# Usage:
#   1. Edit VERSION to the new version string
#   2. Run: scripts/release.sh
#   3. Review the gallery in your browser, then confirm to commit/tag/push
#
# What it does:
#   - Reads VERSION for the new version
#   - Finds the previous version from git tags
#   - Verifies the dev server is reachable
#   - Seeds demo data (optional — prompts)
#   - Captures screenshots with the previous version as baseline
#   - Opens the HTML gallery in your default browser
#   - Prompts for confirmation, then commits, tags, and pushes

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VERSION_FILE="${PROJECT_DIR}/VERSION"

cd "${PROJECT_DIR}"

# ── 1. Read new version ─────────────────────────────────────────────
if [[ ! -f "${VERSION_FILE}" ]]; then
    echo "ERROR: ${VERSION_FILE} not found."
    exit 1
fi

NEW_VERSION=$(tr -d '[:space:]' < "${VERSION_FILE}")
if [[ -z "${NEW_VERSION}" ]]; then
    echo "ERROR: VERSION file is empty."
    exit 1
fi

echo "New version: ${NEW_VERSION}"

# ── 2. Find previous version from git tags ────────────────────────────
# Sort tags by version string, newest last. CalVer sorts lexicographically.
PREV_VERSION=""
if git tag -l 'v*' > /dev/null 2>&1; then
    PREV_VERSION=$(git tag -l 'v*' | sed 's/^v//' | sort -V | tail -n1)
fi

if [[ "${PREV_VERSION}" == "${NEW_VERSION}" ]]; then
    echo "WARNING: VERSION has not changed from the latest tag (v${PREV_VERSION})."
    read -rp "Continue anyway? [y/N] " ans
    [[ "${ans}" == [yY]* ]] || exit 0
fi

echo "Previous version: ${PREV_VERSION:-none}"

# ── 3. Check working tree is clean (except VERSION) ───────────────────
UNCLEAN=$(git status --short | grep -v '^\?\?\|^[AM]  VERSION$' || true)
if [[ -n "${UNCLEAN}" ]]; then
    echo "ERROR: Working tree is not clean. Uncommitted changes:"
    echo "${UNCLEAN}"
    exit 1
fi

# ── 4. Health-check the dev server ────────────────────────────────────
BASE_URL="${SCREENSHOT_BASE_URL:-http://localhost:8000}"
if ! curl -sf "${BASE_URL}/health/" > /dev/null 2>&1; then
    echo "ERROR: Dev server not responding at ${BASE_URL}"
    echo "Hint: docker compose up -d"
    exit 1
fi

# ── 5. Optionally re-seed demo data ───────────────────────────────────
read -rp "Re-seed demo data before capturing? [Y/n] " seed_ans
if [[ "${seed_ans}" != [nN]* ]]; then
    echo "Seeding demo data …"
    docker compose exec -T toolkit /venv/bin/python3 manage.py seed_dev_data --wipe
    docker compose exec -T toolkit /venv/bin/python3 manage.py configure_toolkit_users --password password
fi

# ── 6. Run screenshot capture ────────────────────────────────────────
echo ""
echo "Capturing screenshots …"

BASELINE_ARG=""
if [[ -n "${PREV_VERSION}" && -d "screenshots/baseline/${PREV_VERSION}" ]]; then
    BASELINE_ARG="--baseline screenshots/baseline/${PREV_VERSION}"
    echo "  Baseline: ${PREV_VERSION}"
else
    echo "  No baseline found — this will be a first capture."
fi

uv run --with playwright --with Pillow \
    scripts/capture_screenshots.py \
    --version "${NEW_VERSION}" \
    --output screenshots/current/ \
    ${BASELINE_ARG} \
    --base-url "${BASE_URL}"

# ── 7. Open gallery ─────────────────────────────────────────────────
GALLERY="${PROJECT_DIR}/screenshots/gallery/${NEW_VERSION}.html"
if [[ -f "${GALLERY}" ]]; then
    echo ""
    echo "Opening gallery …"
    if command -v xdg-open > /dev/null 2>&1; then
        xdg-open "${GALLERY}"
    elif command -v open > /dev/null 2>&1; then
        open "${GALLERY}"
    else
        echo "  (no opener found — open ${GALLERY} manually)"
    fi
fi

# ── 8. Prompt for commit/tag/push ─────────────────────────────────────
echo ""
echo "────────────────────────────────────────"
echo "Ready to release ${NEW_VERSION}"
echo ""
echo "Next steps:"
echo "  1. Review the gallery (opened above)."
echo "  2. Copy any 'featured' images to screenshots/featured/${NEW_VERSION}/"
echo "  3. Return here and confirm to commit + tag + push."
echo "────────────────────────────────────────"

read -rp "Proceed with git commit + tag + push? [y/N] " confirm
if [[ "${confirm}" != [yY]* ]]; then
    echo "Aborted. No commit or tag was created."
    exit 0
fi

# ── 9. Commit, tag, push ──────────────────────────────────────────────
if git diff --cached --quiet; then
    git add VERSION
fi

git commit -m "chore(release): ${NEW_VERSION}"
git tag "v${NEW_VERSION}"

read -rp "Push commit and tag to origin? [y/N] " push_confirm
if [[ "${push_confirm}" == [yY]* ]]; then
    BRANCH=$(git rev-parse --abbrev-ref HEAD)
    git push origin "${BRANCH}"
    git push origin "v${NEW_VERSION}"
    echo ""
    echo "Pushed. Next: draft a GitHub Release at:"
    echo "  https://github.com/jdkram/sns-toolkit/releases/new?tag=v${NEW_VERSION}"
else
    echo ""
    echo "Commit and tag created locally but not pushed."
    echo "  Commit: $(git rev-parse --short HEAD)"
    echo "  Tag:    v${NEW_VERSION}"
fi

echo ""
echo "Done. Screenshots are in screenshots/current/${NEW_VERSION}/"
