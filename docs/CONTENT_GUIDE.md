# Content Guide — Star and Shadow Toolkit

**Audience:** volunteers who need to update text on the website or toolkit, but aren't developers.

This guide maps every editable area of the site to the tool you use to change it.

---

## The two kinds of page

The Star and Shadow website and volunteer toolkit have two fundamentally different kinds of page:

**Wagtail CMS pages** are written and published through a visual editor — no code required. They live at `/toolkit/cms/`. These are typically narrative pages: About, Get Involved, and so on.

**Toolkit-managed pages** are driven by database records that volunteers edit through the toolkit's own forms. The programme, rota, events, collectives, donations wishlist, and bulletins all work this way.

A small number of pages are **code-only** — their text is hardcoded in templates and needs a developer to change. We try to keep this category small.

---

## Content map

### Public website

| Page | URL | How to edit | Who can edit |
|---|---|---|---|
| Homepage / programme | `/` | Automatic — pulled from confirmed events | Programmers |
| Event detail | `/id/<n>/` | Event hub in the toolkit | Programmers |
| About | `/about/` | Wagtail CMS (`/toolkit/cms/`) | Any logged-in editor |
| Get Involved | `/get-involved/` | Wagtail CMS (`/toolkit/cms/`) | Any logged-in editor |
| Important Info | `/important-info/` | Wagtail CMS (`/toolkit/cms/`) | Any logged-in editor |
| Safer Spaces | `/safer-spaces/` | Wagtail CMS (`/toolkit/cms/`) | Any logged-in editor |
| Collectives directory | `/labs/collectives/public/` | Two places: intro text → Site Settings; individual collective cards → `/labs/collectives/<slug>/edit/` | Intro: Panopticon; Cards: any volunteer |
| Donations wishlist | `/labs/donations/` | `/labs/donations/manage/` | Any logged-in volunteer |

### Volunteer toolkit

| Area | URL | How to edit |
|---|---|---|
| Diary / programme edit | `/diary/edit/` | Standard toolkit forms |
| Rota | `/diary/edit/rota/` | Standard toolkit forms |
| Collectives (internal view) | `/labs/collectives/` | `/labs/collectives/<slug>/edit/` |
| Bulletins | `/labs/bulletins/` | Post a bulletin on that page |
| Jobs board | `/labs/jobs/` | Add/edit on that page |
| Toolkit index links | `/toolkit/index/` (see Meta-programming section) | Index link admin |
| Site settings (thresholds, banner, intro texts) | `/diary/edit/site-config/` | Panopticon only |

---

## The Wagtail CMS

Wagtail is the content management system for narrative pages — the ones with long-form text, images, and sections.

**To access it:** Log in to the toolkit, then go to `/toolkit/cms/`.

**Pages vs snippets:** Most editable content lives in Pages (the tree on the left). There are no snippets in current use.

**Adding a new page:** Navigate to where it should live in the page tree, click the (...) menu on the parent, and choose "Add child page". Choose "Basic Article Page" for standard content.

**Publishing:** Pages have a draft/published state. Save as draft to preview; hit "Publish" when ready. Un-publishing a page makes it return a 404 — it doesn't redirect anywhere, so avoid un-publishing pages that might be linked from elsewhere.

**The page tree and URL structure:** A page's URL is determined by its slug and position in the tree. Moving a page in the tree changes its URL. Wagtail creates redirects automatically when pages are moved, but this is not reliable for all cases.

**Wagtail users:** Anyone with a Django user account can be given Wagtail editor access through `/toolkit/cms/`. This is separate from Programmer and Panopticon tiers.

---

## Site Settings

A small number of configuration values that affect public-facing pages can be edited at `/diary/edit/site-config/` (Panopticon only). These include:

- The intro text on the public Collectives page
- The intro text on the Donations wishlist page
- The site-wide announcement banner
- Bulletin posting permissions and expiry defaults
- Various display thresholds

The site settings form is the right place to put short, plain-text editorial copy that needs updating occasionally but shouldn't require a full CMS page.

---

## Hardcoded content (requires a developer)

The following text is currently in templates and cannot be edited through any UI:

| Content | Template | Notes |
|---|---|---|
| Induction notice on Collectives page | `star_and_shadow_templates/collectives_public.html` | The surrounding notice ("New to the Star and Shadow?") is fixed; only the main intro paragraph is configurable via Site Settings |
| Volunteer rota notice text | `star_and_shadow_templates/view_showing_index.html` | The "you're logged in as a volunteer" message |
| Mailout email body structure | `star_and_shadow_templates/mailout_body.html` | Plain HTML template; text is pulled from event records |

If any of these need changing, raise it with a developer or open a task in the toolkit.

---

## Tips

**When in doubt:** if a page has an "Edit" button in the toolkit, use that. If it's a narrative page (About, Get Involved etc.), try the Wagtail CMS first.

**The collectives page** has two layers: the intro text is in Site Settings, but each collective card is edited through the toolkit (`/labs/collectives/<slug>/edit/`). Both layers exist because the intro is a single piece of text owned by whoever's coordinating comms, while each collective owns its own card.

**Don't edit templates directly** on the production server — changes will be overwritten on the next deploy. All persistent content changes should go through one of the editing mechanisms above.
