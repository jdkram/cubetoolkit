# Maintainability Pass Plan

> **Status:** in progress on branch `chore/maintainability-pass`, branched from `sns_2026_overhaul` at `6d9cf776`.
> **Last updated:** 2026-06-26
> **Source review:** fresh-eyes code review dispatched 2026-06-26 (four parallel deep reads of diary, members+auth, labs+inductions+mailer, settings+scripts+docs+tests).
> **Resume by:** reading this file top-to-bottom — each chunk has status + scope + commit guidance. Check `git log chore/maintainability-pass` to see which chunks have shipped.

## Goals

Lens: maintainability for a future maintainer WITHOUT AI assistance. Scope: full pass — attic, latent bugs, shared helpers, god-module splits, SiteConfiguration tax, feature-flag reconciliation, migration squashing, docs cleanup. Motivation: tidying for its own sake (no external deadline), so each commit should independently improve the repo and the sequence is safe to stop at any chunk.

## Squashing baseline

Merge-base with `master`: `afe1117e` ("Add onboarding documentation for new developers"). Migrations added on `sns_2026_overhaul` since that commit are squash-candidate (no live DB is on the S+S branch). Pre-baseline migrations stay untouched:

| App | Pre-baseline (keep) | Squash-candidate range | First new migration |
|---|---|---|---|
| diary | 0001-0008 | 0009-0090 (81 files) | `0009_add_role_description.py` |
| members | 0001-0008 | 0009-0029 (20 files) | `0009_volunteer_user.py` |
| labs | (none) | 0001-0027 (all 27) | `0001_initial.py` |
| inductions | (none) | 0001-0008 (all 9) | `0001_initial.py` |
| mailer | 0001 | 0002 (1) | `0002_alter_mailoutjob_body_html.py` |
| index | 0001-0002 | 0003 (1) | `0003_indexlink_description.py` |

~139 of 178 migration files are squashable.

## Committed creds

Two legacy import commands ship hardcoded DB passwords (`ye2EUsSUCYY8ALx7`, `kq9LaMpgf4czGQ9v`). Decision: just delete the files. No rotation note (`s+s`-era creds, assumed stale).

## Chunks

Each chunk = one or more commits, independently reviewable, ordered by risk.

### Chunk 1: Delete the attic — DONE 2026-06-26

Very low risk. ~800 LOC removed. No behaviour change. No tests affected (no live importers). 959 tests pass.

Deleted:
- [x] `toolkit/util/management/commands/mailman-subscriber.py` (Python 2 only, no BaseCommand)
- [x] `toolkit/util/management/commands/delete_all_members.py` (`django.utils.six` removed in Django 3)
- [x] `toolkit/util/management/commands/delete_members_who_dont_get_the_mailout.py` (destructive, only doc ref)
- [x] `toolkit/util/management/commands/delete_non_members_who_dont_get_the_mailout.py` (destructive one-off)
- [x] `toolkit/util/management/commands/keep_vols_from_csv_retire_everyone_else.py` (destructive, retire workflow removed)
- [x] `toolkit/util/management/commands/backfill_qualifications_from_training.py` (self-described one-off)
- [x] `toolkit/util/management/commands/import_members_from_csv.py` (hardcoded `upcoming.csv`, 0 refs)
- [x] `toolkit/util/management/commands/check_vols_against_mailman.py` (Cube-specific, Mailman 2 EOL, paired with mailman-subscriber)
- [x] `toolkit/util/management/commands/mysqldump_database.py` (0 refs, obsolete flags, "production has own backup")
- [x] `toolkit/util/management/commands/show_active_vols.py` (0 refs, trivial)
- [x] `toolkit/util/management/commands/show_email_duplicates.py` (0 refs, commented-out delete, unfinished)
- [x] NOT deleted: `strip_lines.py` is live (used in `mailout_body.txt`, not `.html` — initial grep scope was too narrow). Restored after test failure.
- [x] `toolkit/diary/templatetags/tk_crispy_filter.py` (zero usages)
- [x] `scripts/fix_orphaned_showings.py` (one-off, migration done per CURRENT_WORK:253)
- [x] `scripts/fix_rooms_after_migration.py` (one-off, duplicates rooms.toml)

In-place edits:
- [x] Remove `_adjust_colour_historic` from `diary/edit_views.py:271-276` (no callers)
- [x] Remove `EDIT_INDEX_DEFAULT_USE_POPUPS` setting from `settings_common.py:82` (no refs)
- [x] Remove commented-out block in `Event.clear_main_mediaitem` at `diary/models.py:745-748`
- [x] Remove commented `created_at = ...` in `RotaEntry` at `diary/models.py:1453`
- [x] Remove dead `from django.core.exceptions import PermissionDenied` import in `inductions/views.py:11`
- [x] Remove unreachable line in `labs/forms.py:414` (after `return`)

Commit: `chore: delete dead attic — broken one-offs, unused templatetags, dead helpers`

### Chunk 2: Remove committed credentials — DONE 2026-06-26

Very low risk. ~700 LOC removed.

- [x] Delete `toolkit/util/management/commands/import_legacy_events.py` (hardcoded `ye2EUsSUCYY8ALx7`)
- [x] Delete `toolkit/util/management/commands/import_legacy_documents.py` (hardcoded `kq9LaMpgf4czGQ9v`)

Commit: `chore(security): delete legacy import scripts that shipped hardcoded DB passwords`

Very low risk. ~450 LOC removed.

- [ ] Delete `toolkit/util/management/commands/import_legacy_events.py` (hardcoded `ye2EUsSUCYY8ALx7`)
- [ ] Delete `toolkit/util/management/commands/import_legacy_documents.py` (hardcoded `kq9LaMpgf4czGQ9v`)

Commit guidance: `chore(security): delete legacy import scripts that shipped hardcoded DB passwords`

### Chunk 3: Fix 5 latent bugs — DONE 2026-06-26

Low risk, small. 959 tests pass (no new failures; note: legacy-redirect and calendar-summary paths had no test coverage before or after, so the fixes are unverified by the suite).

- [x] `diary/public_views.py:372` `redirect_legacy_event` referenced removed `Event.notes` (would raise FieldError) — repointed to `programming_notes__contains` (migration 0067 copied the substring content across)
- [x] `diary/calendar_links.py:56` read `showing.room` (no longer exists; `getattr` default silently hid the bug) — now uses `showing.primary_room`; room names will now actually appear in calendar summaries when MULTIROOM_ENABLED
- [x] `toolkit/devserver_settings.py:32` typo `email_unsubcribe_host` → `email_unsubscribe_host` (was silently no-oping the override)
- [x] `labs/forms.py:414` unreachable line after `return` — already deleted in chunk 1
- [x] `members/volunteer_views.py:1252` success message was a plain string, not an f-string — added `f` prefix (function slated for deletion in chunk 5; fix is moot but harmless)
- [x] Bonus: `diary/edit_views.py:596` `clone_event` docstring referenced removed `notes` field — updated to `programming_notes`
- [x] Bonus: `diary/edit_views.py:_film_json` emitted identical `poster_url_sm`/`poster_url_md` keys (dead vestige of TMDB's w92/w185 sizes) — collapsed to single canonical `poster_url` key (matches OMDb search response shape and the `form_event.html` JS preference)

Commit: `fix: latent bugs found in code review — legacy redirect, calendar summary, dev settings typo, success msg`

### Chunk 4: Extract shared helpers — PENDING

### Chunk 4: Extract shared helpers — IN PROGRESS (commit A done 2026-06-26)

Low-moderate. Net negative LOC. Tests stay green (959 pass).

- [x] **Commit A** `toolkit.toolkit_auth.password_emails` — single module for build-password-reset-token + send/welcome/reset email + venue/from-address lookup. Replaces 3 duplicate paths:
  - `members/volunteer_views._send_password_set_email` → thin delegate (also drops `default_token_generator`/`force_bytes`/`urlsafe_base64_encode` imports)
  - `inductions/views._send_password_reset_email` → reuses `build_password_reset_url` + `password_reset_validity` + `venue_name` + `from_email` from helper (inductor-confirmation copy stays inductions-specific)
  - `inductions/emails.send_welcome_email` → reuses `build_password_reset_url` + `password_reset_validity` (template-driven subject/body via InductionsSettings preserved)
  - Bonus: `inductions/views._test_template_vars` and `inductions/emails._venue/_from_email` now delegate to the helper
  - Note: behavioural change — members' version read `settings.VENUE["longname"]` strictly (KeyError if unset); now uses the same lenient `.get("longname", .get("name", ""))` fallback used by inductions. Stricly more robust; S+S deploys set longname.
- [ ] **Commit B** `members.render_email_template(template, name, venue)` — replaces 4 `.replace("{name}", ...).replace("{venue}", ...)` sites at `volunteer_views.py:696-697, 832-833, 1070-1075, 1875-1880`.
- [ ] **Commit B** `labs._get_volunteer(user)` — replaces 11 bare `except Exception:` blocks at `labs/views.py:163, 185, 197, 819, 844, 861, 879, 901, 1088, 1174, 1211`. Use `hasattr(request.user, "volunteer")`.
- [ ] **Commit C** `toolkit.test_common.ToolkitAuthMixin` — replaces the per-app "create admin/read_only/no_perm users + dummy ContentType + toolkit.write/read permissions" boilerplate copy-pasted across `diary/tests/common.py:450-504`, `members/tests/common.py:142-175`, `labs/tests/common.py:15-49`, `inductions/tests/common.py:19-44`.

Commit guidance (one per helper or split per app): `refactor(auth): extract password-email and template-render helpers` etc.

### Chunk 5: Split `volunteer_views.py` into `members/views/` subpackage — PENDING

Moderate risk. URL paths preserved; view predicates unchanged.

- [ ] Create `members/views/` package with submodules:
  - `volunteer_reports.py` — `view_volunteer_list`, `view_volunteer_summary`, `view_volunteer_directory`, `view_volunteer_training_records`, `view_qualification_report`
  - `volunteer_stats.py` — `volunteer_stats` (the 246-line method) + its local helpers
  - `volunteer_edit.py` — `edit_volunteer`, training-record add/delete, qualification add/remove, `save_volunteer_permissions`, `set_volunteer_password`, `send_volunteer_password_reset`
  - `volunteer_pool_admin.py` — pool health, bulk anonymise, bulk delete never-onboarded, auto-dormancy, last-gasp (single + bulk)
  - `volunteer_bulk_record.py` — `bulk_record` + helpers
  - `volunteer_suspension.py` — `toggle_volunteer_suspension`, `send_suspension_email`, `skip_suspension_email`
  - `volunteer_self_service.py` — `reactivate_self`, `volunteer_digest_unsubscribe`
  - `volunteer_export.py` — `export_volunteers_as_csv`, `export_audit_log`, `_EXPORT_FIELD_GROUPS`
- [ ] Update `members/urls.py` imports to point at the new modules
- [ ] Drop superseded duplicates: `add_volunteer_training_group_record` (`volunteer_views.py:1217`), `bulk_award_qualification` (`volunteer_views.py:1508`) — both replaced by unified `bulk_record`; remove their URL routes and tests; note the f-string bug at `:1252` goes with them
- [ ] Drop the bare shim `view_volunteer_role_report` (`volunteer_views.py:853-855`, only redirects) — or convert to `RedirectView` in `urls.py`; remove its own test
- [ ] Keep `volunteer_views.py` as a thin re-export shim temporarily if needed for any external imports, then delete once grep confirms no consumers

Structure: "move first, refactor after" — one commit for the moves (clean renames in `git log --stat`), one for the deletions.

### Chunk 6: Split `labs/views.py` + register unregistered models — PENDING

Moderate. URL paths preserved.

- [ ] Split `labs/views.py` (1,567 lines) into `labs/views/` per feature:
  - `collectives.py` (140-233), `floorplan.py` (237-305), `donations.py` (308-387), `jobs.py` (399-483), `loft.py` (488-558), `area_photos.py` (563-591), `bulletins.py` (587-791), `shopping.py` (794-1238), `lost_found.py` (1243-1326), `exchange.py` (1331-1567)
- [ ] Update `labs/urls.py` imports
- [ ] Register the seven unregistered labs models in `labs/admin.py`: `RoomNote`, `LoftItem`, `BulletinRead`, `ProcurementPledge`, `CollectiveLink`, `AreaPhoto`, `LoftItemPhoto`
- [ ] Register the four inductions models in `inductions/admin.py` (currently a 2-line stub)

Move-first, refactor-after. Commit guidance: `refactor(labs): split views per-feature; register admin for unregistered models`

### Chunk 7: Split `diary/edit_views.py` + models package — PENDING

Moderate. Import paths preserved via `models/__init__.py` re-exports.

- [ ] Split `diary/edit_views.py` (2,888 lines) into `diary/views/` subpackage — natural split: rota views (2041-2267), event CRUD (470-763, 1208-1383), showing CRUD (1107-1198, 1439-1473), templates (1563-1753), tag/role/room admin (1755-1938, 2574-2621), site config (2320-2536), film/OMDb (2724-2888), reports (1474-1560)
- [ ] Split `diary/models.py` (2,437 lines) into `models/` package:
  - `models/site_config.py` — `SiteConfiguration` (775 lines)
  - `models/event.py` — `Event`, `EventLink`, `EventTemplateLink`, `EventTermsRevision`, `Film`
  - `models/showing.py` — `Showing`, `RoomBooking`, `Room`
  - `models/rota.py` — `Role`, `EventTemplate`, `EventTemplateRole`, `EventTemplateRoom`, `RotaEntry`
  - `models/misc.py` — `MediaItem`, `EventTag`, `DiaryIdea`, `PrintedProgramme`, `VolunteerEventMark`
  - `models/__init__.py` re-exports everything to preserve `from toolkit.diary.models import X`
- [ ] Move `_safe_json` duplicate (`public_views.py:9` + `edit_views.py:64`) into `diary/utils.py` or `daterange.py` (already the shared module)

Move-first.

### Chunk 8: SiteConfiguration auto-form — PENDING

Moderate-high. Closes the 4-place sync tax.

- [ ] Add a `group` attribute (or `meta`) on each `SiteConfiguration` field naming its form-section
- [ ] Derive `SiteConfigurationForm.Meta.fields` from the model `_meta`
- [ ] Derive `edit_site_configuration`'s `field_groups` list (`edit_views.py:2325-2467`) from the model metadata
- [ ] Add a test asserting form `Meta.fields` parity with model fields so future drift fails loudly

Commit guidance: `refactor(diary): auto-derive SiteConfiguration form fields from model metadata`

### Chunk 9: Reconcile feature-flag systems — PENDING

Moderate-high. Small LOC delta. Tests per touched field.

- [ ] Pick and document one precedence rule in `SiteConfiguration` docstring: "DB wins, settings.py seeds"
- [ ] Make `omdb_api_key`, `eventlink_extra_allowed_domains`, `programme_*` max-chars/min-words fields consistently DB-first across all readers
- [ ] Decide per-field for `TAGS_WITHOUT_TERMS`, `EDIT_INDEX_DEFAULT_DAYS_AHEAD`, `MULTIROOM_ENABLED` etc. — fold into SiteConfiguration OR mark explicitly as settings-only with a comment
- [ ] Remove the dead/misleading claim in the `SiteConfiguration` docstring (`models.py:1627-1632`)

### Chunk 10: Squash migrations — PENDING

High on active deploys; safe here (fresh-branch port, no live DB on `sns_2026_overhaul`). Squash in stable chunks, NOT big-bang.

Per app, squash the migration range above the merge-base (see "Squashing baseline" table). Preserve data-migration semantics for: `0014 copy_roles_to_through_model`, `0047 seed_new_fields`, `0050 carry_over_dormancy_value`, `0067 copy_notes_to_programming_notes`, `0071 seed_ticketsource_guidance`. If squashing past these, fold the data migration into the squashed migration's `RunPython`.

Order:
- [ ] Squash diary 0009-0029 → diary 0009_v2 (foundation layer)
- [ ] Squash diary TMDB cycle 0075-0083 → fold (add-then-remove disappears; create Film with OMDb fields)
- [ ] Squash diary SiteConfiguration field-add migrations 0036-0090 → diary 0010_v2 (one CreateModel + seed data)
- [ ] Squash members 0009-0029 → members 0009_v2
- [ ] Squash labs 0001-0027 → labs 0001_initial_v2 (single initial migration, whole app)
- [ ] Squash inductions 0001-0008 → inductions 0001_initial_v2 (single initial)
- [ ] mailer + index already single-file additions; leave alone unless tests catch issues

Test DBs rebuild from scratch, so squash correctness is verified by the suite running clean.

### Chunk 11: Docs cleanup — PENDING

Low risk. No tests.

- [ ] CURRENT_WORK.md: archive done-items older than the latest release into CHANGELOG.md only. Improve signal-to-noise for "what's actually left". Move the "Last updated" run-on sentence into structured fields.
- [ ] `docs/tasks/events-and-rota.md` (3,775 lines): split by feature or shrink. Largest spec file, larger than SPEC + ONBOARDING combined.
- [ ] Move rewrite-essay sections out of `docs/SPEC.md` (sections 10-12, ~300 lines) into `docs/REWRITE_STRATEGY.md`. Keep SPEC as a snapshot of the current system.
- [ ] Fix the broken-ish `BRANCH_NOTES.md` link in `CLAUDE.md` (points at `docs/BRANCH_NOTES.md`, file is at `docs/ARCHIVE/BRANCH_NOTES.md`)
- [ ] `docs/ARCHIVE/README.md` is 1 line — make it a real index, or remove
- [ ] Flatten `docs/ROADMAP.md` since `CURRENT_WORK` has overtaken it; or freeze it with a clear "superseded by CURRENT_WORK" header

---

## Verification command (run after each chunk)

```bash
docker compose exec toolkit /venv/bin/python3 manage.py test --settings=toolkit.test_settings
```

Per-app suite for faster feedback:
```bash
docker compose exec toolkit /venv/bin/python3 manage.py test toolkit.diary --settings=toolkit.test_settings
docker compose exec toolkit /venv/bin/python3 manage.py test toolkit.members --settings=toolkit.test_settings
docker compose exec toolkit /venv/bin/python3 manage.py test toolkit.labs --settings=toolkit.test_settings
```

Black check before each commit:
```bash
docker compose exec toolkit /venv/bin/black --line-length 79 --check toolkit/
```