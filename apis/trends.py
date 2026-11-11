"""
Historical Trend & Discovery Radar
Monitors real-time search spikes, historical anniversaries, and archaeological discoveries.
All sources are keyless and free tier.

  google       Google Trends daily RSS (search trends in India / global)
  on_this_day  Historic anniversaries, decisive battles, and milestones on today's date
  archaeology  Recent archaeological excavation findings & heritage discoveries
  wikipedia    Wikipedia most-read articles (yesterday's reading trends)
"""
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import config
from apis.http import get, get_json, ttl_cache

_HT = {"ht": "https://trends.google.com/trending/rss"}

# Wikipedia's most-read list skip list
_WIKI_SKIP = ("Main_Page", "Special:", "Wikipedia:", "Portal:", "File:", "Deaths_in_")


def google_trends(geo: str = "IN", limit: int = 12) -> list:
    """Google Trends daily RSS search spikes."""
    target_geo = geo or getattr(config, "TRENDS_GEO", "IN")
    try:
        r = get("https://trends.google.com/trending/rss", params={"geo": target_geo}, timeout=10)
        root = ET.fromstring(r.content)
        out = []
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            if not title:
                continue
            news = item.find("ht:news_item", _HT)
            url = (news.findtext("ht:news_item_url", namespaces=_HT)
                   if news is not None else None)
            headline = (news.findtext("ht:news_item_title", namespaces=_HT)
                        if news is not None else "")
            out.append({
                "title":  title,
                "detail": headline or "",
                "meta":   (item.findtext("ht:approx_traffic", namespaces=_HT) or "").strip(),
                "url":    url or f"https://www.google.com/search?q={quote_plus(title)}",
            })
        return out[:limit]
    except Exception as e:
        print(f"   ⚠ Google Trends retrieval warning: {e}")
        return []


def wikipedia_most_read(limit: int = 12) -> list:
    """Most read Wikipedia articles."""
    try:
        day = datetime.now(timezone.utc) - timedelta(days=1)
        d = get_json(f"https://en.wikipedia.org/api/rest_v1/feed/featured/{day:%Y/%m/%d}", timeout=10)
        out = []
        for a in d.get("mostread", {}).get("articles", []):
            if a.get("title", "").startswith(_WIKI_SKIP):
                continue
            out.append({
                "title":  a.get("normalizedtitle") or a.get("title", "").replace("_", " "),
                "detail": a.get("description", ""),
                "meta":   f"{a.get('views', 0):,} views",
                "url":    a.get("content_urls", {}).get("desktop", {}).get("page", ""),
            })
        return out[:limit]
    except Exception as e:
        print(f"   ⚠ Wikipedia most read retrieval warning: {e}")
        return []


def on_this_day_history(limit: int = 12) -> list:
    """Historical anniversaries, battles, treaties, and turning points that happened on this calendar date."""
    try:
        today = datetime.now(timezone.utc)
        url = f"https://en.wikipedia.org/api/rest_v1/feed/onthisday/events/{today.month:02d}/{today.day:02d}"
        data = get_json(url, timeout=10)
        events = data.get("events", [])
        out = []
        for e in events:
            year = e.get("year", "")
            text = e.get("text", "")
            pages = e.get("pages", [])
            first_url = pages[0].get("content_urls", {}).get("desktop", {}).get("page", "") if pages else ""
            out.append({
                "title": f"{year} CE: {text[:90]}..." if len(text) > 90 else f"{year} CE: {text}",
                "detail": text,
                "meta": f"Year {year}",
                "url": first_url or f"https://en.wikipedia.org/wiki/{today.strftime('%B_%d')}",
            })
        return out[:limit]
    except Exception as e:
        print(f"   ⚠ On-This-Day history retrieval warning: {e}")
        return []


def archaeological_discoveries(limit: int = 10) -> list:
    """Recent archaeological findings and heritage excavation news."""
    try:
        # Crossref recent works on archaeological excavations
        data = get_json("https://api.crossref.org/works", params={
            "query": "archaeological excavation discovery civilization",
            "rows": limit,
            "sort": "published",
        }, timeout=10)
        items = data.get("message", {}).get("items", [])
        out = []
        for it in items:
            title = (it.get("title") or ["Archaeological Discovery"])[0]
            container = (it.get("container-title") or ["Archaeology Journal"])[0]
            doi = it.get("DOI", "")
            url = f"https://doi.org/{doi}" if doi else it.get("URL", "")
            out.append({
                "title": title[:100],
                "detail": f"Published in {container}",
                "meta": "Archaeology",
                "url": url,
            })
        return out
    except Exception as e:
        print(f"   ⚠ Archaeology discovery retrieval warning: {e}")
        return []


# Maintain backward compatibility aliases
hackernews = on_this_day_history
spaceflight_news = archaeological_discoveries
arxiv_latest = archaeological_discoveries

SOURCES = {
    "google":        ("Google Trends (India)", google_trends),
    "on_this_day":   ("On This Day in History", on_this_day_history),
    "archaeology":   ("Archaeological Discoveries", archaeological_discoveries),
    "wikipedia":     ("Wikipedia Reading Trends", wikipedia_most_read),
}


def _safe(key: str):
    label, fn = SOURCES[key]
    t0 = time.time()
    try:
        if key == "google":
            items = fn(getattr(config, "TRENDS_GEO", "IN"))
        else:
            items = fn()
        return key, {"label": label, "ok": True, "items": items,
                     "ms": int((time.time() - t0) * 1000)}
    except Exception as e:
        return key, {"label": label, "ok": False, "items": [],
                     "error": str(e)[:200], "ms": int((time.time() - t0) * 1000)}


@ttl_cache(15 * 60)
def get_trends() -> dict:
    """All historical trends sources, fetched in parallel, cached 15 minutes."""
    with ThreadPoolExecutor(max_workers=len(SOURCES)) as ex:
        results = dict(ex.map(_safe, SOURCES))
    return {"sources": results, "fetched_at": int(time.time())}


def headlines(limit: int = 25) -> list:
    """Flat list of trending historical titles — fed to the researcher for trend-aware picks."""
    data = get_trends()["sources"]
    titles = []
    for key in ("on_this_day", "archaeology", "google", "wikipedia"):
        titles += [i["title"] for i in data.get(key, {}).get("items", [])[:7]]
    return titles[:limit]
