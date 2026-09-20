import datetime

from app.ingestion.normalizer import (
    normalize_abstract,
    normalize_author_name,
    normalize_datetime,
    parse_arxiv_id_and_version,
)
from app.ingestion.parser import parse_arxiv_response

# Sample XML fragment resembling arXiv Atom output
SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.12345v2</id>
    <updated>2024-01-25T14:30:00Z</updated>
    <published>2024-01-20T10:00:00Z</published>
    <title>A Sample Paper</title>
    <summary>This is the abstract.
    
    It has newlines.</summary>
    <author>
      <name>John D. O'Connor</name>
    </author>
    <author>
      <name>René Descartes</name>
    </author>
    <arxiv:doi>10.1234/5678</arxiv:doi>
    <arxiv:primary_category term="cs.AI" scheme="http://arxiv.org/schemas/atom"/>
    <category term="cs.AI" scheme="http://arxiv.org/schemas/atom"/>
    <category term="cs.LG" scheme="http://arxiv.org/schemas/atom"/>
    <link href="http://arxiv.org/pdf/2401.12345v2" rel="related" title="pdf" type="application/pdf"/>
  </entry>
</feed>
"""


def test_parser_valid_xml():
    dtos = parse_arxiv_response(SAMPLE_XML)
    assert len(dtos) == 1
    dto = dtos[0]

    assert dto.id == "http://arxiv.org/abs/2401.12345v2"
    assert dto.title == "A Sample Paper"
    assert dto.doi == "10.1234/5678"
    assert dto.primary_category == "cs.AI"
    assert dto.pdf_url == "http://arxiv.org/pdf/2401.12345v2"

    assert len(dto.authors) == 2
    assert dto.authors[0].name == "John D. O'Connor"
    assert dto.authors[1].name == "René Descartes"

    assert len(dto.categories) == 2
    assert dto.categories[0].term == "cs.AI"


def test_normalizer_datetime():
    dt = normalize_datetime("2024-01-25T14:30:00Z")
    assert dt.year == 2024
    assert dt.month == 1
    assert dt.hour == 14
    assert dt.tzinfo == datetime.UTC


def test_normalizer_author_name():
    # Casefolding and punctuation stripping
    assert normalize_author_name("John D. O'Connor") == "john d oconnor"
    # Unicode decomposition (é -> e)
    assert normalize_author_name("René Descartes") == "rene descartes"
    # Multiple spaces
    assert normalize_author_name("A  B   C") == "a b c"


def test_normalizer_abstract():
    raw = "This is the abstract.\n\nIt has newlines and \x00 control chars."
    clean = normalize_abstract(raw)
    assert "newlines and control chars" in clean
    assert "This is the abstract. It has" in clean
    assert "\n" not in clean


def test_parse_arxiv_id_and_version():
    arxiv_id, version = parse_arxiv_id_and_version("http://arxiv.org/abs/2401.12345v2")
    assert arxiv_id == "2401.12345"
    assert version == 2

    arxiv_id, version = parse_arxiv_id_and_version("http://arxiv.org/abs/hep-th/9901001")
    assert arxiv_id == "hep-th/9901001"
    assert version == 1
