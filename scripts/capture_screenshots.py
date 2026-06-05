#!/usr/bin/env python3
"""
Screenshot capture automation for the Cube Toolkit.

Captures public and authenticated pages at multiple viewport sizes,
compares against a baseline release, and generates an HTML gallery
with before/after sliders and a "changed only" filter.

Usage:
    uv run --with playwright scripts/capture_screenshots.py \
        --version 2026.06.2 \
        --output screenshots/current/ \
        --baseline screenshots/baseline/2026.06.1

Requires:
    - Docker dev server running on http://localhost:8000
    - Demo data seeded (so pages are not empty)
    - configure_toolkit_users run with a known password
"""

# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"

from __future__ import annotations

import argparse
import base64
import io
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout


BASE_URL = "http://localhost:8000"
DEFAULT_PASSWORD = "password"

VIEWPORTS = [
    # Mobile heights extended so filter bars don't swallow all vertical space.
    {"name": "mobile-narrow", "width": 375, "height": 1100},
    {"name": "mobile", "width": 390, "height": 1200},
    {"name": "tablet", "width": 768, "height": 1024},
    {"name": "desktop", "width": 1280, "height": 800},
    {"name": "wide", "width": 1920, "height": 1080},
]


@dataclass(frozen=True)
class PageDef:
    """A page to capture."""

    path: str
    slug: str
    requires_auth: bool = False
    discover_id: bool = False


# ---------------------------------------------------------------------------
# Page catalog — grouped by the persona that should visit them
# ---------------------------------------------------------------------------

ANONYMOUS_PAGES: list[PageDef] = [
    PageDef("/", "programme-home"),
    PageDef("/labs/collectives/public/", "collectives-public"),
    PageDef("/id/{event_id}/", "event-detail", discover_id=True),
]

VOLUNTEER_PAGES: list[PageDef] = [
    PageDef("/toolkit/", "toolkit-index", requires_auth=True),
    PageDef("/diary/edit/rota/", "rota-edit", requires_auth=True),
    PageDef("/volunteers/directory/", "volunteer-directory", requires_auth=True),
    PageDef("/labs/bulletins/", "labs-bulletins", requires_auth=True),
]

PROGRAMMER_PAGES: list[PageDef] = [
    PageDef("/diary/edit/", "diary-edit-list", requires_auth=True),
    PageDef("/diary/edit/calendar/", "diary-edit-calendar", requires_auth=True),
    PageDef("/labs/jobs/", "labs-jobs", requires_auth=True),
    PageDef("/diary/edit/event/id/{event_id}/", "event-edit-form", requires_auth=True, discover_id=True),
]

PANOPTICON_PAGES: list[PageDef] = [
    PageDef("/members/search/", "members-search", requires_auth=True),
    PageDef("/volunteers/", "volunteers-list", requires_auth=True),
    PageDef("/toolkit/access/", "toolkit-access", requires_auth=True),
    PageDef("/diary/edit/site-config/", "site-config", requires_auth=True),
]

PUBLIC_LABS_PAGES: list[PageDef] = [
    PageDef("/labs/donations/", "labs-donations"),
    PageDef("/labs/exchange/", "labs-exchange"),
]


# ---------------------------------------------------------------------------


class ScreenshotCapture:
    def __init__(
        self,
        base_url: str,
        output_dir: Path,
        baseline_dir: Optional[Path],
        version: str,
        password: str = DEFAULT_PASSWORD,
    ):
        self.base_url = base_url.rstrip("/")
        self.output_dir = output_dir / version
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.baseline_dir = baseline_dir
        self.version = version
        self.password = password
        self.results: list[CaptureResult] = []

    def run(self) -> None:
        with sync_playwright() as p:
            browser = p.chromium.launch()

            # ---- Anonymous -------------------------------------------------
            ctx = browser.new_context()
            page = ctx.new_page()
            event_id = self._discover_event_id(page)
            self._capture_pages(page, "anonymous", ANONYMOUS_PAGES, event_id=event_id)
            ctx.close()

            # ---- Volunteer -------------------------------------------------
            ctx = browser.new_context()
            page = ctx.new_page()
            self._login(page, "volunteer")
            self._capture_pages(page, "volunteer", VOLUNTEER_PAGES)
            ctx.close()

            # ---- Programmer ------------------------------------------------
            ctx = browser.new_context()
            page = ctx.new_page()
            self._login(page, "programmer")
            event_id_prog = self._discover_event_id_from_edit_list(page)
            self._capture_pages(
                page, "programmer", PROGRAMMER_PAGES, event_id=event_id_prog
            )
            ctx.close()

            # ---- Panopticon ------------------------------------------------
            ctx = browser.new_context()
            page = ctx.new_page()
            self._login(page, "admin")
            self._capture_pages(page, "panopticon", PANOPTICON_PAGES)
            ctx.close()

            # ---- Public labs (no auth) -------------------------------------
            ctx = browser.new_context()
            page = ctx.new_page()
            self._capture_pages(page, "anonymous", PUBLIC_LABS_PAGES)
            ctx.close()

            browser.close()

        # Post-processing
        if self.baseline_dir and self.baseline_dir.exists():
            self._generate_diffs()
        self._generate_report()

    # ------------------------------------------------------------------
    # Auth & discovery helpers
    # ------------------------------------------------------------------

    def _login(self, page, username: str) -> None:
        page.goto(urljoin(self.base_url, "/auth/login/"), wait_until="networkidle")
        page.fill("input[name='username']", username)
        page.fill("input[name='password']", self.password)
        page.click("input[type='submit']")
        page.wait_for_load_state("networkidle")
        # Verify we are inside by checking we left the login page
        if "/auth/login" in page.url:
            print(f"  WARNING: login failed for {username}")
        else:
            print(f"  Logged in as {username}")

    def _discover_event_id(self, page) -> str | None:
        """Scrape the programme homepage for the first /id/<n>/ link."""
        page.goto(urljoin(self.base_url, "/"), wait_until="networkidle")
        link = page.locator("a[href^='/id/']").first
        if link.count() == 0:
            return None
        href = link.get_attribute("href")
        # href is like "/id/194/"
        parts = href.strip("/").split("/")
        return parts[-1] if parts else None

    def _discover_event_id_from_edit_list(self, page) -> str | None:
        """Scrape the diary edit list for the first event edit link."""
        page.goto(urljoin(self.base_url, "/diary/edit/"), wait_until="networkidle")
        link = page.locator("a[href*='/diary/edit/event/id/']").first
        if link.count() == 0:
            return None
        href = link.get_attribute("href")
        # href is like /diary/edit/event/id/123/view/ or /diary/edit/event/id/123/
        # Extract the numeric ID from the path.
        import re
        m = re.search(r"/id/(\d+)", href)
        return m.group(1) if m else None

    # ------------------------------------------------------------------
    # Capture logic
    # ------------------------------------------------------------------

    def _capture_pages(
        self,
        page,
        persona: str,
        pages: list[PageDef],
        event_id: str | None = None,
    ) -> None:
        print(f"\nCapturing {persona} pages …")
        for pd in pages:
            path = pd.path
            if pd.discover_id and event_id:
                path = path.format(event_id=event_id)
            elif pd.discover_id and not event_id:
                print(f"  SKIP {pd.slug}: no event ID discovered")
                continue

            url = urljoin(self.base_url, path)
            for vp in VIEWPORTS:
                filename = f"{vp['width']}x{vp['height']}__{pd.slug}.png"
                out_path = self.output_dir / filename

                print(f"  [{vp['name']}] {path} -> {filename}")
                page.set_viewport_size({"width": vp["width"], "height": vp["height"]})

                for attempt in range(3):
                    try:
                        page.goto(url, wait_until="networkidle", timeout=15_000)
                        break
                    except PlaywrightTimeout:
                        print(f"    TIMEOUT — retrying ({attempt + 1}/3)")
                        page.wait_for_timeout(1_000)
                    except Exception as exc:
                        print(f"    ERROR: {exc} — retrying ({attempt + 1}/3)")
                        page.wait_for_timeout(2_000)
                else:
                    print(f"    FAILED after 3 attempts — skipping")
                    continue

                # Collapse filter box on mobile rota pages so content is visible
                if pd.slug == "rota-edit" and vp["width"] < 768:
                    try:
                        toggle = page.locator("#rota-filter-toggle")
                        if toggle.count() > 0:
                            toggle.click()
                            page.wait_for_timeout(300)
                    except Exception:
                        pass

                # Wait for JS layout (masonry, etc.) to settle
                page.wait_for_timeout(800)
                page.screenshot(path=str(out_path), full_page=False)
                # Brief pause between viewports to avoid hammering the server
                page.wait_for_timeout(400)

                # Check for baseline
                baseline_path = None
                if self.baseline_dir:
                    baseline_path = self.baseline_dir / filename
                    if not baseline_path.exists():
                        baseline_path = None

                self.results.append(
                    CaptureResult(
                        slug=pd.slug,
                        persona=persona,
                        viewport_name=vp["name"],
                        viewport_w=vp["width"],
                        viewport_h=vp["height"],
                        current_path=out_path,
                        baseline_path=baseline_path,
                    )
                )

    # ------------------------------------------------------------------
    # Diffing
    # ------------------------------------------------------------------

    def _generate_diffs(self) -> None:
        diffs_dir = self.output_dir.parent.parent / "diffs" / self.version
        diffs_dir.mkdir(parents=True, exist_ok=True)
        print(f"\nGenerating diffs in {diffs_dir} …")

        for r in self.results:
            if r.baseline_path is None:
                continue
            diff_path = diffs_dir / r.current_path.name
            pct = _compute_diff(r.baseline_path, r.current_path, diff_path)
            r.diff_pct = pct
            if pct > 0:
                print(f"  {r.current_path.name}: {pct:.2f}% changed")

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def _generate_report(self) -> None:
        gallery_dir = self.output_dir.parent.parent / "gallery"
        gallery_dir.mkdir(parents=True, exist_ok=True)
        report_path = gallery_dir / f"{self.version}.html"
        print(f"\nWriting gallery report to {report_path} …")

        html = _build_html(self.version, self.results, self.baseline_dir)
        report_path.write_text(html, encoding="utf-8")
        print(f"Done. Open {report_path} in a browser.")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class CaptureResult:
    slug: str
    persona: str
    viewport_name: str
    viewport_w: int
    viewport_h: int
    current_path: Path
    baseline_path: Path | None
    diff_pct: float = 0.0

    @property
    def filename(self) -> str:
        return self.current_path.name

    @property
    def changed(self) -> bool:
        return self.diff_pct > 0.0


# ---------------------------------------------------------------------------
# Diff computation (Pillow)
# ---------------------------------------------------------------------------

THRESHOLD = 20  # per-channel delta to count as "different"


def _compute_diff(baseline: Path, current: Path, diff_out: Path) -> float:
    """Return percentage of pixels that differ (0.0–100.0)."""
    try:
        img1 = Image.open(baseline).convert("RGB")
        img2 = Image.open(current).convert("RGB")
    except Exception as exc:
        print(f"    ERROR opening images: {exc}")
        return 0.0

    if img1.size != img2.size:
        # Resize both to the smaller dimensions so we can still diff
        w = min(img1.width, img2.width)
        h = min(img1.height, img2.height)
        img1 = img1.crop((0, 0, w, h))
        img2 = img2.crop((0, 0, w, h))

    diff = ImageChops.difference(img1, img2)
    # diff is an image where each pixel = abs(a-b) per channel
    pixels = diff.getdata()
    total = len(pixels)
    changed = sum(
        1 for r, g, b in pixels if r > THRESHOLD or g > THRESHOLD or b > THRESHOLD
    )

    pct = (changed / total) * 100 if total else 0.0

    if pct > 0:
        # Build a red-highlight diff image
        diff_red = Image.new("RGB", img1.size)
        diff_px = diff_red.load()
        for i, (r, g, b) in enumerate(pixels):
            if r > THRESHOLD or g > THRESHOLD or b > THRESHOLD:
                x = i % img1.width
                y = i // img1.width
                diff_px[x, y] = (255, 0, 0)
        diff_red.save(diff_out)

    return pct


# ---------------------------------------------------------------------------
# HTML gallery builder
# ---------------------------------------------------------------------------

def _build_html(version: str, results: list[CaptureResult], baseline_dir: Path | None) -> str:
    # Group results by page slug for display
    changed_count = sum(1 for r in results if r.changed)
    new_count = sum(1 for r in results if r.baseline_path is None)

    cards_html = ""
    for r in results:
        cards_html += _card_html(r, baseline_dir)

    return textwrap.dedent(f'''\
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Toolkit Screenshots — {version}</title>
      <style>
        :root {{
          --bg: #f5f5f5;
          --card: #fff;
          --text: #333;
          --muted: #666;
          --accent: #2563eb;
          --danger: #dc2626;
          --success: #16a34a;
          --border: #ddd;
          --radius: 8px;
        }}
        * {{ box-sizing: border-box; }}
        body {{
          font-family: system-ui, -apple-system, sans-serif;
          background: var(--bg);
          color: var(--text);
          margin: 0;
          padding: 24px;
          line-height: 1.5;
        }}
        header {{
          max-width: 1400px;
          margin: 0 auto 24px;
          padding-bottom: 16px;
          border-bottom: 2px solid var(--border);
        }}
        h1 {{ margin: 0 0 8px; font-size: 1.6rem; }}
        .stats {{
          display: flex;
          gap: 24px;
          color: var(--muted);
          font-size: 0.95rem;
        }}
        .stats strong {{ color: var(--text); }}
        .filters {{
          max-width: 1400px;
          margin: 0 auto 24px;
          display: flex;
          gap: 12px;
          align-items: center;
        }}
        .filters button {{
          padding: 6px 14px;
          border: 1px solid var(--border);
          background: var(--card);
          border-radius: var(--radius);
          cursor: pointer;
          font-size: 0.9rem;
        }}
        .filters button.active {{
          background: var(--accent);
          color: #fff;
          border-color: var(--accent);
        }}
        .grid {{
          max-width: 1400px;
          margin: 0 auto;
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
          gap: 24px;
        }}
        .card {{
          background: var(--card);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          overflow: hidden;
          box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}
        .card.hidden {{ display: none; }}
        .card-header {{
          padding: 12px 16px;
          border-bottom: 1px solid var(--border);
          display: flex;
          justify-content: space-between;
          align-items: center;
        }}
        .card-title {{
          font-weight: 600;
          font-size: 0.95rem;
        }}
        .card-meta {{
          font-size: 0.8rem;
          color: var(--muted);
        }}
        .badge {{
          display: inline-block;
          padding: 2px 8px;
          border-radius: 12px;
          font-size: 0.75rem;
          font-weight: 600;
        }}
        .badge-changed {{
          background: #fee2e2;
          color: var(--danger);
        }}
        .badge-new {{
          background: #dcfce7;
          color: var(--success);
        }}
        .card-body {{
          position: relative;
          background: #000;
        }}
        .card-body img {{
          display: block;
          width: 100%;
          height: auto;
        }}
        .ba-slider {{
          position: relative;
        }}
        .ba-slider > img {{ width: 100%; display: block; }}
        .ba-slider .resize {{
          position: absolute;
          top: 0; left: 0;
          height: 100%;
          overflow: hidden;
        }}
        .ba-slider .resize img {{
          display: block;
          height: 100%;
          width: auto;
        }}
        .ba-handle {{
          position: absolute;
          bottom: 8px;
          left: 5%;
          width: 90%;
          z-index: 10;
          opacity: 0;
          transition: opacity 0.2s;
        }}
        .ba-slider:hover .ba-handle {{ opacity: 1; }}
        .ba-labels {{
          position: absolute;
          top: 8px;
          left: 8px;
          right: 8px;
          display: flex;
          justify-content: space-between;
          pointer-events: none;
          z-index: 5;
        }}
        .ba-labels span {{
          background: rgba(0,0,0,0.6);
          color: #fff;
          padding: 2px 8px;
          border-radius: 4px;
          font-size: 0.75rem;
        }}
        .card-footer {{
          padding: 12px 16px;
          font-size: 0.85rem;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }}
        .card-footer a {{
          color: var(--accent);
          text-decoration: none;
        }}
        .card-footer a:hover {{ text-decoration: underline; }}
        .no-diff {{
          padding: 40px;
          text-align: center;
          color: var(--muted);
        }}
      </style>
    </head>
    <body>
      <header>
        <h1>Toolkit Screenshots — {version}</h1>
        <div class="stats">
          <span><strong>{len(results)}</strong> captures</span>
          <span><strong>{changed_count}</strong> changed</span>
          <span><strong>{new_count}</strong> new (no baseline)</span>
        </div>
      </header>

      <div class="filters">
        <button class="active" id="btn-all" onclick="filter('all')">All</button>
        <button id="btn-changed" onclick="filter('changed')">Changed only</button>
        <button id="btn-new" onclick="filter('new')">New only</button>
      </div>

      <div class="grid" id="grid">
        {cards_html}
      </div>

      <script>
        function filter(mode) {{
          document.querySelectorAll('.filters button').forEach(b => b.classList.remove('active'));
          document.getElementById('btn-' + mode).classList.add('active');
          document.querySelectorAll('.card').forEach(card => {{
            const isChanged = card.dataset.changed === 'true';
            const isNew = card.dataset.new === 'true';
            if (mode === 'all') card.classList.remove('hidden');
            else if (mode === 'changed') card.classList.toggle('hidden', !isChanged);
            else if (mode === 'new') card.classList.toggle('hidden', !isNew);
          }});
        }}
        // Wire up range inputs to resize overlays
        document.querySelectorAll('.ba-handle').forEach(slider => {{
          slider.addEventListener('input', function() {{
            this.previousElementSibling.style.width = this.value + '%';
          }});
        }});
      </script>
    </body>
    </html>
    ''')


def _card_html(r: CaptureResult, baseline_dir: Path | None) -> str:
    is_new = r.baseline_path is None
    is_changed = r.changed

    # Build relative paths from the gallery HTML to the image files.
    # Gallery is in screenshots/gallery/<version>.html
    # Current images are in screenshots/current/<version>/
    # Baseline images are in screenshots/baseline/<baseline_version>/
    current_rel = f"../current/{r.current_path.parent.name}/{r.filename}"

    badge = ""
    if is_new:
        badge = '<span class="badge badge-new">new</span>'
    elif is_changed:
        badge = f'<span class="badge badge-changed">{r.diff_pct:.1f}% diff</span>'

    # Before/after slider (only when baseline exists)
    if r.baseline_path and baseline_dir:
        baseline_rel = f"../baseline/{r.baseline_path.parent.name}/{r.filename}"
        image_block = textwrap.dedent(f'''\
          <div class="ba-slider">
            <img src="{current_rel}" alt="current">
            <div class="resize" style="width: 50%">
              <img src="{baseline_rel}" alt="baseline">
            </div>
            <div class="ba-labels">
              <span>baseline</span>
              <span>{r.version}</span>
            </div>
            <input type="range" min="0" max="100" value="50" class="ba-handle"
                   aria-label="Before / after slider">
          </div>
        ''')
    else:
        image_block = f'<img src="{current_rel}" alt="screenshot">'

    return textwrap.dedent(f'''\
      <div class="card" data-changed="{'true' if is_changed else 'false'}" data-new="{'true' if is_new else 'false'}">
        <div class="card-header">
          <div>
            <div class="card-title">{r.slug}</div>
            <div class="card-meta">{r.persona} · {r.viewport_name} ({r.viewport_w}×{r.viewport_h})</div>
          </div>
          {badge}
        </div>
        <div class="card-body">
          {image_block}
        </div>
        <div class="card-footer">
          <span>{r.filename}</span>
          <a href="{current_rel}" target="_blank">Open full size ↗</a>
        </div>
      </div>
    ''')


# Fix: add a version property to CaptureResult so _card_html can reference it
# Actually we can just use the global version. Let me inject it into the card.


def _build_html(version: str, results: list[CaptureResult], baseline_dir: Path | None) -> str:
    changed_count = sum(1 for r in results if r.changed)
    new_count = sum(1 for r in results if r.baseline_path is None)

    cards_html = ""
    for r in results:
        cards_html += _card_html(r, baseline_dir, version)

    return textwrap.dedent(f'''\
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Toolkit Screenshots — {version}</title>
      <style>
        :root {{
          --bg: #f5f5f5;
          --card: #fff;
          --text: #333;
          --muted: #666;
          --accent: #2563eb;
          --danger: #dc2626;
          --success: #16a34a;
          --border: #ddd;
          --radius: 8px;
        }}
        * {{ box-sizing: border-box; }}
        body {{
          font-family: system-ui, -apple-system, sans-serif;
          background: var(--bg);
          color: var(--text);
          margin: 0;
          padding: 24px;
          line-height: 1.5;
        }}
        header {{
          max-width: 1400px;
          margin: 0 auto 24px;
          padding-bottom: 16px;
          border-bottom: 2px solid var(--border);
        }}
        h1 {{ margin: 0 0 8px; font-size: 1.6rem; }}
        .stats {{
          display: flex;
          gap: 24px;
          color: var(--muted);
          font-size: 0.95rem;
        }}
        .stats strong {{ color: var(--text); }}
        .filters {{
          max-width: 1400px;
          margin: 0 auto 24px;
          display: flex;
          gap: 12px;
          align-items: center;
        }}
        .filters button {{
          padding: 6px 14px;
          border: 1px solid var(--border);
          background: var(--card);
          border-radius: var(--radius);
          cursor: pointer;
          font-size: 0.9rem;
        }}
        .filters button.active {{
          background: var(--accent);
          color: #fff;
          border-color: var(--accent);
        }}
        .grid {{
          max-width: 1400px;
          margin: 0 auto;
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
          gap: 24px;
        }}
        .card {{
          background: var(--card);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          overflow: hidden;
          box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}
        .card.hidden {{ display: none; }}
        .card-header {{
          padding: 12px 16px;
          border-bottom: 1px solid var(--border);
          display: flex;
          justify-content: space-between;
          align-items: center;
        }}
        .card-title {{
          font-weight: 600;
          font-size: 0.95rem;
        }}
        .card-meta {{
          font-size: 0.8rem;
          color: var(--muted);
        }}
        .badge {{
          display: inline-block;
          padding: 2px 8px;
          border-radius: 12px;
          font-size: 0.75rem;
          font-weight: 600;
        }}
        .badge-changed {{
          background: #fee2e2;
          color: var(--danger);
        }}
        .badge-new {{
          background: #dcfce7;
          color: var(--success);
        }}
        .card-body {{
          position: relative;
          background: #000;
        }}
        .card-body img {{
          display: block;
          width: 100%;
          height: auto;
        }}
        .ba-slider {{
          position: relative;
        }}
        .ba-slider > img {{ width: 100%; display: block; }}
        .ba-slider .resize {{
          position: absolute;
          top: 0; left: 0;
          height: 100%;
          overflow: hidden;
        }}
        .ba-slider .resize img {{
          display: block;
          height: 100%;
          width: auto;
        }}
        .ba-handle {{
          position: absolute;
          bottom: 8px;
          left: 5%;
          width: 90%;
          z-index: 10;
          opacity: 0;
          transition: opacity 0.2s;
        }}
        .ba-slider:hover .ba-handle {{ opacity: 1; }}
        .ba-labels {{
          position: absolute;
          top: 8px;
          left: 8px;
          right: 8px;
          display: flex;
          justify-content: space-between;
          pointer-events: none;
          z-index: 5;
        }}
        .ba-labels span {{
          background: rgba(0,0,0,0.6);
          color: #fff;
          padding: 2px 8px;
          border-radius: 4px;
          font-size: 0.75rem;
        }}
        .card-footer {{
          padding: 12px 16px;
          font-size: 0.85rem;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }}
        .card-footer a {{
          color: var(--accent);
          text-decoration: none;
        }}
        .card-footer a:hover {{ text-decoration: underline; }}
        .no-diff {{
          padding: 40px;
          text-align: center;
          color: var(--muted);
        }}
      </style>
    </head>
    <body>
      <header>
        <h1>Toolkit Screenshots — {version}</h1>
        <div class="stats">
          <span><strong>{len(results)}</strong> captures</span>
          <span><strong>{changed_count}</strong> changed</span>
          <span><strong>{new_count}</strong> new (no baseline)</span>
        </div>
      </header>

      <div class="filters">
        <button class="active" id="btn-all" onclick="filter('all')">All</button>
        <button id="btn-changed" onclick="filter('changed')">Changed only</button>
        <button id="btn-new" onclick="filter('new')">New only</button>
      </div>

      <div class="grid" id="grid">
        {cards_html}
      </div>

      <script>
        function filter(mode) {{
          document.querySelectorAll('.filters button').forEach(b => b.classList.remove('active'));
          document.getElementById('btn-' + mode).classList.add('active');
          document.querySelectorAll('.card').forEach(card => {{
            const isChanged = card.dataset.changed === 'true';
            const isNew = card.dataset.new === 'true';
            if (mode === 'all') card.classList.remove('hidden');
            else if (mode === 'changed') card.classList.toggle('hidden', !isChanged);
            else if (mode === 'new') card.classList.toggle('hidden', !isNew);
          }});
        }}
        document.querySelectorAll('.ba-handle').forEach(slider => {{
          slider.addEventListener('input', function() {{
            this.previousElementSibling.style.width = this.value + '%';
          }});
        }});
      </script>
    </body>
    </html>
    ''')


def _card_html(r: CaptureResult, baseline_dir: Path | None, version: str) -> str:
    is_new = r.baseline_path is None
    is_changed = r.changed

    current_rel = f"../current/{r.current_path.parent.name}/{r.filename}"

    badge = ""
    if is_new:
        badge = '<span class="badge badge-new">new</span>'
    elif is_changed:
        badge = f'<span class="badge badge-changed">{r.diff_pct:.1f}% diff</span>'

    if r.baseline_path and baseline_dir:
        baseline_rel = f"../baseline/{r.baseline_path.parent.name}/{r.filename}"
        image_block = textwrap.dedent(f'''\
          <div class="ba-slider">
            <img src="{current_rel}" alt="current">
            <div class="resize" style="width: 50%">
              <img src="{baseline_rel}" alt="baseline">
            </div>
            <div class="ba-labels">
              <span>baseline</span>
              <span>{version}</span>
            </div>
            <input type="range" min="0" max="100" value="50" class="ba-handle"
                   aria-label="Before / after slider">
          </div>
        ''')
    else:
        image_block = f'<img src="{current_rel}" alt="screenshot">'

    return textwrap.dedent(f'''\
      <div class="card" data-changed="{'true' if is_changed else 'false'}" data-new="{'true' if is_new else 'false'}">
        <div class="card-header">
          <div>
            <div class="card-title">{r.slug}</div>
            <div class="card-meta">{r.persona} · {r.viewport_name} ({r.viewport_w}×{r.viewport_h})</div>
          </div>
          {badge}
        </div>
        <div class="card-body">
          {image_block}
        </div>
        <div class="card-footer">
          <span>{r.filename}</span>
          <a href="{current_rel}" target="_blank">Open full size ↗</a>
        </div>
      </div>
    ''')


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture toolkit screenshots at multiple viewports."
    )
    parser.add_argument("--version", required=True)
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--output", default="screenshots/current")
    parser.add_argument("--baseline", default=None, help="Path to baseline folder")
    parser.add_argument(
        "--password", default=DEFAULT_PASSWORD, help="Password for demo accounts"
    )
    args = parser.parse_args()

    output_dir = Path(args.output)
    baseline_dir = Path(args.baseline) if args.baseline else None

    cap = ScreenshotCapture(
        args.base_url, output_dir, baseline_dir, args.version, password=args.password
    )
    cap.run()


if __name__ == "__main__":
    main()
