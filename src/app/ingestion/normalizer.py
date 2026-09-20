import datetime
import hashlib
import re
import unicodedata
from typing import Any

from app.ingestion.schemas import PaperDTO


def normalize_datetime(dt_str: str) -> datetime.datetime:
    """Converts RFC3339 string to tz-aware UTC datetime."""
    # Handle zulu time suffix
    if dt_str.endswith("Z"):
        dt_str = dt_str[:-1] + "+00:00"
    return datetime.datetime.fromisoformat(dt_str).astimezone(datetime.UTC)


def normalize_author_name(name: str) -> str:
    """
    Normalizes author name for unique deduplication.
    Rules: casefold, NFKD (decompose accents), strip punctuation.
    """
    # Decompose unicode
    nfkd = unicodedata.normalize("NFKD", name)
    # Casefold
    lower = nfkd.casefold()
    # Strip punctuation and multiple spaces
    no_punct = re.sub(r"[^\w\s]", "", lower)
    return re.sub(r"\s+", " ", no_punct).strip()


def normalize_abstract(raw: str) -> str:
    """
    Unwraps hard newlines, collapses whitespace, strips control chars.
    Leaves LaTeX math as-is mostly, but fixes visual flow.
    """
    # Strip control chars except whitespace (\t, \n, \r)
    no_control = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", raw)
    # Replace newlines with space to unwrap
    unwrapped = no_control.replace("\n", " ")
    # Collapse multiple spaces
    return re.sub(r"\s+", " ", unwrapped).strip()


def parse_arxiv_id_and_version(url_id: str) -> tuple[str, int]:
    """
    Extracts versionless arxiv_id and version number.
    e.g. 'http://arxiv.org/abs/2401.12345v2' -> ('2401.12345', 2)
    """
    # The ID part is after /abs/
    parts = url_id.split("/abs/")
    if len(parts) < 2:
        return url_id, 1

    raw_id = parts[-1]
    # Check for version suffix 'vN'
    match = re.search(r"(.*)v(\d+)$", raw_id)
    if match:
        return match.group(1), int(match.group(2))
    return raw_id, 1


def generate_content_hash(title: str, abstract: str) -> str:
    """
    SHA256 hash of title + abstract to drive selective re-embedding.
    """
    content = f"{title}\n\n{abstract}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def normalize_paper(dto: PaperDTO) -> dict[str, Any]:
    """
    Takes a parsed DTO and normalizes it to dict payload suitable for upsert.
    """
    arxiv_id, version = parse_arxiv_id_and_version(dto.id)

    normalized_authors = []
    for pos, author in enumerate(dto.authors):
        normalized_authors.append(
            {
                "display_name": author.name,
                "normalized_name": normalize_author_name(author.name),
                "position": pos,
            }
        )

    normalized_categories = []
    for cat in dto.categories:
        normalized_categories.append(
            {
                "code": cat.term,
                "is_primary": cat.term == dto.primary_category,
            }
        )

    abstract_clean = normalize_abstract(dto.summary)

    return {
        "arxiv_id": arxiv_id,
        "version": version,
        "title": normalize_abstract(dto.title),  # also unwrap title just in case
        "abstract_raw": dto.summary,
        "abstract": abstract_clean,
        "published_at": normalize_datetime(dto.published),
        "updated_at_source": normalize_datetime(dto.updated),
        "doi": dto.doi if dto.doi else None,
        "journal_ref": dto.journal_ref if dto.journal_ref else None,
        "comment": dto.comment if dto.comment else None,
        "primary_category_code": dto.primary_category,
        "content_hash": generate_content_hash(dto.title, abstract_clean),
        "abs_url": dto.id,
        "pdf_url": dto.pdf_url if dto.pdf_url else dto.id.replace("/abs/", "/pdf/"),
        "authors": normalized_authors,
        "categories": normalized_categories,
    }
