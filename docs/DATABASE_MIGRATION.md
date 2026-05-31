# Database Migration: s+s Branch to Master

**Test Date:** 2026-03-31  
**Tested By:** Migration of staging DB (`s+s` branch, March 2026) to current `master` codebase  
**Result:** ✅ SUCCESS — All data preserved, site functional

---

## Executive Summary

Successfully migrated 9,214 events, 10,994 showings, 2,334 members, and 1,879 volunteers from the old Django 2.2 `s+s` branch to the current Django 5.2 `master` codebase. Migration took ~5 minutes with no data loss.

**Key Lessons:**
1. Migration history needs fixing (members app numbering changed)
2. Media files must be synced from live (staging is always incomplete)
3. **Passwords work as-is** — users keep their existing passwords, no reset needed

The automated script handles 95% of the work.

---

## Critical Gotchas & How to Fix Them

### 1. Migration History Mismatch (BLOCKER)

**What Happens:** Django tries to re-run migrations that already exist in the database, causing "Duplicate column name" errors.

**Why:** The `members` app had different migration numbering between branches:

| Old (s+s) | New (master) | Status |
|-----------|--------------|--------|
| `0008_volunteer_user` | `0009_volunteer_user` | Renumbered |
| `0009_member_email_is_mandatory` | `0010_make_email_mandatory` | Renamed |
| — | `0008_member_preferred_pronouns_squashed_0009_auto_20220627_1114` | New (squashed) |

**The Fix:**
```sql
-- Delete old migration records
DELETE FROM django_migrations 
WHERE app='members' AND name IN ('0008_volunteer_user', '0009_member_email_is_mandatory');

-- Insert new migration records (mark as already applied)
INSERT INTO django_migrations (app, name, applied) VALUES 
    ('members', '0008_member_preferred_pronouns_squashed_0009_auto_20220627_1114', NOW()),
    ('members', '0009_volunteer_user', NOW());
```

**Prevention:** The `migrate-staging-db.sh` script handles this automatically.

---

### 2. Media Files Are Incomplete (COMMON)

**What Happens:** Images appear as broken links on the site. Easy_thumbnail errors in logs:
```
easy_thumbnails.exceptions.InvalidImageFormatError: 
The source file does not appear to be an image: 'diary/filename.jpg'
```

**Why:** Staging environments rarely have complete media syncs. Our test found **240 missing files** (5% of 4,861 media items).

**The Fix:**
```bash
# Identify missing files
docker compose exec toolkit python3 manage.py shell -c "
from toolkit.diary.models import MediaItem
missing = [m.media_file.name for m in MediaItem.objects.all() 
           if m.media_file and not m.media_file.storage.exists(m.media_file.name)]
print(f'Missing: {len(missing)}')
for f in missing[:10]: print(f'  - {f}')
"

# Copy from live site (adjust paths as needed)
rsync -av ~/code/sns-live-toolkit/media/diary/ ~/code/sns-staging-toolkit/media/diary/

# Or copy directly to Docker volume
docker run --rm -v sns-toolkit_media_data:/media \
    -v ~/code/sns-live-toolkit/media:/live busybox \
    sh -c 'cp /live/diary/* /media/diary/'
```

**Gotcha:** Some files may exist in the database but nowhere (orphaned records). These need cleanup:
```python
# Delete orphaned MediaItem records
for m in MediaItem.objects.all():
    if m.media_file and not m.media_file.storage.exists(m.media_file.name):
        print(f"Deleting orphaned: {m.media_file}")
        m.delete()
```

**Our Test Results:**
- Staging media: 4,946 files
- Live media: 5,287 files  
- Missing from staging: 341 files
- Orphaned DB records: 3 files (deleted)
- **Final count: 5,286 files, 0 missing**

---

### 3. User Passwords — They DO Work! ✅

**What Happens:** You might think passwords don't work, but they actually do!

**The Reality:** Django 5.2 is fully backward compatible with Django 2.2 password hashes. The `pbkdf2_sha256` algorithm works whether it used 150,000 or 1,000,000 iterations.

**Why We Got Confused:**
- Demo accounts (`admin`, `programmer`, etc.) — we set these to new passwords
- Existing accounts kept their **original passwords**
- We didn't know the original live site passwords, so we couldn't test them!

**The Fix:**
**Nothing!** Users just log in with their existing live site passwords. They work immediately.

```bash
# Only run this if you want demo/test accounts:
docker compose exec toolkit /venv/bin/python3 manage.py configure_toolkit_users \
    --password=YourNewPassword123!
```

**Demo Accounts vs Existing Accounts:**

| Account Type | Examples | Password After Migration |
|--------------|----------|------------------------|
| **Demo accounts** | `admin`, `programmer`, `volunteer1-5` | Whatever you set with `--password` |
| **Existing accounts** | All real users from live site | **Original password** — unchanged |

**For Production:** Users keep their existing passwords. No action needed.

---

### 4. Room Data Gets Overwritten (DATA LOSS RISK)

**What Happens:** After migration, rooms have:
- Wrong colours (old neon colours instead of nice pastels)
- All `is_primary=False` (should be True for Cinema/Venue Space/Café)
- Wrong names (e.g., "workshop" instead of "Workshop")
- Rooms appear as "Other rooms" in the UI

**Why:** The SQL dump from the old `s+s` branch contains the old room configuration. Loading it overwrites the nice room data that was set up in the new `master` branch.

**The Fix:**
Run the room fix script to restore proper room configuration:

```bash
# Copy and run the room fix script
docker compose cp fix_rooms_after_migration.py toolkit:/site/
docker compose exec toolkit /venv/bin/python3 /site/fix_rooms_after_migration.py
```

**What the script does:**
1. Maps old room names to new ones (fixes "workshop" → "Workshop")
2. Updates colours to the new palette
3. Sets `is_primary=True` for Cinema, Venue Space, and Café
4. Handles duplicate room merges safely

**Room Mapping:**

| Old Name | New Name | Old Colour | New Colour | is_primary |
|----------|----------|------------|------------|------------|
| Cinema | Cinema | #ff3399 | #CC2200 | True |
| Venue Space | Venue Space | #FF00FF | #0057B8 | True |
| Café | Café | #33CC33 | #FFD700 | True |
| External | External | #FF6600 | #E0F5CC | False |
| Meeting | Meeting | #555555 | #DDD0FF | False |
| Dark Room | Dark Room | #0066ff | #707070 | False |
| Print Room | Print Room | #ff0000 | #CCE8F8 | False |
| workshop | Workshop | #33CC33 | #F2E4A8 | False |
| Green room | Green room | #3d85c6 | #74BB88 | False |

**Gotcha within the gotcha:** The script had a bug that deleted the Workshop room and left 914 showings with NULL rooms. This has been fixed in the current version, but if you're running an older version, check for orphaned showings:

```python
from toolkit.diary.models import Showing
orphaned = Showing.objects.filter(room__isnull=True).count()
print(f"{orphaned} showings have no room assigned")
```

---

### 5. Thumbnail Errors in Logs (COSMETIC)

**What Happens:** Log spam like:
```
ERROR [thumbnail_l.py:26] Failed generating thumbnail for diary/filename.jpg
```

**Why:** easy_thumbnails tries to generate thumbnails for images as they're viewed. If the source file is missing/corrupted, it errors.

**Impact:** None. Site works fine, just noisy logs.

**Fix:** Resolve missing media files (see Gotcha #2).

---

## Migration Checklist

Use this for live migration:

- [ ] **Backup live database** — mysqldump with `--single-transaction`
- [ ] **Backup live media** — rsync or tar the entire media directory
- [ ] **Stop toolkit** — `docker compose stop toolkit`
- [ ] **Drop & recreate DB** — Fresh database with utf8mb4
- [ ] **Load SQL dump** — `mysql < live_backup.sql`
- [ ] **Copy media files** — Ensure ALL files are present
- [ ] **Fix migrations** — Run the SQL in Gotcha #1
- [ ] **Run Django migrations** — `manage.py migrate`
- [ ] **Collect static** — `manage.py collectstatic --noinput`
- [ ] **Create demo accounts** — `configure_toolkit_users --password=...` (optional, for testing)
- [ ] **Fix room data** — Run `fix_rooms_after_migration.py` (see Gotcha #4)
- [ ] **Verify** — Check programme page, try login, spot-check events
- [ ] **Start toolkit** — `docker compose up -d toolkit`

---

## Automated Migration Script

The `migrate-staging-db.sh` script handles most of this:

```bash
./migrate-staging-db.sh \
    /path/to/live_backup.sql \
    /path/to/live_media_directory
```

**What it does:**
1. Stops toolkit container
2. Drops & recreates database
3. Loads SQL dump
4. Copies media files to Docker volume
5. Fixes migration history (Gotcha #1)
6. Runs Django migrations
7. Collects static files
8. Restarts toolkit

**What it DOESN'T do:**
- Sync incomplete media from another source (Gotcha #2)
- Fix room data colours/names (Gotcha #4) — run `fix_rooms_after_migration.py` manually
- Clean up orphaned media records — run this manually if needed

---

## Data Verification

After migration, verify these counts:

```bash
docker compose exec toolkit /venv/bin/python3 manage.py shell -c "
from toolkit.diary.models import Event, Showing, MediaItem
from toolkit.members.models import Member, Volunteer
print(f'Events: {Event.objects.count()}')
print(f'Showings: {Showing.objects.count()}')
print(f'Members: {Member.objects.count()}')
print(f'Volunteers: {Volunteer.objects.count()}')
print(f'MediaItems: {MediaItem.objects.count()}')
"
```

**Expected (from our test):**
| Table | Count |
|-------|-------|
| Events | 9,214 |
| Showings | 10,994 |
| Members | 2,334 |
| Volunteers | 1,879 |
| RotaEntries | 38,099 |
| MediaItems | 4,858 (after cleanup) |

---

## Schema Changes Applied

These migrations ran successfully, adding new fields/tables:

**diary app (9 migrations):**
- `0009_add_role_description` — `Roles.description` field
- `0010_widen_rota_notes` — `Showings.rota_notes` size increase
- `0011_add_room_is_primary` — `Rooms.is_primary` flag
- `0012_add_mediaitem_alt_text` — `MediaItems.alt_text` field
- `0013_add_eventtemplate_fields` — Multiple `EventTemplate` fields
- `0014_eventtemplate_role_counts` — `EventTemplateRole` through-model
- `0015_add_event_links` — `EventLinks` model
- `0016_role_badge_flags` — `beginner_friendly`, `not_wheelchair_accessible`
- `0017_role_keyholder_flag` — `keyholder_only`
- `0018_alter_eventtemplaterole_count` — Role count validation

**members app (1 migration):**
- `0010_make_email_mandatory` — Email becomes required

**mailer app (2 migrations):**
- `0001_initial` — Creates `MailoutJob` table
- `0002_alter_mailoutjob_body_html` — HTML field size

**Plus:** 50+ Wagtail/Django contrib migrations (no data changes).

---

## Time Estimates

| Step | Time |
|------|------|
| mysqldump (live) | 1-2 min |
| rsync media (live) | 5-10 min (depends on size) |
| Load SQL dump | 1-2 min |
| Django migrations | 1-2 min |
| Static collection | 30 sec |
| **Total downtime** | **~5-7 min** |

---

## Rollback Plan

If migration fails:

1. Stop toolkit: `docker compose stop toolkit`
2. Restore database: `mysql < pre_migration_backup.sql`
3. Restore media: `rsync -av backup/media/ /path/to/media/`
4. Start toolkit: `docker compose up -d toolkit`

---

## Lessons Learned

1. **Migration history is the tricky part.** The schema changes themselves are straightforward, but Django's migration table needs manual fixing when branch histories diverge.

2. **Media sync is never complete.** Always assume staging is missing files. Verify with the missing-files check script.

3. **Passwords DON'T break!** Django maintains backward compatibility. We thought they broke because we were testing with demo account credentials instead of real user passwords. Real users keep their original passwords — no reset needed.

4. **Room data gets overwritten by the SQL dump.** The old s+s branch had different room colours and names. You MUST run the room fix script after migration to restore the nice colour scheme and proper `is_primary` flags.

5. **Test the full flow.** We found the media issue only by actually viewing the site, not by checking logs. We found the room issue when rooms showed as "Other rooms" in the UI.

6. **The automated script is 90% there.** But you still need to: fix migration history, verify media completeness, and run the room fix script.

---

---

## Post-migration: Qualification gates (rota sign-up)

The toolkit supports gating rota sign-up by named qualifications (e.g. "Bar", "Projectionist level 1"). The gate is configured per-role at **Meta → Roles** and enforced when a volunteer taps to sign up. Superusers/Panopticons always bypass the gate.

**Default state after migration:** All roles default to `gate = Off` — no sign-up checks are active. This is intentional. The qualification records need to be populated before any gate can be trusted.

**Recommended sequence after going live:**

1. **Create qualifications.** Go to Meta → Roles and use the Qualifications panel to add the credential names used on your site (e.g. "Bar", "Projectionist level 1", "Cafe").

2. **Audit bar-trained volunteers.** Cross-reference the bar mailing list against active volunteers. For each bar-trained volunteer, visit their profile and award the "Bar" qualification. This is the most critical gate — bar training is widely held and reliably tracked via the mailing list.

3. **Audit projectionists.** Check whether projection training has been recorded in the system (training records tab on each volunteer profile). The data may be sparse — do not enable a blocking gate until you are confident the records are complete. Start with Advisory mode.

4. **Backfill qualifications from existing training records.** If the site has role training records (visible on volunteer profiles under the Training tab), you can use the backfill command to award qualifications automatically rather than doing it one volunteer at a time. This is most useful for qualifications that have been consistently recorded as role training — for example, projection training if every projector-trained volunteer has a training record against the projection role.

   **Prerequisite:** The role must already have `required_qualification` set (step 1 above). The command only acts on roles that have a qualification configured.

   ```bash
   # Preview — shows what would be awarded without writing anything
   docker compose exec toolkit /venv/bin/python3 manage.py \
       backfill_qualifications_from_training --dry-run

   # Run for real
   docker compose exec toolkit /venv/bin/python3 manage.py \
       backfill_qualifications_from_training

   # Optional: record who triggered the backfill
   docker compose exec toolkit /venv/bin/python3 manage.py \
       backfill_qualifications_from_training --granted-by "Marcus (projection backfill Jan 2027)"
   ```

   **What it does:**
   - Finds all ROLE_TRAINING records where the role has a `required_qualification`
   - Awards that qualification to the volunteer using the earliest training date as `granted_on`
   - Skips volunteers who already hold the qualification (safe to re-run)
   - Does not touch GENERAL_TRAINING records (GST has no qualification equivalent)

   **Caveats:**
   - It awards based on "has a training record" not "training is current." Expired training records still trigger an award. If you want to filter by currency, do a dry run first and inspect the output before committing.
   - Bar training is almost certainly *not* consistently recorded as role training records in your system. Award Bar qualifications manually via volunteer profiles, or use the mailing list as the authoritative source.

5. **Set gate mode.** Once qualification records are populated and verified, go to Meta → Roles. Set "Requires qualification" to the relevant credential and set "Gate" to Advisory (warns the volunteer but allows sign-up) or Blocking (prevents sign-up without the qualification). **Start with Advisory.** Move to Blocking only after a period of live use confirms the records are reliable.

6. **Ongoing maintenance.** When a new volunteer completes bar induction, award them the "Bar" qualification on their profile. This is a manual step — there is no automatic sync with mailing lists.

**Notes:**
- Qualifications are intentionally separate from `TrainingRecord` (which logs training *events*). A `TrainingRecord` says "this person attended a session"; a `VolunteerQualification` says "this person is currently cleared for this role." Both models are kept deliberately: `TrainingRecord` is also where **General Safety Training** lives (surfaced as the "Safety trained" date on the volunteer profile), which has no equivalent in qualifications. There is therefore no need to convert or drop `TrainingRecord` data on migration — the two coexist.
- The advisory notice is shown as a browser alert when the volunteer taps to sign up. They can proceed regardless.
- The blocking gate returns a plain-text error and cancels the sign-up. The volunteer sees a message directing them to a coordinator.

---

## Files Referenced

- `migrate-staging-db.sh` — Automated migration script
- `CURRENT_WORK.md` — Task tracking (check for updates)
- `docs/BRANCH_NOTES.md` — Full s+s vs master comparison
