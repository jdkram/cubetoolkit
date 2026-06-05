# Screenshot Automation Quick Reference

Automated visual regression testing and release documentation for the Cube Toolkit.

---

## One-command release workflow

If you are cutting a release, use `scripts/release.sh` instead of running the commands below by hand:

```bash
# 1. Edit VERSION to the new version string
# 2. Run the release helper
scripts/release.sh
```

It will:
- find the previous version from git tags
- health-check the dev server
- optionally re-seed demo data
- capture screenshots with the previous release as baseline
- open the gallery in your browser
- pause for your review
- commit, tag, and optionally push

The rest of this doc covers the underlying script and manual workflows.

---

## What it does

`scripts/capture_screenshots.py` drives a headless Chromium browser (via Playwright) against the running local dev server, captures 17 key pages at 5 viewport sizes, and produces:

- `screenshots/current/<version>/` — the raw PNG captures
- `screenshots/gallery/<version>.html` — a static HTML report with before/after sliders and a "changed only" filter
- `screenshots/diffs/<version>/` — pixel-difference images (when a baseline is supplied)

Nothing is committed to git. The `screenshots/` directory is gitignored.

---

## Prerequisites

1. Dev server running with demo data:

   ```bash
   docker compose up -d
   docker compose exec toolkit /venv/bin/python3 manage.py seed_dev_data --wipe
   docker compose exec toolkit /venv/bin/python3 manage.py configure_toolkit_users --password password
   ```

2. `uv` installed on the host (for transient dependency management).

---

## First run — no baseline

```bash
uv run --with playwright --with Pillow \
  scripts/capture_screenshots.py \
  --version 2026.06.2 \
  --output screenshots/current/
```

Open the report:

```bash
firefox screenshots/gallery/2026.06.2.html
```

This produces 85 captures (17 pages × 5 viewports). All cards in the gallery will show a green **new** badge because there is no baseline to compare against.

---

## Subsequent runs — with baseline

After you have a version you trust, promote it to the baseline folder:

```bash
# Copy the captures you want to keep as the reference set
cp -r screenshots/current/2026.06.2 screenshots/baseline/2026.06.2
```

Then on the next release:

```bash
uv run --with playwright --with Pillow \
  scripts/capture_screenshots.py \
  --version 2026.06.3 \
  --output screenshots/current/ \
  --baseline screenshots/baseline/2026.06.2
```

The gallery will now show:

- **Red diff badge** — pages where pixels changed (drag the slider to see before/after)
- **Green new badge** — pages that did not exist in the baseline
- **No badge** — identical to baseline

---

## Promoting images for release notes

Copy specific screenshots into a curated `featured/` folder for use in GitHub Release notes or demo decks:

```bash
mkdir -p screenshots/featured/2026.06.3

cp screenshots/current/2026.06.3/390x1200__rota-edit.png \
   screenshots/featured/2026.06.3/
```

Add a caption file alongside:

```bash
cat > screenshots/featured/2026.06.3/rota-edit.yml <<EOF
caption: "Tap-to-sign-up now works on mobile rota"
EOF
```

---

## Pages captured

| Persona | Pages |
|---|---|
| **Anonymous** | Programme home (`/`), collectives public (`/labs/collectives/public/`), event detail (`/id/<n>/`) |
| **Volunteer** | Toolkit dashboard (`/toolkit/`), rota edit (`/diary/edit/rota/`), volunteer directory (`/volunteers/directory/`), bulletins (`/labs/bulletins/`) |
| **Programmer** | Diary edit list (`/diary/edit/`), calendar (`/diary/edit/calendar/`), jobs (`/labs/jobs/`), event edit form (`/diary/edit/event/id/<n>/`) |
| **Panopticon** | Member search (`/members/search/`), volunteer list (`/volunteers/`), access transparency (`/toolkit/access/`), site config (`/diary/edit/site-config/`) |
| **Public Labs** | Donations (`/labs/donations/`), community exchange (`/labs/exchange/`) |

---

## Customising

### Different password

```bash
--password MyDevPassword
```

### Different base URL

```bash
--base-url http://localhost:8001
```

### Add or remove pages

Edit the `ANONYMOUS_PAGES`, `VOLUNTEER_PAGES`, `PROGRAMMER_PAGES`, `PANOPTICON_PAGES`, and `PUBLIC_LABS_PAGES` lists near the top of `scripts/capture_screenshots.py`.

### Change viewports

Edit the `VIEWPORTS` list in the same file. The script currently uses:

- mobile-narrow: 375×1100
- mobile: 390×1200
- tablet: 768×1024
- desktop: 1280×800
- wide: 1920×1080

Mobile heights are deliberately taller than real devices so filter bars do not swallow the entire viewport.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Server not responding` | `docker compose up -d` and wait for migrations |
| `Login failed` | Re-run `configure_toolkit_users --password password` |
| Pages timeout repeatedly | The dev server may be under load; increase the `--timeout` flag (not yet exposed — edit `15_000` in the script) |
| Event detail/edit pages are blank | The script discovers IDs dynamically; if the listing pages are empty, no IDs are found. Seed data fixes this. |

---

## Integration with releases

See [ONBOARDING.md](ONBOARDING.md) §"Releases and Versioning" for the full release workflow. Screenshots are an **optional but recommended** step between tagging and drafting the GitHub Release:

1. Bump `VERSION` and commit
2. Tag and push
3. **Run `capture_screenshots.py`** against the new tag
4. Review the gallery; copy changed images to `screenshots/featured/<version>/`
5. Use those images in the GitHub Release notes

This gives every release a visual changelog that volunteers and funders can understand without reading commit messages.
