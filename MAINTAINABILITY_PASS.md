# Maintainability Pass Plan

> **Status:** in progress on branch `chore/maintainability-pass`, branched from `sns_2026_overhaul` at `6d9cf776`.
> **Last updated:** 2026-06-26
> **Source review:** fresh-eyes code review dispatched 2026-06-26 (four parallel deep reads of diary, members+auth, labs+inductions+mailer, settings+scripts+docs+tests).
> **Resume by:** reading this file top-to-bottom — each chunk has status + scope + commit guidance. Check `git log chore/maintainability-pass` to see which chunks have shipped.

## Goals

Lens: maintainability for a future maintainer WITHOUT AI assistance. Scope: full pass — attic, latent bugs, shared helpers, god-module splits, SiteConfiguration tax, feature-flag reconciliation, migration squashing, docs cleanup. Motivation: tidying for its own sake (no external deadline), so each commit should independently improve the repo and the sequence is safe to stop at any chunk.

## Standing notes for the executing model

- **Docs sync (CLAUDE.md hard rule):** code changes update the relevant docs in the same commit. Behaviour-neutral refactors mostly leave `docs/SPEC.md` alone, but: deleted management commands (chunks 1-2) and the data-model split (chunk 7) need a note; status goes in `CURRENT_WORK.md` **only**, not `docs/TASKS.md`.
- **Authorship tags:** use the *actual* contributing model name in `ai-contributors`, not a generic "Claude". (`toolkit/toolkit_auth/password_emails.py` is currently mis-tagged — fix when next touched.)
- **Verify before each commit:** full test suite green (959 baseline as of 2026-06-27) + `black --line-length 79 --check`. See the Verification section at the foot of this file.

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

### Chunk 4: Extract shared helpers — DONE 2026-06-26

Low-moderate. Net negative LOC. Tests stay green (959 pass).

- [x] **Commit A** `toolkit.toolkit_auth.password_emails` — single module for build-password-reset-token + send/welcome/reset email + venue/from-address lookup. Replaces 3 duplicate paths:
  - `members/volunteer_views._send_password_set_email` → thin delegate (also drops `default_token_generator`/`force_bytes`/`urlsafe_base64_encode` imports)
  - `inductions/views._send_password_reset_email` → reuses `build_password_reset_url` + `password_reset_validity` + `venue_name` + `from_email` from helper (inductor-confirmation copy stays inductions-specific)
  - `inductions/emails.send_welcome_email` → reuses `build_password_reset_url` + `password_reset_validity` (template-driven subject/body via InductionsSettings preserved)
  - Bonus: `inductions/views._test_template_vars` and `inductions/emails._venue/_from_email` now delegate to the helper
  - Note: behavioural change — members' version read `settings.VENUE["longname"]` strictly (KeyError if unset); now uses the same lenient `.get("longname", .get("name", ""))` fallback used by inductions. Stricly more robust; S+S deploys set longname.
- [x] **Commit B** `members._render_admin_email(template, name, venue)` — replaces 4 `.replace("{name}", ...).replace("{venue}", ...)` sites at `volunteer_views.py` (last-gasp single + bulk, suspension preview, suspension send). Plain `.replace` (not `str.format`) so stray `{` chars in admin text don't crash.
- [x] **Commit B** `labs._user_volunteer(user)` — replaces 11 bare `except Exception:` blocks across collectives + shopping views. Uses `hasattr(user, "volunteer")` (canonical Django pattern); the try/except variant was silently swallowing real errors (e.g. a corrupt Volunteer row would read as "no volunteer" and hide the bug).
- [x] **Commit C** `toolkit.test_common.create_toolkit_test_users()` — replaces the per-app "create admin/read_only/no_perm users + dummy ContentType + toolkit.write/read permissions" boilerplate copy-pasted across three test commons:
  - `diary/tests/common.py:ToolkitUsersFixture` (Fixture variant — uses `fixtures.Fixture._setUp`)
  - `members/tests/common.py:_setup_test_users` (TestCase setUp variant)
  - `labs/tests/common.py:_setup_test_users` (TestCase variant; exposes users on self for tests that pass them as Bulletin.author / Job.posted_by)
  - **Skipped:** `inductions/tests/common.py` — uses a different shape (no toolkit.write/read perms at all, superuser-only access + its own InductionsSettings fixture). Refactoring it would distort the test intent.
  - **Per-app superuser policy preserved:** diary + members keep `admin` as superuser (Panopticon tier); labs keeps `admin` as non-superuser write-perm user (Programmer tier) because labs panopticon-only tests (`test_bulletin_post_panopticon_blocks_write_user`, `test_non_superuser_gets_403`, `test_non_superuser_cannot_delete_bulletin`) deliberately exercise the "has write but not super" rejection path. Helper takes `is_admin_superuser` (default True); labs passes False.
  - Drops the now-unused `contenttypes` import from all three commons.

Commit guidance (one per helper or split per app): `refactor(auth): extract password-email and template-render helpers` etc.

### Chunk 5: Split `volunteer_views.py` into `members/views/` subpackage — DONE 2026-06-26

Moderate risk. URL paths preserved; view predicates unchanged. 959 tests pass.

- [x] Move commit: split into `members/views/` package with 8 submodules + `_common.py` + `__init__.py` re-export shim. `urls.py` imports unchanged (toolkit.members.views import ..., same names).
- [x] **Refactor-after decision:** the three superseded-duplicate candidates (`add_volunteer_training_group_record`, `bulk_award_qualification`, `view_volunteer_role_report`) are **kept** because they have live test coverage (`test_security.py` panopticon_required matrix + `test_volunteers.py` template-used assertions). Deleting them would either require deleting tests (feels louder than the "tidying for its own sake" remit) or weaken the security contract (a bare RedirectView on `view-volunteer-role-report` would let unauthenticated users hit it). Instead: `view_volunteer_role_report` kept as a one-line `panopticon_required` redirect with an expanded comment explaining WHY it's not a bare RedirectView (so a future maintainer doesn't "simplify" it into a security regression). The two bulk views are left untouched; the f-string bug in `add_volunteer_training_group_record` was already fixed in chunk 3.
- [x] Helper `_render_admin_email` moved to `_common.py` (was a module-level function; now shared across `volunteer_pool_admin` and `volunteer_suspension`).
- [x] Helper `_notify_vols_admin_status_change` moved to `_common.py`.
- [x] Helper `_send_password_set_email` (thin delegate to `password_emails`) moved to `volunteer_edit.py`.
- [x] Initial extraction script missed the `members.forms` import (VolunteerForm etc.); added to `_common.py.__all__` after first test-run failure, suite green.

Commit: `refactor(members): split volunteer_views.py into views/ subpackage` + follow-up comment-polish commit.

### Chunk 6: Split `labs/views.py` + register unregistered models — DONE 2026-06-27

Moderate. URL paths preserved via `views/__init__.py` re-exports; `labs/urls.py` and `toolkit/index/views.py` (which imports `_unread_bulletins_for`) unchanged.

- [x] Split `labs/views.py` (1,556 lines) into `labs/views/` per feature:
  - `_common.py` (verbatim header + `_user_volunteer`, the one cross-module helper), `collectives.py`, `floorplan.py`, `loft.py` (loft zone constants + photos CRUD; floorplan imports `_serialize_loft_items`/`_LOFT_ZONE_*` from here), `donations.py`, `jobs.py`, `area_photos.py`, `bulletins.py` (incl. `_user_can_post_bulletin`, `_active_bulletins_qs`, `_unread_bulletins_for`, `BULLETIN_RATE_LIMIT_PER_HOUR`), `shopping.py`, `lost_found.py`, `exchange.py`, `__init__.py` re-exporting every public view name + the 3 externally-referenced private names.
  - Each submodule carries the original import header verbatim (with `from .models` → `from ..models` etc. since we are now one directory deeper), plus a targeted `from ._common import _user_volunteer` in the two submodules that use it (collectives, shopping). No circular imports; loft constants consumed by floorplan via `from .loft import …`.
  - Source `labs/views.py` deleted; replaced by the package. `git mv` semantics not used (file rewritten across the package split).
- [x] `labs/urls.py` unchanged (still `from . import views`); no URL rewrite needed.
- [x] Register the seven previously-unregistered labs models in `labs/admin.py`: `RoomNote`, `LoftItem`, `BulletinRead`, `ProcurementPledge`, `CollectiveLink`, `AreaPhoto`, `LoftItemPhoto`. Each gets `list_display`/`search_fields`/`raw_id_fields` calibrated to its fields; image-bearing ones mark `uploaded_at` readonly.
- [x] Register the four inductions models in `inductions/admin.py` (replaced the 2-line stub): `InductionSession` (prepopulated slug, date_hierarchy), `InductionSignup`, `InductionRequest`, `InductionsSettings`. `InductionsSettingsAdmin.has_add_permission` returns False once a row exists, to nudge the singleton case.

Verified: `manage.py check` clean; 959 tests pass; black `--line-length 79` clean on all touched files.

Move-first, refactor-after. Commit guidance: `refactor(labs): split views per-feature; register admin for unregistered models`

### Chunk 7: Split `diary/edit_views.py` + models package — DONE 2026-06-27

Moderate. Import paths preserved via `models/__init__.py` and `edit_views/__init__.py` re-exports.

**Do this chunk before chunk 6.** `diary/models.py` (2,432 lines) is the single biggest maintainability liability in the repo — it holds the models with the `__init__`/`refresh_from_db` recursion footgun (see CLAUDE.md "Never use `.only()`"), so making it navigable helps a future human far more than splitting `labs/views.py`. Within this chunk, split `models.py` **first**, then `edit_views.py`.

Migration safety: Django migrations reference models by `app_label.ModelName`, not import path, so moving model classes between files does not break the migration history. The re-export `__init__.py` keeps `from toolkit.diary.models import X` working for the rest of the codebase.

**Boundaries below are provisional.** The real work is the circular FKs between `event` / `showing` / `rota` (they reference each other in both directions). Expect to adjust the split — or co-locate a tightly-coupled cluster — to avoid import cycles. Decide the cycle-break strategy (string FK refs `"diary.Showing"` are already used by Django and sidestep import order) before committing to the file boundaries.

- [x] Split `diary/models.py` (2,432 lines) into `models/` package — DONE 2026-06-27:
  - `models/site_config.py` — `SiteConfiguration` (775 lines), `get_site_config`, `DEFAULT_FILMS_START_BANNER_TEXT`
  - `models/event.py` — `Event`, `EventLink`, `EventTemplateLink`, `EventTermsRevision`, `Film`
  - `models/showing.py` — `Showing`, `RoomBooking`, `Room`, `FutureDateTimeField`
  - `models/rota.py` — `Role`, `EventTemplate`, `EventTemplateRole`, `EventTemplateRoom`, `RotaEntry`
  - `models/misc.py` — `MediaItem`, `EventTag`, `DiaryIdea`, `PrintedProgramme`, `VolunteerEventMark`
  - `models/__init__.py` re-exports everything to preserve `from toolkit.diary.models import X`
  - **Cycle-break strategy used:** all cross-module ForeignKey/M2M `to` and `through` args use string references (`"diary.ModelName"`), resolved by Django's app registry — so submodules can be imported in any order with no Python-level import cycles. The one module-level cross-import is `rota.py` → `from .event import Event` (for `Event.COST_TYPE_CHOICES` / `Event.SOUND_ENGINEER_PAID_BY_CHOICES` used at EventTemplate class-def time); acyclic since `event.py` has no module-level rota import. `showing.py` module-level imports `Role, RotaEntry` from `rota.py` for use in Showing method bodies. `misc.py` module-level imports `Event` for `EventTag.delete()`.
  - No schema change; migrations unaffected (they reference models by `app_label.ModelName`). `docs/SPEC.md` §8 notes the new layout. Suite green at 959; black clean.
- [x] Then split `diary/edit_views.py` (2,879 lines) into `diary/edit_views/` subpackage — DONE 2026-06-27:
  - 12 submodules: `_common`, `diary_overview`, `events`, `showings`, `templates`, `tags_roles_rooms`, `rota`, `misc`, `site_config`, `film`, `reports`, `__init__`.
  - Each submodule carries the original import header verbatim so every name a view uses is available locally (no per-view import surgery, lowest risk).
  - Helpers were traced for cross-module use: only `_get_omdb_api_key` and `_film_json` are referenced from more than one feature area (by `EditEventView` in `events` AND by `omdb_search`/`link_film` in `film`), so those two live in `_common`. Every other `_`-helper (`_safe_json`, `_return_to_editindex`, `_create_room_booking`, `_template_data`, `_rooms_json`, `_get_oneshot_roles_for_showing`, `_parse_oneshot_roles`, `_is_light_colour`, `_export_template_json`, `_build_cert_lookup_url`, `_post_int_or_none`) is local to exactly one submodule and stays there.
  - `events.py` co-locates the tightly-coupled EditEventView with the film-display helpers (`_build_cert_lookup_url`, `_safe_json`) it uses; it imports `_get_omdb_api_key`/`_film_json` from `_common`.
  - The package `__init__.py` re-exports all 53 top-level names (views, classes, and the `_`-private helpers) so `urls.py`'s `from toolkit.diary.edit_views import (...)` and the one test importing `_export_template_json` keep working unchanged. `edit_views.py` is now a package, not a shim.
  - Decorator handling: the slicer walks each `def`/`class` upward to capture preceding `@decorator` lines so no view loses its `@write_required` / `@permission_required` / `@require_POST` / `@feature_required` guard.
  - Suite green at 959; black --line-length 79 clean.
- [x] Move `_safe_json` duplicate (`public_views.py:9` + `edit_views.py:64` → `edit_views/events.py`) into `diary/daterange.py` (the existing shared module) — DONE 2026-06-27:
  - Promoted to a public `safe_json(data)` in `daterange.py` (with the `_JSON_SCRIPT_ESCAPES` table) since it is now genuinely cross-module.
  - `public_views.py` and `edit_views/events.py` both drop their local copies and import `safe_json` from `daterange`; their two call sites use `mark_safe(safe_json(...))`. The now-unused `import json` was removed from `public_views.py` (its only other use was the local docstring/comment).
  - `edit_views/__init__.py` drops the `_safe_json` re-export (no external importer used it).
  - Suite green at 959; black clean.

Move-first. All three chunk-7 items (models split, edit-views split, `_safe_json` dedup) are now committed. Chunk 7 is **DONE**.

### Chunk 8: SiteConfiguration auto-form — DONE 2026-06-27

Moderate-high. Closes the 4-place sync tax.

**Commit A (cheap guardrail):**
- [x] A parity test (`SiteConfigurationConsistencyTests` in `toolkit/diary/tests/test_site_config.py:258`) already exists from earlier work: `test_form_fields_match_model_fields` and `test_view_field_groups_match_form_fields`. These assert that adding a SiteConfiguration field without also listing it on the form (and in the view's grouped/permission renderings) fails the suite.

**Commit B (the auto-derivation):**
- [x] Single source of truth for field grouping is now `SITE_CONFIG_FIELD_GROUPS` in `toolkit/diary/models/site_config.py` — an insertion-ordered dict (Python 3.7+ dicts preserve insertion order) mapping section label → list of field names in display order. The `perm_*` fields are deliberately NOT in this dict: the edit view renders them via the separate `permission_rows` table (with fixed interleaved rows), and adding them to grouped fields would double-render them.
- [x] `SiteConfigurationForm.Meta` now auto-derives its field set from the model `_meta` via `exclude = ("id",)` instead of an 80-line explicit `fields` tuple. Adding a new model field automatically appears on the form.
- [x] `edit_site_configuration` view (`toolkit/diary/edit_views/site_config.py`) reads `field_groups = list(SITE_CONFIG_FIELD_GROUPS.items())` instead of an inline 150-line list.
- [x] Parity test updated to inspect `SiteConfigurationForm.base_fields` (the resolved post-Meta set) rather than `Meta.fields`, which is None now that `Meta` uses `exclude`.

Verified: `manage.py check` clean, 959 tests pass, black `--line-length 79` clean.

Commit guidance: `test(diary): assert SiteConfiguration form/model field parity` (A — already done), `refactor(diary): auto-derive SiteConfiguration form fields from model metadata` (B). Bundled into one commit since A predates the pass.

### Chunk 9: Reconcile feature-flag systems — DONE 2026-06-27

Low-moderate (rescoped). Document-and-comment, don't migrate-everything. The original "decide per-field for every flag" framing is open-ended with no clean stopping point — the opposite of the rest of this plan. Narrow to the cheap, high-value half; defer actual DB-first migration of individual flags unless one is actively causing confusion.

In scope:
- [x] Precedence rule written into the `SiteConfiguration` docstring: "the DB row is the source of truth for every field on this model; settings.py values seed the row via the initial data migration and are not re-read at runtime for fields on this model." Plus a pointer to the settings-only flags.
- [x] One-line comments at each settings-only flag reader marking it explicitly settings-only:
  - `TAGS_WITHOUT_TERMS`: `toolkit/diary/models/misc.py:101`, `toolkit/diary/forms.py:614`
  - `EDIT_INDEX_DEFAULT_DAYS_AHEAD`: `toolkit/diary/edit_prefs.py:9`
  - `MULTIROOM_ENABLED`: `toolkit/diary/calendar_links.py:57`, `toolkit/diary/context_processors.py:31`, `toolkit/diary/edit_views/diary_overview.py` (module-level comment near module logger — used at 5 sites in this file)
  - Bonus while reading `context_processors.py`: `MEMBERSHIP_EXPIRY_ENABLED` is also settings-only (no SiteConfiguration counterpart) — comment marks both together.
- [x] Removed the dead/misleading claim in the `SiteConfiguration` docstring that "settings.py values are only used to seed the row in the initial data migration" — replaced with the precedence rule above that makes the settings-only flags explicit.

Out of scope (defer unless a specific flag is causing live confusion):
- [ ] ~~Make `omdb_api_key`, `eventlink_extra_allowed_domains`, `programme_*` fields consistently DB-first across all readers~~ — only worth the churn+test cost per flag if the inconsistency is actually biting. `omdb_api_key` already has a DB-first reader (`_get_omdb_api_key`); leave the rest unless asked.

Verified: `manage.py check` clean, 959 tests pass, black `--line-length 79` clean on all touched files (bonus: also reformatted three pre-existing long-line files in the same directories).

### Chunk 10: Squash migrations — PENDING

High on active deploys; **safe here — verified 2026-06-27**: the only two environments (homeserver + local dev) are both regularly wiped and only ever hold seed data; no production DB lives on a codebase newer than the pre-`sns_2026_overhaul` baseline. No `--fake` reconciliation step needed on any deploy. Squash in stable chunks, NOT big-bang.

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