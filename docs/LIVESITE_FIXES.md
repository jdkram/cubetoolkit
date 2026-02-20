# Quick-win fixes for the live (legacy) site

This file documents low-effort, high-impact bugs and friction points found during the master branch port that can be quickly backported to the current live S+S Django 2.2 codebase.

---

## 1. Rota role count limitation (8 slots max)

**Problem:** The rota can only accommodate up to 8 people per role. For events with many participants (e.g. participant 1–8 + trainee 1–8), this forces workarounds: adding multiple roles with near-identical names or using rota notes to clarify that "Trainee" and "Participant" slots refer to the same group.

**Root cause:** `MAX_COUNT_PER_ROLE = 8` hard-codes the limit in settings. This is enforced:
- In the form validator ([toolkit/diary/forms.py](toolkit/diary/forms.py#L276), rota count IntegerField with `max_value` kwarg)
- In the jQuery spinner widget configuration ([toolkit/diary/edit_views.py](toolkit/diary/edit_views.py#L579), passed to template as `max_role_assignment_count`)

**Source code locations in `master`:**
- Setting definition: [toolkit/settings_common.py](toolkit/settings_common.py#L97)
- Form enforcement: [toolkit/diary/forms.py](toolkit/diary/forms.py#L276)
- Template: [toolkit/diary/templates/edit_rota.html](toolkit/diary/templates/edit_rota.html) (sets jQuery spinner `max` kwarg)

**Fix:** Increase `MAX_COUNT_PER_ROLE` in [toolkit/settings_ss.py](toolkit/settings_ss.py) (or the live equivalent) from `8` to `16` (or higher, depending on typical rota load):

```python
# toolkit/settings_ss.py (or equivalent on live site)
MAX_COUNT_PER_ROLE = 16
```

**Effort:** ~5 minutes (one-line change, no migration needed)

**Impact:** High — eliminates confusing rota notes and allows cleaner role naming

---

## 2. Rota text fields show raw HTML entities

**Problem:** When editing rota entry names via the inline edit widget (jeditable), apostrophes and quotes appear as raw HTML entities (`&apos;`, `&quot;`) in the form. Users see `don&apos;t` instead of `don't`, making the form harder to read and appear broken.

**Root cause:** In [toolkit/diary/edit_views.py](toolkit/diary/edit_views.py#L1141), the `edit_showing_rota_entry()` view applies Django's `escape()` function to the submitted name before returning it. The response payload is marked as `text/plain`, so jeditable inserts the escaped response as literal text instead of decoding HTML entities.

**Source code location in `master`:**
```python
# toolkit/diary/edit_views.py line ~1138–1145
rota_entry.name = name
rota_entry.save()

response = escape(name)  # ← This line escapes the output

# Returned text is displayed as the rota entry:
return HttpResponse(response, content_type="text/plain")
```

**Fix:** Remove the `escape()` call and return the unescaped name directly:

```python
# toolkit/diary/edit_views.py
rota_entry.name = name
rota_entry.save()

# Return unescaped text (no need to re-escape — it's stored as plain text)
return HttpResponse(name, content_type="text/plain")
```

**Alternatively:** Keep the escaping but change the response content type and configure jeditable to decode HTML:
```python
return HttpResponse(escape(name), content_type="text/html")
```

Ensure the jeditable initialization doesn't force `type: 'text'` (allow HTML parsing).

**Related:** The rota notes endpoint at [toolkit/diary/edit_views.py](toolkit/diary/edit_views.py#L1153) returns rota notes without escaping, so rota notes should display correctly.

**Effort:** ~10–15 minutes (change 1 line in views.py, test rota name edit)

**Impact:** Medium — improves form usability and makes the interface look less broken

---

## Implementation notes

**On the `master` branch:**
- The rota role limit setting (`MAX_COUNT_PER_ROLE`) is defined in [toolkit/settings_common.py](toolkit/settings_common.py#L97) with a baseline of `8`.
- The S+S-specific settings file [toolkit/settings_ss.py](toolkit/settings_ss.py) already exists and can override this setting.
- To apply fix #1 on `master`, add `MAX_COUNT_PER_ROLE = 16` to [toolkit/settings_ss.py](toolkit/settings_ss.py).
- To apply fix #2 on `master`, edit [toolkit/diary/edit_views.py](toolkit/diary/edit_views.py#L1141) in the `edit_showing_rota_entry()` function.

**For the live (legacy) site:**
- These fixes are venue-specific to S+S (defined in the live site's S+S settings layer).
- No database migrations are needed for either fix.
- Both are low-risk, backwards-compatible changes.
- Test the rota edit form after applying either change to ensure no unintended side effects.

