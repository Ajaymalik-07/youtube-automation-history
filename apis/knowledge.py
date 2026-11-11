"""
Fact Grounding & Historical Evidence Retrieval System
Pulls verified historical background facts, archaeological papers, and citable sources.

Source Hierarchy:
  1. Government Archives / ASI Publications (Archive.org Historical Collections)
  2. Peer-Reviewed Academic Research (Crossref Open Metadata API)
  3. Historical Documents, Memoirs & Digitized Books (Archive.org)
  4. Wikipedia (Preliminary discovery & entity orientation only)
"""
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

from apis.http import get, get_json, ttl_cache

# Evidence Classification Standard
EVIDENCE_LEVELS = {
    "ESTABLISHED_FACT": "Level 1: Verified by archaeological consensus, inscriptions, or official treaties.",
    "STRONGLY_SUPPORTED": "Level 2: Backed by multiple contemporary chronicles and major academic consensus.",
    "DISPUTED_INTERPRETATION": "Level 3: Valid academic debate exists; differing interpretations.",
    "ORAL_TRADITION": "Level 4: Preserved in bards, folklore, or traditional songs; not epigraphically verified.",
    "MYTHOLOGY_FOLKLORE": "Level 5: Religious epics or mythological legends; treated as cultural belief.",
    "SPECULATION": "Level 6: Modern conjecture without contemporary archaeological or textual backing.",
}


def wikipedia(topic: str, n: int = 2) -> list:
    """Preliminary discovery and general context via Wikipedia API (keyless)."""
    s = get_json("https://en.wikipedia.org/w/api.php", params={
        "action": "query", "list": "search", "srsearch": topic,
        "format": "json", "srlimit": n,
    })
    out = []
    for hit in s.get("query", {}).get("search", []):
        title = hit["title"]
        try:
            summ = get_json("https://en.wikipedia.org/api/rest_v1/page/summary/"
                            + quote(title.replace(" ", "_"), safe=""))
        except Exception:
            continue
        extract = (summ.get("extract") or "").strip()
        if not extract or summ.get("type") == "disambiguation":
            continue
        out.append({
            "source_type": "Preliminary Discovery (Wikipedia)",
            "source": "Wikipedia",
            "title":  title,
            "text":   extract,
            "url":    summ.get("content_urls", {}).get("desktop", {}).get("page", ""),
            "evidence_tier": "Preliminary",
        })
    return out


def archive_org_historical(topic: str, n: int = 3) -> list:
    """
    Government archives, ASI records, and digitized historical literature
    from Internet Archive's Open Collections (keyless).
    """
    clean_words = [w for w in topic.replace('"', '').split() if len(w) > 3][:5]
    if not clean_words:
        return []
    query = " ".join(clean_words) + " AND (history OR archaeology OR empire OR civilization)"
    try:
        data = get_json("https://archive.org/advancedsearch.php", params={
            "q": query,
            "fl[]": ["title", "identifier", "description", "year", "creator"],
            "rows": n,
            "page": 1,
            "output": "json",
        }, timeout=12)
        docs = data.get("response", {}).get("docs", [])
        out = []
        for d in docs:
            title = d.get("title") or "Historical Record"
            desc = d.get("description") or ""
            if isinstance(desc, list):
                desc = " ".join(desc)
            desc = desc[:450].strip()
            year = d.get("year", "")
            creator = d.get("creator", "Historical Archive")
            ident = d.get("identifier", "")
            url = f"https://archive.org/details/{ident}" if ident else "https://archive.org"
            snippet = f"{title} ({year}) by {creator}. {desc}".strip()
            out.append({
                "source_type": "Historical Archive / Primary & Secondary Record",
                "source": "Internet Archive Historical Collection",
                "title": f"{title} [{year}]" if year else title,
                "text": snippet,
                "url": url,
                "evidence_tier": "Archival / Book",
            })
        return out
    except Exception as e:
        print(f"   ⚠ Archive.org historical retrieval warning: {e}")
        return []


def crossref_peer_reviewed(topic: str, n: int = 3) -> list:
    """
    Peer-reviewed scholarly articles and archaeological publications
    via Crossref Open Metadata API (keyless).
    """
    clean_topic = " ".join([w for w in topic.replace('"', '').split() if len(w) > 3][:6])
    if not clean_topic:
        return []
    try:
        data = get_json("https://api.crossref.org/works", params={
            "query": f"{clean_topic} history archaeology",
            "rows": n,
            "sort": "relevance",
        }, timeout=12)
        items = data.get("message", {}).get("items", [])
        out = []
        for it in items:
            titles = it.get("title", [])
            title = titles[0] if titles else "Academic Journal Article"
            container = it.get("container-title", [])
            journal = container[0] if container else "Peer-Reviewed Journal"
            doi = it.get("DOI", "")
            url = f"https://doi.org/{doi}" if doi else it.get("URL", "")
            issued = it.get("issued", {}).get("date-parts", [[None]])[0][0]
            year_str = f" ({issued})" if issued else ""
            out.append({
                "source_type": "Peer-Reviewed Scholarly Publication",
                "source": f"Crossref ({journal})",
                "title": f"{title}{year_str}",
                "text": f"Scholarly publication in {journal}. DOI: {doi}",
                "url": url,
                "evidence_tier": "Academic / Peer-Reviewed",
            })
        return out
    except Exception as e:
        print(f"   ⚠ Crossref peer-reviewed query warning: {e}")
        return []


@ttl_cache(60 * 60)
def gather_context(topic: str) -> dict:
    """
    Gathers multi-tiered historical context from archives, academic literature, and encyclopedias.
    Returns:
      {
        "facts": str,
        "sources": [{"source": str, "title": str, "url": str, "tier": str}],
        "evidence_framework": dict
      }
    """
    if not topic.strip():
        return {"facts": "", "sources": [], "evidence_framework": EVIDENCE_LEVELS}

    def _safe_run(fn, *args):
        try:
            return fn(*args)
        except Exception as e:
            print(f"   ⚠ {fn.__name__} context gathering failed: {e}")
            return []

    with ThreadPoolExecutor(max_workers=3) as ex:
        f_arch = ex.submit(_safe_run, archive_org_historical, topic, 3)
        f_cross = ex.submit(_safe_run, crossref_peer_reviewed, topic, 2)
        f_wiki = ex.submit(_safe_run, wikipedia, topic, 2)

        arch_results = f_arch.result()
        cross_results = f_cross.result()
        wiki_results = f_wiki.result()

    # Prioritize: Primary/Archival → Academic → Preliminary Wikipedia
    all_docs = arch_results + cross_results + wiki_results

    fact_blocks = []
    for d in all_docs:
        fact_blocks.append(f"[{d.get('source_type', d['source'])}: {d['title']}]\n{d['text']}\nURL: {d['url']}")

    facts = "\n\n".join(fact_blocks)

    return {
        "facts": facts[:7500],
        "sources": [
            {
                "source": d["source"],
                "title": d["title"],
                "url": d["url"],
                "tier": d.get("evidence_tier", "Secondary"),
            }
            for d in all_docs
        ],
        "evidence_framework": EVIDENCE_LEVELS,
    }
