# Seed Data Refactor - Progress Summary

**Date:** 2026-03-26
**Status:** In progress - seed_dev_data.py partially fixed, performance issues identified

---

## Current State (End of Session)

### What Was Fixed in seed_dev_data.py

The file had multiple serious bugs introduced during refactoring (likely by AI models). Fixed issues include:

1. **Duplicate Command class** - File had two complete copies of the Command class; removed duplicate

2. **Syntax errors:**
   - Line 220: `" ".join()` corrupted to `".join()`
   - Line 198: Missing closing parenthesis on `min()` call
   - Multiple indentation issues throughout (200+ lines with wrong indentation)
   - Line 399: `)` missing on `set()` call for `unfilled_indices`

3. **Variable name errors:**
   - `vol_list` undefined in multiple places - changed to `list(volunteer_objects.values())` or passed as parameter
   - `TAGS` is a list of dicts from TOML, not strings - fixed to extract `tag_data["name"]`
   - `volunteer_objects` undefined in `_seed_one_recurring_showing` and `_seed_film_showing` - fixed to use `vol_list` parameter

4. **Type conversion issues:**
   - Duration (int minutes) to datetime.time objects needed conversion
   - `num_expanded = len(roles_list) * fill_rate` produced float, needed `int()` for `range()`
   - `date.replace(hour=...)` called on date object (not datetime) - fixed to use `datetime.datetime.combine()`
   - Naive datetime needed `timezone.make_aware()` for timezone-aware field

5. **Database field errors:**
   - `rota_notes` field doesn't exist on Event model - removed
   - Event duration field uses TimeField, not integer - fixed to use `datetime.time()`

6. **Function call issues:**
   - `_seed_one_recurring_showing()` missing `anchor` parameter - added
   - `_seed_recurring_showing()` had wrong parameter for `room` - fixed to use Room object from `rooms_dict`
   - `_seed_film_showing()` had extra positional args (removed stray `30` and `rooms_dict`)
   - Film loops iterating over wrong thing (films instead of dates) - fixed to `for i, d in enumerate(sundays)`

7. **Date collection for recurring events:**
   - Original code collected past dates (8 weeks ago) which would fail Showing model validation
   - Fixed to only include dates from today onwards

### Remaining Performance Issues (NOT YET FIXED)

**CRITICAL:** The command still runs very slowly. Root causes identified:

1. **Nested loop bug (lines 841-906)** - Rota entry creation logic is *inside* the `for role_name in film_roles:` loop, creating 5×5=25 rota entries per showing instead of 5. This multiplies DB operations significantly.

2. **Image downloads** - Each film showing calls `_make_event_image()` which tries to download from external URLs with 10-second timeout. For 24 Sundays × 24 films cycling + 24 Thursdays × 29 films = many slow downloads.

3. **Missing constants** - `SAFER_SPACES_BODY`, `WHO_ARE_WE_BODY`, `HOW_TO_VOLUNTEER_BODY`, `SAFEGUARDING_BODY`, `FURTHER_RESOURCES_BODY`, `PRIVACY_POLICY_BODY` are undefined. Will cause NameError when `_seed_cms_pages()` is called.

4. **Missing imports** - `Image` from PIL/Pillow and `urllib.request` are used in `_make_event_image()` but not imported. `ContentFile` is used but not imported.

### Files That Exist and Work

- `seed_data/__init__.py` - loads TOML files correctly
- `seed_data/roles.toml` - 42 roles with badge flags
- `seed_data/rooms.toml` - 9 rooms with colours
- `seed_data/tags.toml` - 16 tags with colours
- `seed_data/volunteers.toml` - 20 fictional volunteers  
- `seed_data/templates.toml` - 13 event templates
- `seed_data/films.toml` - 24 Sunday films, 29 Thursday films with image_urls

---

## Immediate Next Steps

### 1. Fix Performance Issues (Priority 1)

**File:** `toolkit/util/management/commands/seed_dev_data.py`

a) **Fix nested loop bug** (lines ~841-906):
```python
# WRONG - creates rota entries inside the roles loop:
for role_name in film_roles:
    try:
        role = Role.objects.get(name=role_name)
    except Role.DoesNotExist:
        continue
    # Creates 5 rota entries PER role (25 total instead of 5!)
    _, re_created = RotaEntry.objects.get_or_create(showing=showing, role=Role.objects.get(name="Keyholder"), ...)
    _, re_created = RotaEntry.objects.get_or_create(showing=showing, role=Role.objects.get(name="Projectionist - DCP"), ...)
    # etc.

# CORRECT - create rota entries per role:
for role_name, required, default_name in film_roles:
    try:
        role = Role.objects.get(name=role_name)
    except Role.DoesNotExist:
        continue
    vol_name = default_name or next(vol_iter).member.name if vol_iter else ""
    _, created = RotaEntry.objects.get_or_create(showing=showing, role=role, defaults={"required": required, "name": vol_name})
```

b) **Skip image downloads** - Modify `_make_event_image()` to return None early (skip all image creation) OR generate local placeholder without network calls

c) **Add missing imports** or remove the code that uses them:
```python
# Either add at top:
from django.core.files.base import ContentFile
# Or remove _make_event_image calls and the method
```

d) **Fix _seed_cms_pages()** - Either define the missing content constants or stub out the method

### 2. Verify Performance

After fixes, run:
```bash
time docker compose exec toolkit /venv/bin/python3 manage.py seed_dev_data --wipe
```
Should complete in under 30 seconds.

### 3. Clean Up Code Quality

- Remove duplicate/unused methods (`_nth_weekday_of_month`, `_last_weekday_of_month` at bottom of file)
- There's still a second copy of `_seed_bulk_volunteers` and other methods at the end of the file (remnants of the duplicate Command class)
- Fix the indentation issues that remain (editor shows many warnings)

---

## Original Plan (Still Valid)

### TOML Files (Already Complete)
- roles.toml ✓
- rooms.toml ✓
- tags.toml ✓
- volunteers.toml ✓
- templates.toml ✓
- films.toml ✓
- recurring.toml ✓
- __init__.py ✓

### seed_dev_data.py (Needs More Work)
- Fix performance issues above
- Remove duplicate code at end of file
- Ensure all methods work correctly

### Tests
After seed command works fast and clean:
```bash
./runtests
```

---

## Key Questions for Next Session

1. Should we skip image generation entirely for dev seeding? (Recommended: yes, saves ~10s per film)
2. Should CMS pages be seeded? If so, what content? (Need to define `SAFER_SPACES_BODY` etc.)

---

*Progress updated 2026-03-26 after debugging session*