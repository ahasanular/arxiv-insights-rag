from io import BytesIO

from lxml import etree

from app.ingestion.schemas import AuthorDTO, CategoryDTO, PaperDTO

NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}


def parse_arxiv_response(xml_text: str) -> list[PaperDTO]:
    """
    Parses arXiv Atom XML feed securely.
    Converts to PaperDTOs.
    """
    # XXE-safe parser
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    try:
        root = etree.parse(BytesIO(xml_text.encode("utf-8")), parser)
    except etree.XMLSyntaxError as e:
        import structlog

        logger = structlog.get_logger(__name__)
        logger.error("XML parsing error", error=str(e))
        return []

    papers: list[PaperDTO] = []

    for entry in root.xpath("//atom:entry", namespaces=NAMESPACES):
        # Extract fields using XPath
        id_node = entry.xpath("./atom:id/text()", namespaces=NAMESPACES)
        if not id_node:
            continue

        paper_id = id_node[0].strip()

        updated = _get_text(entry, "./atom:updated")
        published = _get_text(entry, "./atom:published")
        title = _get_text(entry, "./atom:title")
        summary = _get_text(entry, "./atom:summary")

        # Extracted namespaced fields
        doi = _get_text(entry, "./arxiv:doi")
        journal_ref = _get_text(entry, "./arxiv:journal_ref")
        comment = _get_text(entry, "./arxiv:comment")
        primary_category = entry.xpath("./arxiv:primary_category/@term", namespaces=NAMESPACES)
        primary_category_term = primary_category[0] if primary_category else None

        # Authors
        authors = []
        for author in entry.xpath("./atom:author", namespaces=NAMESPACES):
            name = _get_text(author, "./atom:name")
            if name:
                authors.append(AuthorDTO(name=name))

        # Categories
        categories = []
        for category in entry.xpath("./atom:category", namespaces=NAMESPACES):
            term = category.get("term")
            if term:
                categories.append(CategoryDTO(term=term))

        # PDF URL
        pdf_url = None
        for link in entry.xpath("./atom:link", namespaces=NAMESPACES):
            if link.get("title") == "pdf":
                pdf_url = link.get("href")
                break

        papers.append(
            PaperDTO(
                id=paper_id,
                updated=updated,
                published=published,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=primary_category_term,
                doi=doi,
                journal_ref=journal_ref,
                comment=comment,
                pdf_url=pdf_url,
            )
        )

    return papers


def _get_text(node: etree._Element, xpath_query: str) -> str:
    result = node.xpath(f"{xpath_query}/text()", namespaces=NAMESPACES)
    return result[0].strip() if result else ""
