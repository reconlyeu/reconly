"""
Tests for Digest CRUD operations.
"""
import pytest
from reconly_core.database.crud import DigestDB
from reconly_core.database.models import Digest


@pytest.mark.database
@pytest.mark.unit
def test_create_digest(db_session):
    """Test creating a digest."""
    digest_db = DigestDB(session=db_session)

    digest = digest_db.create_digest(
        title="Test Article",
        url="https://example.com/test",
        content="Test content",
        summary="Test summary",
        source_type="website",
        tags=["test", "example"],
        language="en"
    )

    assert digest.id is not None
    assert digest.title == "Test Article"
    assert digest.url == "https://example.com/test"
    assert [tag.tag.name for tag in digest.tags] == ["test", "example"]
    assert digest.language == "en"


@pytest.mark.database
@pytest.mark.unit
def test_get_digest_by_id(db_session):
    """Test getting digest by ID."""
    digest_db = DigestDB(session=db_session)

    # Create digest
    created = digest_db.create_digest(
        title="Test Article",
        url="https://example.com/test",
        content="Test content",
        summary="Test summary",
        source_type="website",
        tags=["test"],
        language="en"
    )
    db_session.commit()

    # Retrieve by ID
    retrieved = digest_db.get_digest_by_id(created.id)

    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.title == "Test Article"


@pytest.mark.database
@pytest.mark.unit
def test_get_nonexistent_digest(db_session):
    """Test getting non-existent digest returns None."""
    digest_db = DigestDB(session=db_session)
    result = digest_db.get_digest_by_id(99999)

    assert result is None


@pytest.mark.database
@pytest.mark.unit
def test_get_digests_by_ids(db_session):
    """Test getting multiple digests by IDs."""
    digest_db = DigestDB(session=db_session)

    # Create multiple digests
    digest1 = digest_db.create_digest(
        title="Article 1",
        url="https://example.com/1",
        content="Content 1",
        summary="Summary 1",
        source_type="website",
        tags=["test"],
        language="en"
    )
    digest2 = digest_db.create_digest(
        title="Article 2",
        url="https://example.com/2",
        content="Content 2",
        summary="Summary 2",
        source_type="website",
        tags=["test"],
        language="en"
    )
    digest3 = digest_db.create_digest(
        title="Article 3",
        url="https://example.com/3",
        content="Content 3",
        summary="Summary 3",
        source_type="website",
        tags=["test"],
        language="en"
    )
    db_session.commit()

    # Retrieve by IDs (order should be preserved)
    ids = [digest1.id, digest3.id, digest2.id]
    retrieved = digest_db.get_digests_by_ids(ids)

    assert len(retrieved) == 3
    assert retrieved[0].id == digest1.id
    assert retrieved[1].id == digest3.id
    assert retrieved[2].id == digest2.id


@pytest.mark.database
@pytest.mark.unit
def test_get_digests_by_ids_empty_list(db_session):
    """Test getting digests with empty ID list returns empty list."""
    digest_db = DigestDB(session=db_session)
    result = digest_db.get_digests_by_ids([])

    assert result == []


@pytest.mark.database
@pytest.mark.unit
def test_get_digests_by_ids_nonexistent(db_session):
    """Test getting digests with non-existent IDs."""
    digest_db = DigestDB(session=db_session)

    # Create one digest
    digest = digest_db.create_digest(
        title="Article 1",
        url="https://example.com/1",
        content="Content 1",
        summary="Summary 1",
        source_type="website",
        tags=["test"],
        language="en"
    )
    db_session.commit()

    # Request existing and non-existing IDs
    ids = [digest.id, 99999, 88888]
    retrieved = digest_db.get_digests_by_ids(ids)

    # Should only return existing digest
    assert len(retrieved) == 1
    assert retrieved[0].id == digest.id


@pytest.mark.database
@pytest.mark.unit
def test_list_digests(db_session):
    """Test listing digests."""
    digest_db = DigestDB(session=db_session)

    # Create multiple digests
    for i in range(10):
        digest_db.create_digest(
            title=f"Article {i}",
            url=f"https://example.com/{i}",
            content=f"Content {i}",
            summary=f"Summary {i}",
            source_type="website",
            tags=["test"],
            language="en"
        )
    db_session.commit()

    # List with limit
    results = digest_db.list_digests(limit=5)

    assert len(results) == 5


@pytest.mark.database
@pytest.mark.unit
def test_search_digests(db_session):
    """Test searching digests."""
    digest_db = DigestDB(session=db_session)

    # Create test digests
    digest_db.create_digest(
        title="Python Programming Guide",
        url="https://example.com/python",
        content="Learn Python from scratch",
        summary="Python tutorial",
        source_type="website",
        tags=["python"],
        language="en"
    )
    digest_db.create_digest(
        title="JavaScript Basics",
        url="https://example.com/javascript",
        content="Learn JavaScript fundamentals",
        summary="JS tutorial",
        source_type="website",
        tags=["javascript"],
        language="en"
    )
    db_session.commit()

    # Search for Python
    results = digest_db.search_digests("Python")

    assert len(results) >= 1
    assert any("Python" in d.title for d in results)


@pytest.mark.database
@pytest.mark.unit
def test_filter_by_source_type(db_session):
    """Test filtering digests by source type."""
    digest_db = DigestDB(session=db_session)

    # Create digests with different source types
    digest_db.create_digest(
        title="Website Article",
        url="https://example.com/web",
        content="Web content",
        summary="Web summary",
        source_type="website",
        tags=["test"],
        language="en"
    )
    digest_db.create_digest(
        title="RSS Article",
        url="https://example.com/rss",
        content="RSS content",
        summary="RSS summary",
        source_type="rss",
        tags=["test"],
        language="en"
    )
    db_session.commit()

    # Filter by source type
    results = digest_db.list_digests(source_type="rss")

    assert len(results) >= 1
    for digest in results:
        assert digest.source_type == "rss"


@pytest.mark.database
@pytest.mark.unit
def test_filter_by_tags(db_session):
    """Test filtering digests by tags."""
    digest_db = DigestDB(session=db_session)

    # Create digests with different tags
    digest_db.create_digest(
        title="Python Article",
        url="https://example.com/python",
        content="Python content",
        summary="Python summary",
        source_type="website",
        tags=["python", "programming"],
        language="en"
    )
    digest_db.create_digest(
        title="Sports Article",
        url="https://example.com/sports",
        content="Sports content",
        summary="Sports summary",
        source_type="website",
        tags=["sports", "news"],
        language="en"
    )
    db_session.commit()

    # Filter by tags
    results = digest_db.list_digests(tags=["python"])

    assert len(results) >= 1
    for digest in results:
        tag_names = [tag.tag.name for tag in digest.tags]
        assert "python" in tag_names
