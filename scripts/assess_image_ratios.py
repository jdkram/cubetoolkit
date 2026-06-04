#!/usr/bin/env python3
# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 4.6"]; status: "#ai-input"
"""
Scrape event images from starandshadow.org.uk and assess their aspect ratios.

Compares the real-world distribution of image shapes against the 2:3 portrait
crop target (600×900) to inform whether the current crop-box approach is
sensible for S+S content.

Usage:
    uv run --with requests --with pillow --with beautifulsoup4 scripts/assess_image_ratios.py
"""

import io
import sys
import time
from collections import Counter
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from PIL import Image

BASE_URL = "https://starandshadow.org.uk"
PROGRAMME_URL = f"{BASE_URL}/programme/"
TARGET_W, TARGET_H = 600, 900  # our 2:3 crop target
TARGET_RATIO = TARGET_W / TARGET_H

HEADERS = {"User-Agent": "sns-toolkit-image-audit/1.0 (internal research)"}


def classify_ratio(w, h):
    ratio = w / h
    if ratio < 0.6:
        return "very tall portrait (taller than 2:3)"
    elif ratio < 0.75:
        return "2:3 portrait (film one-sheet)"
    elif ratio < 0.9:
        return "3:4 portrait"
    elif ratio < 1.1:
        return "square (≈1:1)"
    elif ratio < 1.4:
        return "4:3 landscape"
    elif ratio < 1.8:
        return "3:2 landscape"
    else:
        return "wide landscape (>3:2)"


def crop_loss(w, h):
    """Fraction of the image that would be cropped away to hit TARGET_RATIO (2:3).

    Returns 0.0 if no crop needed (already correct ratio or taller).
    Returns a positive float if pixels would be lost from top/bottom or sides.
    """
    actual_ratio = w / h
    if actual_ratio <= TARGET_RATIO:
        # Image is already portrait enough — we'd crop the sides (or it fits exactly)
        needed_w = h * TARGET_RATIO
        if w <= needed_w:
            return 0.0  # no loss — image is narrower than target ratio
        return 1.0 - (needed_w / w)
    else:
        # Image is wider — we'd crop top/bottom
        needed_h = w / TARGET_RATIO
        return 1.0 - (h / needed_h)


def fetch_image_urls(session):
    print(f"Fetching programme page: {PROGRAMME_URL}")
    resp = session.get(PROGRAMME_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    urls = []
    seen = set()
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if "/media/diary/thumbnails/" not in src:
            continue
        full = urljoin(BASE_URL, src)
        if full not in seen:
            seen.add(full)
            urls.append(full)
    print(f"Found {len(urls)} unique event thumbnail URLs.\n")
    return urls


def analyse(urls, session):
    results = []
    failed = 0
    for i, url in enumerate(urls, 1):
        try:
            resp = session.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content))
            w, h = img.size
            results.append({"url": url, "w": w, "h": h})
            label = classify_ratio(w, h)
            loss = crop_loss(w, h)
            print(f"  [{i:3d}/{len(urls)}] {w:4d}×{h:4d}  ratio={w/h:.3f}  loss={loss:.0%}  {label}")
            time.sleep(0.05)  # polite crawl
        except Exception as e:
            print(f"  [{i:3d}/{len(urls)}] FAILED: {url} — {e}", file=sys.stderr)
            failed += 1
    return results, failed


def report(results):
    if not results:
        print("No results to report.")
        return

    print("\n" + "=" * 65)
    print("ASPECT RATIO AUDIT — starandshadow.org.uk event images")
    print("=" * 65)
    print(f"Target crop: {TARGET_W}×{TARGET_H} ({TARGET_W}:{TARGET_H} = {TARGET_RATIO:.3f})\n")

    # Category counts
    counts = Counter(classify_ratio(r["w"], r["h"]) for r in results)
    total = len(results)
    print("Shape distribution:")
    for label, n in sorted(counts.items(), key=lambda x: -x[1]):
        pct = n / total * 100
        bar = "█" * int(pct / 2)
        print(f"  {label:<40s}  {n:3d}  ({pct:5.1f}%)  {bar}")

    # Loss distribution
    losses = [crop_loss(r["w"], r["h"]) for r in results]
    no_loss = sum(1 for l in losses if l < 0.01)
    mild = sum(1 for l in losses if 0.01 <= l < 0.15)
    significant = sum(1 for l in losses if 0.15 <= l < 0.33)
    severe = sum(1 for l in losses if l >= 0.33)

    print(f"\nCrop loss if forced to {TARGET_W}:{TARGET_H}:")
    print(f"  <1%  (essentially no crop)  : {no_loss:3d}  ({no_loss/total*100:.0f}%)")
    print(f"  1–15%  (mild crop)           : {mild:3d}  ({mild/total*100:.0f}%)")
    print(f"  15–33%  (significant crop)   : {significant:3d}  ({significant/total*100:.0f}%)")
    print(f"  >33%  (severe — major loss)  : {severe:3d}  ({severe/total*100:.0f}%)")

    # Worst offenders
    worst = sorted(results, key=lambda r: -crop_loss(r["w"], r["h"]))[:10]
    print(f"\nTop 10 worst fits for 2:3 crop:")
    for r in worst:
        loss = crop_loss(r["w"], r["h"])
        fname = r["url"].split("/")[-1][:55]
        print(f"  {loss:5.0%} lost  {r['w']}×{r['h']}  {fname}")

    # Verdict
    print("\n" + "-" * 65)
    bad_pct = (significant + severe) / total * 100
    print(f"VERDICT: {bad_pct:.0f}% of images would lose >15% of their content")
    print(f"         to a hard 2:3 crop with no programmer-set crop box.")
    if bad_pct < 15:
        print("         → Low risk. The 2:3 default is a reasonable fit.")
    elif bad_pct < 35:
        print("         → Moderate risk. The crop tool matters; bad defaults hurt.")
    else:
        print("         → High risk. A forced 2:3 crop is a poor fit for S+S content.")
        print("           Consider: default to no crop (use easy_thumbnails resize),")
        print("           only crop when the programmer explicitly sets a box.")
    print("=" * 65)


def main():
    with requests.Session() as session:
        urls = fetch_image_urls(session)
        if not urls:
            print("No image URLs found. Check the scraper.", file=sys.stderr)
            sys.exit(1)
        results, failed = analyse(urls, session)
    report(results)
    if failed:
        print(f"\n({failed} images failed to download and were excluded.)")


if __name__ == "__main__":
    main()
