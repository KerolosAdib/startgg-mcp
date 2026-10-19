"""start.gg URLs built from the slugs the scraper stores."""

from .config import STARTGG_BASE_URL


def startgg_url(slug: str | None) -> str | None:
    """Full start.gg URL for a slug such as `user/a1b2c3d4` or
    `tournament/evo/event/sf6`, or None when there is no slug."""
    if not slug:
        return None
    return STARTGG_BASE_URL + slug.lstrip("/")


def slug_from_url(value: str) -> str:
    """Turn a start.gg URL or slug into the stored event slug form
    (`tournament/<name>/event/<name>`), dropping anything after the event name."""
    slug = value.strip()
    for prefix in ("https://", "http://"):
        slug = slug.removeprefix(prefix)
    for host in ("www.start.gg/", "start.gg/"):
        slug = slug.removeprefix(host)
    parts = [p for p in slug.split("/") if p]
    if len(parts) >= 4 and parts[0] == "tournament" and parts[2] == "event":
        parts = parts[:4]
    return "/".join(parts)
