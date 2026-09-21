from app.ingestion.parser import parse_arxiv_response


def test_parse_invalid_xml():
    """Test parsing completely invalid XML string."""
    invalid_xml = "<feed> <entry> <id>unclosed id"
    dtos = parse_arxiv_response(invalid_xml)
    assert len(dtos) == 0, "Parser should return empty list on XMLSyntaxError"


def test_parse_missing_required_fields():
    """Test parsing an entry missing the <id> node (which causes it to be skipped)."""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
      <entry>
        <updated>2024-01-25T14:30:00Z</updated>
        <title>A Sample Paper</title>
        <summary>This is the abstract.</summary>
      </entry>
    </feed>
    """
    dtos = parse_arxiv_response(xml)
    assert len(dtos) == 0, "Entries without <id> should be skipped"


def test_parse_extreme_abstract_length():
    """Test parsing an entry with an extremely large abstract."""
    huge_abstract = "A" * 150000  # 150k characters
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
      <entry>
        <id>http://arxiv.org/abs/2401.12345v1</id>
        <title>Huge Abstract Paper</title>
        <summary>{huge_abstract}</summary>
      </entry>
    </feed>
    """
    dtos = parse_arxiv_response(xml)
    assert len(dtos) == 1
    assert len(dtos[0].summary) == 150000


def test_parse_author_explosion():
    """Test parsing an entry with 10,000 authors."""
    authors_xml = "\n".join(
        f"<author><name>Author {i}</name></author>" for i in range(10000)
    )
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
      <entry>
        <id>http://arxiv.org/abs/2401.12346v1</id>
        <title>Massive Collaboration</title>
        {authors_xml}
      </entry>
    </feed>
    """
    dtos = parse_arxiv_response(xml)
    assert len(dtos) == 1
    assert len(dtos[0].authors) == 10000
    assert dtos[0].authors[-1].name == "Author 9999"


def test_parse_malformed_fields():
    """Test parsing malformed namespaces or weird field values."""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
      <entry>
        <id>http://arxiv.org/abs/2401.12347v1</id>
        <arxiv:doi></arxiv:doi>
        <arxiv:primary_category term="weird!@#$category" scheme="http://arxiv.org/schemas/atom"/>
        <updated>Not-A-Date</updated>
      </entry>
    </feed>
    """
    dtos = parse_arxiv_response(xml)
    assert len(dtos) == 1
    assert dtos[0].doi == ""
    assert dtos[0].primary_category == "weird!@#$category"
    assert dtos[0].updated == "Not-A-Date"
