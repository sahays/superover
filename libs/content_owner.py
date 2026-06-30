"""Content ownership tagging — derive a studio owner slug from a filename.

Scopes conversational search per studio (Sony, Zee, …). One rule, one place:
upload, sync, and the backfill all call ``derive_owner_from_filename`` so
tagging stays consistent. Returns "" when no configured marker matches, which
means "untagged / shared" — visible to every studio.
"""

from config import get_settings


def derive_owner_from_filename(filename: str) -> str:
    """Return the owner slug whose marker appears in ``filename``, else "".

    Matching is case-insensitive substring against the configured
    ``content_owners`` map (slug -> [markers]). The first matching slug wins
    (config insertion order). An empty/None filename returns "".
    """
    if not filename:
        return ""
    name = filename.lower()
    for slug, markers in get_settings().content_owners.items():
        for marker in markers:
            if marker and marker.lower() in name:
                return slug
    return ""
