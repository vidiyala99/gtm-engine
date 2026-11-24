"""Free page fetches (homepage, careers) with a disk cache, plus the quote a page gives about itself."""

from __future__ import annotations

import hashlib
import html as htmllib
import re

import httpx

from gtm.pipeline.store import data_dir

UA = "Mozilla/5.0 (compatible; GTMEngine/0.1; +https://github.com/ethanplusai/sellbird)"
MAX_BYTES = 1_500_000


def _cache(url: str):
    d = data_dir() / "cache" / "web"
    d.mkdir(parents=True, exist_ok=True)
    return d / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".html")


def fetch(url: str, timeout: float = 10.0) -> tuple[str, str]:
    """(final_url, html); ("", "") when the page can't be read. Cached on disk, misses too."""
    path = _cache(url)
    if path.exists():
        raw = path.read_text(encoding="utf-8", errors="replace")
        final, _, body = raw.partition("\n")
        return final, body
    final, body = "", ""
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers={"User-Agent": UA}) as c:
            r = c.get(url)
            if r.status_code == 200 and "html" in r.headers.get("content-type", ""):
                final, body = str(r.url), r.text[:MAX_BYTES]
    except (httpx.HTTPError, ValueError):
        pass
    path.write_text(f"{final}\n{body}", encoding="utf-8")
    return final, body


_META = [re.compile(p, re.I | re.S) for p in (
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']{20,})["\']',
    r'<meta[^>]+content=["\']([^"\']{20,})["\'][^>]+name=["\']description["\']',
    r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']{20,})["\']',
    r'<meta[^>]+content=["\']([^"\']{20,})["\'][^>]+property=["\']og:description["\']',
    r"<title[^>]*>([^<]{10,})</title>",
)]


def self_description(html: str) -> str:
    """What the page says it is: meta description, og:description, or the title."""
    for rx in _META:
        m = rx.search(html or "")
        if m:
            return " ".join(htmllib.unescape(m.group(1)).split())[:300]
    return ""
