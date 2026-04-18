"""
OLX 1BHK Rental Monitor
Scrapes OLX India and sends instant push notifications via ntfy.sh
Tap the notification → opens directly in OLX app on iPhone
"""

import os
import json
import time
import logging
import hashlib
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("olx-monitor")

# ── Config (set these as environment variables on Railway) ──────────────────
NTFY_TOPIC      = os.environ["NTFY_TOPIC"]           # e.g. olx-alerts-abc123xyz
AREAS           = [a.strip() for a in os.getenv("AREAS", "Kakkanad,Edapally").split(",")]
BUDGET_MIN      = int(os.getenv("BUDGET_MIN", "5000"))
BUDGET_MAX      = int(os.getenv("BUDGET_MAX", "20000"))
FURNISHED       = os.getenv("FURNISHED", "any")       # any | furnished | semi | unfurnished
CHECK_INTERVAL  = int(os.getenv("CHECK_INTERVAL", "300"))  # seconds between full scans
SEEN_FILE       = Path(os.getenv("SEEN_FILE", "/data/seen_ids.json"))  # persists across restarts

# ── HTTP headers (mimics a real browser) ───────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
        "Mobile/15E148 Safari/604.1"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# ── Persistence ─────────────────────────────────────────────────────────────
def load_seen() -> set:
    try:
        SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        if SEEN_FILE.exists():
            return set(json.loads(SEEN_FILE.read_text()))
    except Exception as e:
        log.warning(f"Could not load seen IDs: {e}")
    return set()


def save_seen(seen: set):
    try:
        SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        SEEN_FILE.write_text(json.dumps(list(seen)))
    except Exception as e:
        log.warning(f"Could not save seen IDs: {e}")


# ── OLX Scraping ─────────────────────────────────────────────────────────────
def build_search_url(area: str) -> str:
    """Build OLX search URL for 1BHK rentals in a given area."""
    slug = area.lower().strip().replace(" ", "-")
    base = f"https://www.olx.in/items/q-1-BHK-for-rent-{slug}"
    params = (
        f"?search%5Bfilter_float_price%3Afrom%5D={BUDGET_MIN}"
        f"&search%5Bfilter_float_price%3Ato%5D={BUDGET_MAX}"
    )
    if FURNISHED == "furnished":
        params += "&search%5Bfilter_enum_furnished%5D%5B0%5D=yes"
    elif FURNISHED == "unfurnished":
        params += "&search%5Bfilter_enum_furnished%5D%5B0%5D=no"
    return base + params


def parse_next_data(html: str) -> list[dict]:
    """Extract listings from OLX's __NEXT_DATA__ JSON blob."""
    listings = []
    try:
        soup = BeautifulSoup(html, "html.parser")
        script = soup.find("script", {"id": "__NEXT_DATA__"})
        if not script:
            return listings

        data = json.loads(script.string)
        # Traverse the Next.js page props to find listing data
        props = data.get("props", {}).get("pageProps", {})

        # OLX stores listings under different paths depending on page type
        items = (
            props.get("ads")
            or props.get("listingProps", {}).get("ads")
            or props.get("data", {}).get("searchAds", {}).get("ads")
            or []
        )

        for item in items:
            try:
                listing_id = str(item.get("id", ""))
                title      = item.get("title", "").strip()
                price_raw  = item.get("price", {})
                price      = int(price_raw.get("value", {}).get("raw", 0)) if isinstance(price_raw, dict) else 0
                url        = "https://www.olx.in" + item.get("url", "")
                location   = (
                    item.get("location", {}).get("city", {}).get("name", "")
                    or item.get("location", {}).get("neighborhood", {}).get("name", "")
                )
                posted     = item.get("list_date", item.get("created_at", ""))

                if not listing_id or not title:
                    continue

                listings.append({
                    "id":       listing_id,
                    "title":    title,
                    "price":    price,
                    "url":      url,
                    "location": location,
                    "posted":   posted,
                })
            except Exception:
                continue

    except Exception as e:
        log.debug(f"parse_next_data error: {e}")

    return listings


def parse_html_fallback(html: str, area: str) -> list[dict]:
    """Fallback: parse OLX listing cards directly from HTML."""
    listings = []
    try:
        soup = BeautifulSoup(html, "html.parser")

        # OLX uses li elements with data-aut-id for listing cards
        cards = soup.select("li[data-aut-id='itemBox'], article[data-aut-id='itemBox']")

        for card in cards:
            try:
                link_tag  = card.select_one("a[href*='/item/']")
                title_tag = card.select_one("[data-aut-id='itemTitle']") or card.select_one("span._1AtVbE")
                price_tag = card.select_one("[data-aut-id='itemPrice']") or card.select_one("span._2Ks63A")

                if not link_tag:
                    continue

                raw_url = link_tag.get("href", "")
                if raw_url.startswith("/"):
                    raw_url = "https://www.olx.in" + raw_url

                title = title_tag.get_text(strip=True) if title_tag else "1 BHK for Rent"
                price_text = price_tag.get_text(strip=True) if price_tag else "0"
                price = int("".join(filter(str.isdigit, price_text))) if price_text else 0

                listing_id = hashlib.md5(raw_url.encode()).hexdigest()[:16]

                listings.append({
                    "id":       listing_id,
                    "title":    title,
                    "price":    price,
                    "url":      raw_url,
                    "location": area,
                    "posted":   "Just now",
                })
            except Exception:
                continue

    except Exception as e:
        log.debug(f"parse_html_fallback error: {e}")

    return listings


def fetch_listings(area: str) -> list[dict]:
    """Fetch and parse listings for one area, with retry logic."""
    url = build_search_url(area)
    log.info(f"Checking: {area}  →  {url}")

    for attempt in range(3):
        try:
            resp = SESSION.get(url, timeout=20)
            if resp.status_code == 200:
                html = resp.text
                listings = parse_next_data(html)
                if not listings:
                    listings = parse_html_fallback(html, area)
                log.info(f"  Found {len(listings)} listing(s) in {area}")
                return listings
            elif resp.status_code == 429:
                wait = 60 * (attempt + 1)
                log.warning(f"  Rate limited. Waiting {wait}s…")
                time.sleep(wait)
            else:
                log.warning(f"  HTTP {resp.status_code} for {area}")
                break
        except requests.RequestException as e:
            log.warning(f"  Request failed (attempt {attempt + 1}): {e}")
            time.sleep(10)

    return []


# ── Filtering ─────────────────────────────────────────────────────────────────
def passes_filters(listing: dict) -> bool:
    """Return True if listing matches user-configured filters."""
    price = listing.get("price", 0)
    if price and (price < BUDGET_MIN or price > BUDGET_MAX):
        return False

    furnished_kw = listing.get("title", "").lower()
    if FURNISHED == "furnished" and "unfurnish" in furnished_kw:
        return False
    if FURNISHED == "unfurnished" and "furnished" in furnished_kw:
        return False

    return True


# ── Notifications ─────────────────────────────────────────────────────────────
def send_notification(listing: dict):
    """
    Send a push notification via ntfy.sh.
    On iPhone, tapping the notification opens the OLX URL →
    iOS universal links route it directly into the OLX app.
    """
    price_str = f"₹{listing['price']:,}/mo" if listing['price'] else "Price not listed"
    title     = f"New 1BHK · {listing['location']} · {price_str}"
    body      = listing["title"]

    try:
        resp = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=body.encode("utf-8"),
            headers={
                "Title":    title,
                "Priority": "high",
                "Tags":     "house,bell",
                "Click":    listing["url"],   # ← tap notification → OLX app
                "Actions":  f"view, Open in OLX, {listing['url']}, clear=true",
            },
            timeout=10,
        )
        if resp.status_code == 200:
            log.info(f"  Notified: {title}")
        else:
            log.warning(f"  ntfy.sh returned {resp.status_code}: {resp.text}")
    except Exception as e:
        log.error(f"  Notification failed: {e}")


def send_startup_ping():
    """Send a test notification when the monitor starts."""
    areas_str = ", ".join(AREAS)
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=f"Monitoring {areas_str} · Budget ₹{BUDGET_MIN:,}–₹{BUDGET_MAX:,}/mo · Every {CHECK_INTERVAL//60} min".encode(),
        headers={
            "Title":    "OLX Monitor is live!",
            "Priority": "default",
            "Tags":     "white_check_mark",
        },
        timeout=10,
    )


# ── Main loop ─────────────────────────────────────────────────────────────────
def main():
    log.info("=" * 60)
    log.info("OLX 1BHK Rental Monitor starting…")
    log.info(f"  Areas        : {AREAS}")
    log.info(f"  Budget       : ₹{BUDGET_MIN:,} – ₹{BUDGET_MAX:,}/mo")
    log.info(f"  Furnished    : {FURNISHED}")
    log.info(f"  Check every  : {CHECK_INTERVAL}s ({CHECK_INTERVAL//60} min)")
    log.info(f"  ntfy topic   : {NTFY_TOPIC}")
    log.info("=" * 60)

    seen = load_seen()
    log.info(f"Loaded {len(seen)} previously seen listing IDs.")

    send_startup_ping()

    scan_count = 0
    while True:
        scan_count += 1
        log.info(f"\n── Scan #{scan_count} at {datetime.now().strftime('%H:%M:%S')} ──")
        new_this_scan = 0

        for area in AREAS:
            listings = fetch_listings(area)

            for listing in listings:
                lid = listing["id"]
                if lid not in seen and passes_filters(listing):
                    seen.add(lid)
                    send_notification(listing)
                    new_this_scan += 1
                    time.sleep(1)  # small delay between notifications

            time.sleep(5)  # be polite between area requests

        save_seen(seen)
        log.info(f"── Scan #{scan_count} done. {new_this_scan} new listing(s) found. ──")
        log.info(f"   Next scan in {CHECK_INTERVAL}s…")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
